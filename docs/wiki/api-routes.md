# API Routes

RA2 Modder exposes four Flask blueprints. All routes return either full HTML pages (for initial load) or HTMX partials (for dynamic updates).

## Blueprint Overview

| Blueprint | URL Prefix | Module | Purpose |
|---|---|---|---|
| `objects` | `/` | `routes/objects.py` | Object browsing, detail views, inline editing |
| `sprites` | `/sprites` | `routes/sprites.py` | Cameo icons, VXL/SHP preview rendering |
| `assets` | `/assets` | `routes/assets.py` | Raw game file browser |
| `patch` | `/patch` | `routes/patch_view.py` | Pending changes view and export |

## Objects Blueprint

### `GET /`

Redirects to the first object type (VehicleTypes) with default filters.

### `GET /<obj_type>`

Lists all objects of a type. Supports filtering and search.

**Query parameters:**

| Param | Default | Description |
|---|---|---|
| `q` | `""` | Search query (matches ID and display name) |
| `side` | `""` | Filter by faction (e.g. `"Allied"`, `"Soviet"`) |
| `tech_min` | `"0"` | Minimum tech level (0 = no filter) |

**HTMX dual-response pattern:**

```python
if request.headers.get("HX-Request"):
    return render_template("partials/unit_cards.html", ...)
return render_template("pages/object_list.html", ...)
```

When called via HTMX (`HX-Request` header present), returns only the `unit_cards.html` partial containing the object list. For full page loads, returns the complete `object_list.html` page with sidebar, filters, and card grid.

### `GET /<obj_type>/<obj_id>`

Shows object detail with all properties and preview.

**HTMX response:** Returns `detail_tabs.html` partial (properties table + VXL/SHP preview).

**Full page response:** Returns complete `object_list.html` with the object selected.

**Preview modes** are determined by `get_vxl_modes()`:

```python
vxl_modes = get_vxl_modes(
    obj_id, art, rules, game_files, obj_type=obj_type
)
```

### `POST /edit/<obj_id>/<field>`

Saves an edited field value. Called by HTMX inline edit forms.

**Form data:**

| Field | Description |
|---|---|
| `old_value` | Original value (for UI display) |
| `new_value` | New value to persist |

**Behaviour:**
- Only writes to patch if `old_value != new_value`
- Calls `save_field()` to persist to `mypatch/rulesmd.ini`
- Returns `diff_line.html` partial showing old → new change

### `POST /revert/<obj_id>/<field>`

Removes a field edit from the patch, restoring the base game value.

- Calls `revert_field()` to remove the key from the patch file
- Returns empty `200` response
- HTMX removes the change indicator in the UI

### `POST /reindex`

Rebuilds the SQLite index from current game files and patch:

1. Reloads rules and art INI (including patch overlay)
2. Re-parses CSF string tables
3. Closes the old DB connection
4. Calls `build_index()` to create a fresh in-memory database
5. Stores new connection in `app.config["DB"]`
6. Redirects to `/`

### `GET /<obj_type>/<obj_id>/tree`

Returns a tech tree partial showing prerequisites (upstream) and dependents (downstream) for the object.

**Query parameters:**

| Param | Default | Description |
|---|---|---|
| `types` | all types | Checkbox filter — only show objects of these types (repeatable param) |

**Response:** HTMX partial `tech_tree.html` with:
- Type filter checkboxes (auto-submits on change)
- Prerequisites section — objects required to build this one (recursive)
- Root node — the current object highlighted
- Dependents section — objects this one unlocks (recursive)

## Sprites Blueprint

### `GET /sprites/<obj_id>/cameo.png`

Serves a cameo icon (build queue thumbnail) for the object.

**Query parameters:**

| Param | Default | Description |
|---|---|---|
| `side` | `""` | Faction name for placeholder colouring |

**Resolution chain** (first match wins):

1. **CameoPCX** — Ares extension: `art_section["CameoPCX"]` → load `.pcx` file directly
2. **Cameo SHP** — `art_section["Cameo"]` → render `<name>.shp` with `cameo.pal`
3. **Convention** — `<obj_id>cameo.shp` → render with `cameo.pal`
4. **Placeholder** — 60×48 faction-coloured PNG

Placeholder colours:

