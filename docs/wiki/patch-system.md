# Patch System

RA2 Modder uses a **non-destructive patch** approach. Original game files are never modified. Instead, all edits are stored in a separate patch directory and merged on top of the base data at load time.

## Design Philosophy

```
┌──────────────────────────┐
│  Original game files     │  read-only
│  rules(md).ini           │
│  art(md).ini             │
└──────────┬───────────────┘
           │ parse + merge
           ▼
┌──────────────────────────┐
│  mypatch/rulesmd.ini     │  user edits only
└──────────┬───────────────┘
           │ overlay
           ▼
┌──────────────────────────┐
│  Merged INI data         │  in-memory result
│  (base + patch)          │
└──────────────────────────┘
```

Benefits:
- **Reversible**: Deleting `mypatch/rulesmd.ini` instantly restores original game state
- **Portable**: The patch file alone captures all user modifications
- **Transparent**: Each edit is visible as a key=value line in standard INI format
- **Safe**: No risk of corrupting the installed game

## Patch Directory

By default, the patch lives at `<game_dir>/mypatch/`:

```python
@dataclass
class GameConfig:
    game_dir: Path
    patch_dir: Path       # game_dir / "mypatch"
    cache_dir: Path
    mix_load_order: list[str]
    mod_type: str         # "vanilla", "ares", "phobos"
```

The directory is created automatically on the first field save. Structure:

```
C:\RA2\
├── ra2.mix              ← original game archive
├── ra2md.mix            ← original game archive
└── mypatch/
    └── rulesmd.ini      ← all pending edits
```

## Patch File Format

The patch file is a standard RA2 INI file containing only modified sections and keys:

```ini
[APOC]
Strength=800
Cost=1500

[HTNK]
Speed=6
```

Sections are sorted alphabetically, and keys within each section are also sorted. This produces clean, predictable diffs.

## Core Operations

### `save_field(patch_dir, section, key, old_value, new_value)`

Persists a single field change:

```python
def save_field(patch_dir, section, key, old_value, new_value):
    patch_file = patch_dir / "rulesmd.ini"
    patch_dir.mkdir(parents=True, exist_ok=True)

    existing = _load_patch(patch_file)
    existing.setdefault(section, {})[key] = new_value
    _write_patch(patch_file, existing)
```

The entire patch file is re-read, updated, and re-written on each save. This keeps the implementation simple and the file always consistent. The `old_value` parameter is passed through for UI purposes but is not stored in the patch.

### `revert_field(patch_dir, section, key)`

Removes a single field from the patch, restoring the base game value:

```python
def revert_field(patch_dir, section, key):
    patch_file = patch_dir / "rulesmd.ini"
    existing = _load_patch(patch_file)

    if section in existing:
        existing[section].pop(key, None)
        if not existing[section]:
            del existing[section]       # clean up empty sections

    _write_patch(patch_file, existing)
```

Empty sections are automatically cleaned up so the patch file never contains `[SECTION]` with no keys.

### `get_diff(patch_dir)`

Returns all pending changes as a nested dictionary:

```python
def get_diff(patch_dir) -> dict[str, dict[str, str]]:
    patch_file = patch_dir / "rulesmd.ini"
    return _load_patch(patch_file)

# Returns: {"APOC": {"Strength": "800", "Cost": "1500"}, ...}
```

### `serialise_patch(diff)`

Converts the diff dictionary back into a downloadable INI string:

```python
def serialise_patch(diff) -> str:
    lines = []
    for section, keys in sorted(diff.items()):
        lines.append(f"[{section}]")
        for key, value in sorted(keys.items()):
            lines.append(f"{key}={value}")
        lines.append("")
    return "\n".join(lines)
```

## Merge Chain

When loading rules or art data, the patch is overlaid on the base INI:

```python
# In ini/rules.py
def load_rules(game_files, patch_dir):
    data = {}
    # 1. Parse base rulesmd.ini from game archives
    for key in game_files:
        if key.lower() == "rulesmd.ini":
            data = parse_ini(game_files[key].decode("latin-1"))
    # 2. Merge patch on top
    patch = _load_patch(patch_dir / "rulesmd.ini")
    for section, keys in patch.items():
        data.setdefault(section, {}).update(keys)
    return data
```

The patch always wins. If the base has `[APOC] Strength=600` and the patch has `[APOC] Strength=800`, the merged result is `800`.

## Edit Flow (HTTP)

Field editing is driven by HTMX inline forms:

```
1. User clicks a value cell → HTMX swaps in an <input> form
2. User types new value and presses Enter
3. POST /edit/APOC/Strength  { old_value: "600", new_value: "800" }
4. save_field() writes to mypatch/rulesmd.ini
5. Server returns updated diff_line.html partial
6. HTMX swaps the cell back to display mode with change indicator
```

Revert follows the reverse path:

```
1. User clicks revert button (×)
2. POST /revert/APOC/Strength
3. revert_field() removes the key from mypatch/rulesmd.ini
4. Server returns empty 200
5. HTMX removes the change indicator
```

## Patch View

The `/patch` page shows all pending changes in a table. The `/patch/export` endpoint generates a downloadable `rulesmd.ini` file:

```python
@bp.route("/patch/export")
def patch_export():
    diff = get_diff(config.patch_dir)
    text = serialise_patch(diff)
    return Response(
        text,
        mimetype="text/plain",
        headers={"Content-Disposition": "attachment; filename=rulesmd.ini"},
    )
```

The exported file is a valid RA2 INI file that can be placed directly into a mod's directory to apply the changes.

## Encoding

All patch reading and writing uses **latin-1** encoding, matching the RA2 INI convention:

```python
patch_file.write_text("\n".join(lines), encoding="latin-1")
```

Latin-1 is a single-byte encoding that preserves all byte values 0x00–0xFF, avoiding corruption of special characters that sometimes appear in modded INI files.
