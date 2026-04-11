# RA2 Modder — Design Spec

**Date:** 2026-04-11  
**Base game:** Mental Omega 3.3 (`C:\Users\timot\Desktop\MentalOmega330Mod`)  
**Stack:** Python 3.11+ · Poetry · Flask · Jinja2 · HTMX · SQLite · Pillow · numpy

---

## 1. Goal

A local Flask web app that lets a modder inspect and edit all game object definitions for Red Alert 2 / Yuri's Revenge (Mental Omega 3.3). The user browses units visually (sprite previews), edits any property through a web form, and exports changes as a clean INI patch file that overrides the base game without touching original MIX archives.

---

## 2. Scope

### Object types covered (all `rules.ini` categories)

| Category | INI section | Notes |
|---|---|---|
| Vehicles | `VehicleTypes` | VXL + HVA rendering |
| Infantry | `InfantryTypes` | SHP rendering |
| Aircraft | `AircraftTypes` | VXL rendering |
| Naval | `VehicleTypes` (amphibious) | VXL rendering |
| Buildings | `BuildingTypes` | SHP rendering |
| Weapons | `WeaponTypes` | No sprite |
| Warheads | `Warheads` | No sprite |
| Projectiles | `Projectiles` | SHP or no sprite |
| Super Weapons | `SuperWeaponTypes` | No sprite |
| Countries | `Countries` | No sprite |
| Houses | `Houses` | No sprite |

### INI tag support

- **Vanilla RA2/YR** — all documented tags
- **Ares extensions** — Shield, AttachEffect, Convert.Type, DigitalDisplay, CloakStages, PassengerTurret, and other Ares-specific tags; stored with tooltips in `ini/ares_schema.py`
- **Phobos** — out of scope (Mental Omega 3.3 does not use Phobos)

---

## 3. Architecture

### Data flow

```
Game Dir (read-only)
  └── *.mix  ──[ra2mix]──► extracted bytes in memory
  └── art.ini (loose)

Parsers
  ├── ini/parser.py       custom RA2 INI reader (duplicate-key safe)
  ├── ini/rules.py        merges: base rulesmd.ini → expandmo*.ini → mypatch/rulesmd.ini
  ├── ini/art.py          merges: art.ini → artmd.ini → mypatch/artmd.ini
  ├── ini/ares_schema.py  Ares tag definitions + tooltips
  └── csf/reader.py       .csf binary → display name strings

Startup indexer (2–5 sec)
  └── db/indexer.py       INI data → SQLite tables (all object types)

Flask request
  ├── routes/             serve unit grids, detail editors, sprite endpoints
  └── render/ (on-demand, cached to .ra2modder/cache/sprites/)
        ├── palette.py    load .pal files, apply remap colour
        ├── shp.py        SHP frames → PNG via Pillow
        └── vxl.py        VXL + HVA → isometric projection via numpy + Pillow
```

### INI merge order (last write wins)