| Faction | Colour |
|---|---|
| Allied / GDI | Blue `(30, 60, 160)` |
| Soviet / Nod | Red `(160, 30, 30)` |
| Yuri / ThirdSide | Purple `(110, 30, 140)` |
| Other | Dark grey `(45, 52, 70)` |

### `GET /sprites/<obj_id>/vxl.png`

Serves a VXL voxel render or SHP sprite preview.

**Query parameters:**

| Param | Default | Description |
|---|---|---|
| `facing` | `4` | Direction 0–7 (N, NE, E, SE, S, SW, W, NW) |
| `mode` | `"base"` | Preview mode — see below |
| `theater` | `"temperate"` | Theater variant for NewTheater buildings (temperate/snow/urban/etc.) |

**VXL modes:**

| Mode | Renders |
|---|---|
| `base` | Body hull only |
| `turret` | Turret only |
| `barrel` | Barrel only |
| `composite` | Body + turret + barrel overlaid |
| `deployed` | Deployed state VXL |

**SHP modes:**

| Mode | Renders |
|---|---|
| `shp_stand` | Infantry standing frame for the given facing |
| `shp_building` | Building undamaged frame 0 (ignores facing) |
| `shp_building_damaged` | Building damaged frame 1 |
| `anim_ActiveAnim` | ActiveAnim overlay as animated GIF |
| `anim_IdleAnim` | IdleAnim overlay as animated GIF |
| `anim_<Key>` | Any art.ini animation key as animated GIF |

**Composite rendering flow:**

```
1. Parse body VXL to find Z height
2. Compute turret offset = body_z * 0.35
3. Merge body + turret + barrel at offset
4. render_vxl_composite() produces 128×128 image
```

**SHP infantry flow:**

```
1. Resolve Image= key → find <base>.shp
2. Parse Sequence section from art INI → get Ready= info
3. frame_index = start_frame + facing * frames_per_facing
4. render_shp() with unit palette
```

### `get_vxl_modes(obj_id, art, rules, game_files, obj_type)`

Helper function (not a route) that determines available preview modes:

```python
# Priority: VXL files first
if f"{base}.vxl" exists:
    return VXL modes (composite/base/turret/barrel/deployed)

# SHP fallback by object type
if f"{base}.shp" exists:
    if obj_type == "InfantryTypes":  → [("shp_stand", "Stand")]
    if obj_type == "BuildingTypes":  → [("shp_building", "Building")]

return []  # no preview available
```

### `_resolve_image_key(obj_id, art, rules)`

Resolves the `Image=` indirection for visual asset lookup:

```python
rules_section = rules.get(obj_id, {})
image_key = rules_section.get("Image", obj_id)  # default: obj_id itself
art_section = art.get(image_key, art.get(obj_id, {}))
return image_key, art_section
```

## Assets Blueprint

### `GET /assets`

Shows all files extracted from MIX archives, grouped by extension.

Returns a page with:
- Total file count
- Files organized by extension (`.vxl`, `.shp`, `.ini`, `.pal`, etc.)
- File sizes for each entry

```python
by_ext: dict[str, list[tuple[str, int]]] = {}
for name, data in sorted(game_files.items()):
    ext = os.path.splitext(name)[1].lower() or "(none)"
    by_ext.setdefault(ext, []).append((name, len(data)))
```

## Patch Blueprint

### `GET /patch`

Displays all pending patch changes in a table.

Reads the diff via `get_diff()` and renders `pages/patch.html`.

### `GET /patch/export`

Downloads the patch as a `rulesmd.ini` file attachment.

```python
diff = get_diff(config.patch_dir)
text = serialise_patch(diff)
return Response(
    text,
    mimetype="text/plain",
    headers={"Content-Disposition": "attachment; filename=rulesmd.ini"},
)
```

## HTMX Integration Pattern

Most routes follow a dual-response pattern for HTMX compatibility:

```python
@bp.route("/<obj_type>")
def object_list(obj_type):
    # ... load data ...

    if request.headers.get("HX-Request"):
        # HTMX request: return only the partial that changed
        return render_template("partials/unit_cards.html", ...)

    # Full page load: return complete page
    return render_template("pages/object_list.html", ...)
```

This enables:
- **First load**: Server renders the full page
- **Navigation**: HTMX swaps only the relevant section, preserving scroll position and filter state
- **No JavaScript framework**: All interactivity is declarative via `hx-get`, `hx-post`, `hx-target`
