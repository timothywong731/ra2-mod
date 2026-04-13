# INI System & Merge Chain

This page documents how RA2 Modder parses INI files and merges multiple sources into the final game data that populates the object browser.

## INI Format

RA2/YR uses a custom INI dialect with several quirks compared to standard Windows INI:

```ini
; This is a full-line comment
[SectionName]
Key=Value
AnotherKey=Some value with spaces
Flag=yes
List=Item1,Item2,Item3
NumberedList=5
Empty=               ; Key with empty value
KeyWithComment=200   ; inline comment after space-semicolon
```

### Quirks handled by the parser

| Quirk | Example | Behaviour |
|---|---|---|
| Duplicate sections | Two `[HTNK]` blocks | Merged — keys from both are combined |
| Duplicate keys | `Cost=1750` then `Cost=2000` | Last write wins — `Cost=2000` |
| Keys without values | `Voxel` (no `=`) | Stored with empty string value |
| Inline comments | `Cost=1750 ; expensive` | Stripped at ` ;` boundary |
| Values with `=` | `Versus=100%,80%,60%` | Only first `=` splits key from value |
| Latin-1 encoding | Extended characters in strings | Files decoded as `latin-1` |

### Parser implementation

The parser in `ra2modder/ini/parser.py` is a single-pass line-by-line processor:

```python
def parse_ini(text: str) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    current: str | None = None

    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith(";"):
            continue

        if line.startswith("[") and "]" in line:
            current = line[1 : line.index("]")].strip()
            result.setdefault(current, {})
            continue

        if current is None:
            continue

        # Strip inline comment
        ci = line.find(" ;")
        if ci >= 0:
            line = line[:ci].strip()

        if "=" in line:
            key, _, value = line.partition("=")
            result[current][key.strip()] = value.strip()
        else:
            result[current][line] = ""

    return result
```

Key design choices:

- **`str.partition("=")`** — splits on the first `=` only, so values containing `=` are preserved intact
- **`line.find(" ;")`** — requires a space before the semicolon to avoid stripping values like `Weapon=120mm;HEAT` (semicolons without a preceding space are part of the value)
- **`result.setdefault(current, {})`** — duplicate sections are merged rather than overwritten

### Return type

The parser returns a nested dictionary:

```python
{
    "VehicleTypes": {"0": "HTNK", "1": "MTNK", "2": "SREF"},
    "HTNK": {"Name": "Name:HTNK", "Cost": "1750", "Strength": "800"},
    "MTNK": {"Name": "Name:MTNK", "Cost": "900", "Strength": "400"},
}
```

All values are strings. The consuming code (`indexer.py`, route handlers) converts to integers or other types as needed.

## Merge Chain

RA2/YR's data is spread across multiple INI files that layer on top of each other. RA2 Modder reproduces this merge order exactly.

### Rules merge order

```
1.  rules.ini       ← Base RA2 rules (inside ra2.mix → local.mix)
2.  rulesmd.ini      ← Yuri's Revenge override (inside ra2md.mix → localmd.mix)
3.  rulesmo*.ini     ← Mod expansion rules (sorted alphabetically)
4.  mypatch/rulesmd.ini  ← User patch (highest priority)
```

### Art merge order

```
1.  art.ini          ← Base RA2 art (inside ra2.mix → local.mix)
2.  artmd.ini        ← Yuri's Revenge override (inside ra2md.mix → localmd.mix)
3.  artmo*.ini       ← Mod expansion art (sorted alphabetically)
4.  mypatch/artmd.ini    ← User patch (highest priority)
```

### Merge semantics

The merge operation is **section-level deep merge with key-level overwrite**:

```python
def _merge(base: dict, override: dict) -> None:
    for section, keys in override.items():
        base.setdefault(section, {}).update(keys)
```

This means:

- A new section in a later file **adds** to the merged result
- A section that already exists is **not replaced** — its keys are merged
- A key that already exists within a section **is overwritten** by the later value
- Keys from the base that are not present in the override **are preserved**

### Example

Base `rules.ini`:
```ini
[HTNK]
Cost=1500
Strength=800
Armor=heavy
```

Override `rulesmd.ini`:
```ini
[HTNK]
Cost=1750
TechLevel=10
```

Merged result:
```ini
[HTNK]
Cost=1750        ; overwritten by rulesmd.ini
Strength=800     ; preserved from rules.ini
Armor=heavy      ; preserved from rules.ini
TechLevel=10     ; added by rulesmd.ini
```

## Ares `[#include]` Directive

The [Ares](https://ares.strategy-x.com/) engine extension adds a special `[#include]` section that instructs the parser to include other INI files inline:

```ini
[#include]
0=extra_units.ini
1=balance_changes.ini
```

RA2 Modder resolves these **recursively** during the merge step. The `_resolve_includes()` function:

1. Pops the `[#include]` section from the parsed data
2. Sorts entries by index (0, 1, 2, …)
3. For each referenced filename, looks it up in the extracted game files
4. Parses the referenced file and recursively resolves its own includes
5. Merges the included data into the current parsed result

```python
def _resolve_includes(parsed, game_files):
    includes = parsed.pop("#include", None)
    if not includes:
        return
    for _idx, filename in sorted(includes.items()):
        data = game_files.get(filename.lower())
        if data:
            included = parse_ini(data.decode("latin-1", errors="replace"))
            _resolve_includes(included, game_files)  # recursive
            _merge(parsed, included)
```

This is critical for large mods like Mental Omega, which split their rules across dozens of included files.

## Mod expansion discovery

Mod INI files are auto-discovered by filename pattern:

| Pattern | Purpose |
|---|---|
| `rulesmo*.ini` | Mod rules extensions |
| `artmo*.ini` | Mod art extensions |

Files matching these patterns are sorted alphabetically and merged in order. This matches the convention used by Ares and Phobos mods where files like `rulesmo01.ini`, `rulesmo02.ini` are loaded sequentially.

## Case sensitivity

RA2's INI system is **case-insensitive** for filenames but **preserves case** for section and key names. RA2 Modder handles this with case-insensitive file lookups:

```python
lower = {k.lower(): v for k, v in game_files.items()}
data = lower.get("rulesmd.ini")
```

Section and key names are stored as-is from the INI file. Lookups that need case-insensitive matching (like the `Image=` key resolution) check both original and lowered forms:

```python
art_section = art.get(image_key, art.get(image_key.lower(),
              art.get(obj_id, art.get(obj_id.lower(), {}))))
```

## Registry sections

Certain INI sections serve as **registries** that list all objects of a given type:

```ini
[VehicleTypes]
0=HTNK
1=MTNK
2=SREF
```

The indexer reads these registries to discover which objects exist. Each index number maps to an object ID, and the object's own section contains its properties:

```ini
[HTNK]
Name=Name:HTNK
Cost=1750
```

Registry sections indexed by RA2 Modder:

| Registry | Object category |
|---|---|
| `VehicleTypes` | Ground vehicles |
| `InfantryTypes` | Infantry units |
| `AircraftTypes` | Aircraft |
| `BuildingTypes` | Structures |
| `WeaponTypes` | Weapon definitions |
| `Warheads` | Damage types |
| `Projectiles` | Projectile behaviour |
| `SuperWeaponTypes` | Superweapons |

Objects not listed in a registry section are ignored — even if they have a full `[SECTION]` in the INI file.