1. `rulesmd.ini` extracted from `ra2md.mix` (base YR rules)
2. `rulesmd.ini` extracted from `expandmo*.mix` files (Mental Omega overrides, in numeric order 94→99)
3. `mypatch/rulesmd.ini` in the game directory (user's patch — applied on top)

Same pattern for `artmd.ini` / `art.ini`.

### SQLite schema

All object properties are stored as a JSON blob alongside indexed lookup columns:

```sql
CREATE TABLE objects (
    id       TEXT PRIMARY KEY,   -- e.g. "HTNK"
    type     TEXT NOT NULL,      -- "VehicleType", "InfantryType", etc.
    name     TEXT,               -- display name from CSF
    side     TEXT,               -- "Allied", "Soviet", "Yuri", ""
    props    JSON NOT NULL        -- full key/value map from merged INI
);

CREATE TABLE patch_changes (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    object_id TEXT NOT NULL,
    key       TEXT NOT NULL,
    old_value TEXT,
    new_value TEXT,
    timestamp TEXT NOT NULL
);
```

---

## 4. UI Design

### Shell

- **Top nav bar:** app title, active game path, unsaved-changes badge
- **Left sidebar:** object type categories (Vehicles, Infantry, Aircraft, Buildings, Naval, Weapons, Warheads, Projectiles, SuperWeapons, Countries, Houses) + Tools section (MIX Assets, Patch Diff)
- **Main area:** context-dependent content (grid or editor)

### Unit/Building grid (list view)

- Cards in a responsive grid; each card shows: cameo icon, unit ID, display name, faction badge
- Filter bar: free-text search, Side dropdown, Type dropdown
- Clicking a card opens the inline detail panel below (HTMX swap — no page reload)

### Detail editor (tabbed form)

All tabs present for every object; tabs with no relevant fields for that type are hidden.

| Tab | Key fields |
|---|---|
| **General** | Name, UIName (CSF key), Owner, TechLevel, Prerequisite, Sight, Strength, Armor, Points, Crushable, Turret, Trainable, Crewed, Crusher, OmniCrusher, IsSelectableCombatant |
| **Combat** | Primary, Secondary, ROT, TurretROT, IsGattling, FireAngle, DeployFire, OpportunisticFighter, ElitePrimary, EliteSecondary |
| **Movement** | Speed, SpeedType, MovementZone, Weight, IsTrain, Naval, Amphibious, Underwater, JumpJetSpeed, Hovering, MoveToShroud |
| **Economics** | Cost, Refund, Soylent, Power, Drain, Storage, OrePurifier, Explodes, SelfHealing, Invulnerable, RadarInvisible, Sensor |
| **Veterancy** | VeteranAbilities, EliteAbilities, VeteranCombat, VeteranSpeed |
| **AI & Logic** | Threat, ThreatPosed, GuardRange, CanPassiveAcquire, Deployer, DeployedActor, Parasiteable, Immune, ImmuneToPoison, ToOverlay, Cloakable, SensorArray, Capturable, Repairable, Unsellable, Adjacent, Factory |
| **Artwork** | Image (art.ini ref), Voxel, Remapable, TurretOffset, ShadowIndex, PrimaryFireFLH, SecondaryFireFLH, Buildup, Foundation, Height |
| **Ares** | Shield.Strength, Shield.Type, Shield.Armor, AttachEffect, Convert.Type, DigitalDisplay, CloakStages, PassengerTurret, and all other Ares tags present in `ares_schema.py` |
| **Raw INI** | Read-only text view of the merged `[SECTION]` block as it will appear in the patch file; copy-to-clipboard button |

**Field input types** are inferred from tag schema:
- Integer / float → `<input type="number">`
- Boolean (yes/no) → toggle switch
- Enum (armor types, speed types, etc.) → `<select>`
- Comma-separated list (e.g. `Prerequisite`) → tag-input widget
- Free text → `<input type="text">`

**Unsaved change indicator:** modified fields are highlighted in amber; a "Save to Patch" button (HTMX POST) writes only the changed keys to `mypatch/rulesmd.ini`; "Revert" restores the base value.

### Sprite preview panel (within detail editor)

- **VXL objects** (vehicles, aircraft): isometric render at 4 facing angles (N, NE, E, SE), rendered on first view and cached; loading spinner while rendering
- **SHP objects** (infantry, buildings): first non-shadow frame of facing 0; palette applied with faction remap colour
- **Cameo icon**: always shown (from `cameo.mix` / `cameomd.mix`)

### MIX Asset browser (`/assets`)

- Tree view of all loaded MIX archives and their contents
- Click a file to preview: INI sections, SHP sprite sheet, raw hex for unknown types
- No editing in this view — read-only inspection

### Patch Diff view (`/patch`)

- Unified diff of `mypatch/rulesmd.ini` vs. base (red/green line colouring)
- Per-change revert buttons
- "Export patch INI" — downloads `mypatch/rulesmd.ini`
- "Copy to game folder" — copies patch files to the game directory

---

## 5. Project Structure

```
ra2-mod/
├── pyproject.toml
├── ra2modder/
│   ├── app.py                  Flask app factory + startup indexer call
│   ├── config.py               Game path, cache dir, patch dir settings
│   ├── mix/
│   │   └── loader.py           ra2mix wrapper; nested MIX resolution; merge order
│   ├── ini/
│   │   ├── parser.py           Custom INI parser (duplicate-key safe)
│   │   ├── rules.py            Load + merge rulesmd chain
│   │   ├── art.py              Load + merge artmd chain
│   │   └── ares_schema.py      Ares tag definitions (name, type, tooltip, default)
│   ├── csf/
│   │   └── reader.py           .csf binary → dict[key → string]
│   ├── db/
│   │   ├── indexer.py          INI data → SQLite (run once at startup)
│   │   └── queries.py          Query helpers (list, get, search, patch CRUD)
│   ├── render/
│   │   ├── palette.py          .pal loader + remap colour application
│   │   ├── shp.py              SHP → PIL Image
│   │   ├── vxl.py              VXL + HVA → isometric PIL Image (numpy)
│   │   └── cache.py            Disk cache: check / save / invalidate
│   ├── patch/
│   │   ├── manager.py          Read/write/diff mypatch/*.ini
│   │   └── writer.py           Serialise changed sections back to INI text
│   └── routes/
│       ├── objects.py          /vehicles, /infantry, /buildings, etc. (shared logic)
│       ├── sprites.py          /sprites/<id>/<type>.png
│       ├── assets.py           /assets MIX browser
│       └── patch.py            /patch diff + export
├── templates/
│   ├── base.html               Nav shell, sidebar, HTMX CDN link
│   ├── partials/
│   │   ├── unit_card.html      Single card (used in grid + HTMX responses)
│   │   ├── detail_tabs.html    Tabbed editor (HTMX target)
│   │   └── diff_line.html      Single diff row
│   └── pages/
│       ├── object_list.html    Card grid page
│       ├── patch.html          Patch diff page
│       └── assets.html         MIX browser page
└── static/
    └── app.css                 Dark theme, grid layout, tab styles
```

---

## 6. Key Technical Notes

### Custom INI parser

Python's `configparser` silently discards duplicate keys (e.g., two `Crawls=` lines in `art.ini`). The custom parser preserves last-write-wins semantics and also handles:
- Keys with no `=` value (treated as `key=`)
- `;` inline comments
- Section continuation across duplicate section headers (RA2 merges them)

### VXL renderer

VXL files store voxels as `(x, y, z, color_index, normal_index)` tuples per column. Rendering pipeline:
1. Parse VXL binary: read section headers, limb data, voxel spans
2. Load HVA: per-frame 4×3 transform matrices for each limb
3. Apply RA2 isometric projection (approx. 30° elevation, SE view)
4. Depth-sort voxels back-to-front
5. Apply palette + simple directional lighting (normal index → brightness multiplier)
6. Composite onto transparent canvas via Pillow
7. Cache result as PNG

### SHP renderer

SHP files store RLE-compressed frames with palette indices. Rendering pipeline:
1. Parse SHP header: frame count, width, height, offsets
2. Decode RLE data → pixel array
3. Map indices through `.pal` palette (256 × RGB)
4. Apply faction remap (indices 80–95 → house colour)
5. Output as RGBA PNG via Pillow

### Startup sequence

```
1. Load config (game path, patch dir)
2. ra2mix: extract ra2md.mix, expandmo*.mix → bytes dict
3. Parse rulesmd.ini chain → merged rules dict
4. Parse artmd.ini chain → merged art dict
5. Parse ra2md.csf → display names
6. Index all objects into SQLite
7. Start Flask dev server
```

---

## 7. Dependencies (pyproject.toml)

```toml
[tool.poetry.dependencies]
python = "^3.11"
flask = "^3.0"
ra2mix = "^1.0"
pillow = "^10.0"
numpy = "^1.26"
```

Dev dependencies: `pytest`, `black`, `ruff`

---

## 8. Out of Scope

- Map editing (use Final Alert 2 / World-Altering Editor)
- Audio editing (.aud/.wav)
- Video playback (.vqa)
- Multiplayer / online features
- Phobos extension tags
- Writing back to MIX archives (patch files only)
