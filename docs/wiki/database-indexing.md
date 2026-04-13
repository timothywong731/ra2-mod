# Database & Indexing

RA2 Modder uses an **in-memory SQLite** database as a fast, queryable index over the parsed INI data. The index is rebuilt from scratch on startup and can be refreshed at runtime via the reindex button.

## Why SQLite?

Raw INI data is nested dictionaries — workable but slow for filtering, searching, and sorting across thousands of objects. SQLite provides:

- **Indexed lookups** by type, name, and tech level
- **Case-insensitive LIKE** search across IDs and display names
- **No external dependencies** — `sqlite3` ships with Python
- **Zero persistence** — in-memory database means no stale cache files

## Schema

```sql
CREATE TABLE objects (
    id TEXT PRIMARY KEY,         -- e.g. "APOC", "E1"
    type TEXT NOT NULL,          -- e.g. "VehicleTypes", "InfantryTypes"
    display_name TEXT NOT NULL,  -- resolved from CSF strings
    side TEXT NOT NULL DEFAULT '',  -- e.g. "Soviet", "Allied,Soviet"
    tech_level INTEGER NOT NULL DEFAULT 0,
    props TEXT NOT NULL DEFAULT '{}',  -- JSON of rules section
    art TEXT NOT NULL DEFAULT '{}'     -- JSON of art section
);

CREATE INDEX idx_type ON objects(type);
CREATE INDEX idx_name ON objects(display_name COLLATE NOCASE);
CREATE INDEX idx_tech ON objects(tech_level);
```

The `props` and `art` columns store full JSON blobs of the parsed INI sections. This avoids the need for a separate table per key and allows the detail page to show all properties without additional queries.

## Object Types

The indexer processes these registry sections from `rulesmd.ini`:

```python
OBJECT_TYPES = [
    "VehicleTypes",
    "InfantryTypes",
    "AircraftTypes",
    "BuildingTypes",
    "WeaponTypes",
    "Warheads",
    "Projectiles",
    "SuperWeaponTypes",
]
```

Each registry section is a numbered list:

```ini
[VehicleTypes]
0=HTNK
1=APOC
2=MTNK
...
```

The indexer iterates each entry, reads its full section from rules, resolves its Image= key for art, and inserts a row into the database.

## Build Process

### `build_index(rules, art, strings) → Connection`

```
rules INI ──┐
art INI   ──┼──→ build_index() ──→ sqlite3.Connection (in-memory)
CSF strings ┘
```

Steps:

1. **Create schema** — `CREATE TABLE objects` with three indexes
2. **Build side map** — `_resolve_sides()` maps country IDs to faction names
3. **Index objects** — For each registry type:
   - Read the numbered list (e.g. `[VehicleTypes]`)
   - For each object ID, resolve its rules section, art section, display name, side, and tech level
   - `INSERT OR REPLACE` into the database
4. **Commit** and return the connection

### Connection configuration

```python
conn = sqlite3.connect(":memory:", check_same_thread=False)
conn.row_factory = sqlite3.Row     # dict-like row access
conn.execute("PRAGMA journal_mode=OFF")  # no WAL for in-memory
```

`check_same_thread=False` is required because Flask may serve requests on different threads than the one that created the connection. This is safe since all writes happen at build time; runtime access is read-only.

## Side Resolution

RA2 objects don't store faction names directly. Instead, they have an `Owner=` key listing country names, and each country has a `Side=` key.

### Step 1: Build country→side map

```python
def _resolve_sides(rules):
    side_map = {}
    countries = rules.get("Countries", {})
    for _idx, country_id in countries.items():
        country_data = rules.get(country_id, {})
        side = country_data.get("Side", "")
        if side:
            side_map[country_id] = side
    return side_map
# {"Americans": "Allied", "Russians": "Soviet", "YuriCountry": "ThirdSide"}
```

### Step 2: Resolve object's side(s)

```python
def _resolve_object_side(owner_str, side_map):
    sides = set()
    for owner in owner_str.split(","):
        side = side_map.get(owner.strip(), "")
        if side:
            sides.add(side)
    return ",".join(sorted(sides))

# Owner=Americans,British → "Allied"
# Owner=Russians,Cubans  → "Soviet"
# Owner=Americans,Russians → "Allied,Soviet"
```

Objects available to multiple factions get a comma-separated side string.

## Image= Key Resolution

When indexing, the art section is resolved through the `Image=` indirection:

```python
image_key = obj_section.get("Image", obj_id)
art_section = art.get(image_key, art.get(obj_id, {}))
```

This means `APOC` with `Image=MTNK` stores `art["MTNK"]` in its `art` column, not `art["APOC"]`.

## Display Name Resolution

The display name comes from C&C's **CSF** string table:

```python
name_key = obj_section.get("Name", "")      # e.g. "Name:APOC"
display_name = strings.get(name_key, obj_id)  # e.g. "Apocalypse Tank"
```

If the CSF key is missing or unresolved, the object ID itself is used as the display name.

## Query Functions

### `list_objects(conn, obj_type, side, tech_min)`

Returns all objects of a type with optional filtering:

```python
# Base query
sql = "SELECT ... FROM objects WHERE type = ?"

# Optional filters appended dynamically
if side:
    sql += " AND side LIKE ?"     # partial match for multi-faction
if tech_min is not None:
    sql += " AND tech_level >= ?"

sql += " ORDER BY display_name"
```

### `get_distinct_sides(conn, obj_type)`

Returns unique faction names for the sidebar filter. Handles comma-separated sides by splitting:

```python
sides = set()
for row in rows:
    for s in row[0].split(","):
        sides.add(s.strip())
return sorted(sides)
# ["Allied", "Soviet", "ThirdSide"]
```

### `get_object(conn, obj_id)`

Returns a single object with its `props` and `art` JSON parsed back into dictionaries:

```python
d["props"] = json.loads(d["props"])
d["art"] = json.loads(d["art"])
```

### `search_objects(conn, query)`

Case-insensitive LIKE search across both `display_name` and `id`, limited to 100 results:

```sql
WHERE display_name LIKE ? COLLATE NOCASE
   OR id LIKE ? COLLATE NOCASE
ORDER BY display_name
LIMIT 100
```

## Reindex Flow

The `/reindex` POST route rebuilds the index at runtime:

```
POST /reindex
    │
    ├─ Reload rules (base + patch)
    ├─ Reload art (base + patch)
    ├─ Re-parse CSF strings
    ├─ Close old DB connection
    ├─ build_index() → new Connection
    ├─ Store in app.config["DB"]
    └─ Redirect to /
```

This picks up any changes to the patch file or newly extracted game files without restarting the Flask server.
