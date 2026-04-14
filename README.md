# RA2 Modder

A local web application for inspecting and editing **Red Alert 2 / Yuri's Revenge** game object definitions. Browse units visually with sprite previews, edit any property through a web form, and export changes as a clean INI patch file — without touching original MIX archives.

Supports vanilla RA2/YR, Ares mods (e.g. Mental Omega 3.3), and Phobos mods.

## Features

- **Visual browser** — Card grid with cameo icons, faction badges, and live search
- **3D voxel preview** — Isometric VXL renders from all 8 compass directions with turret/barrel composite overlay
- **Infantry & building preview** — SHP sprite rendering with facing-based compass grid for infantry and isometric preview for structures
- **Building animations** — Animated GIF overlays for ActiveAnim, IdleAnim, SuperAnim, SpecialAnim, ProductionAnim, and Buildup
- **Theater support** — NewTheater-aware SHP filename resolution with radio buttons to switch between available theater variants (temperate/snow)
- **Damaged state preview** — Building frame 1 shows the correct damaged state (distinct from shadow frames 3–5)
- **Prerequisite tech tree** — Interactive tree visualization showing what each object requires and what it unlocks, with type filters
- **Inline property editor** — Edit any INI key directly; changes are highlighted and tracked
- **Non-destructive patching** — All edits write to `mypatch/rulesmd.ini`, leaving originals intact
- **Patch diff view** — Review pending changes, revert individual fields, export as downloadable INI
- **MIX asset browser** — Inspect all files extracted from game archives grouped by extension
- **Auto-detection** — Detects mod type (vanilla/Ares/Phobos) from DLL presence and adjusts MIX load order
- **Reindex** — Purge and rebuild the database on demand

## Requirements

- Python 3.11+
- A Red Alert 2 / Yuri's Revenge game installation (with MIX archives)

## Installation

```bash
git clone https://github.com/user/ra2-mod.git
cd ra2-mod
poetry install
```

## Usage

```bash
# Point to your game directory
poetry run python -m ra2modder --game-dir "C:\Games\RA2"

# Custom port
poetry run python -m ra2modder --game-dir "C:\Games\RA2" --port 5001
```

Open `http://127.0.0.1:5000` in your browser.

### Command-line options

| Flag | Default | Description |
|---|---|---|
| `--game-dir` | *(required)* | Path to RA2/YR game installation |
| `--port` | `5000` | Port for the local Flask server |

## Project Structure

```
ra2-mod/
├── ra2modder/
│   ├── __main__.py          CLI entry point
│   ├── app.py               Flask app factory
│   ├── config.py            GameConfig dataclass, mod-type detection
│   ├── mix/loader.py        MIX archive extraction (via ra2mix)
│   ├── ini/
│   │   ├── parser.py        Custom RA2 INI parser
│   │   ├── rules.py         Rules INI merge chain
│   │   ├── art.py           Art INI merge chain
│   │   ├── ares_schema.py   Ares extension tag definitions
│   │   └── phobos_schema.py Phobos extension tag definitions
│   ├── csf/reader.py        CSF binary string localization
│   ├── db/
│   │   ├── indexer.py       SQLite in-memory index builder
│   │   └── queries.py       Query helpers (list, get, search)
│   ├── render/
│   │   ├── palette.py       6-bit PAL file loader
│   │   ├── shp.py           SHP sprite renderer (RLE-Zero)
│   │   ├── vxl.py           VXL voxel renderer (isometric projection)
│   │   └── cache.py         Disk-based sprite cache
│   ├── patch/
│   │   ├── manager.py       Read/write/revert patch fields
│   │   └── writer.py        Serialize patch to INI text
│   └── routes/
│       ├── objects.py       Object browser, detail, inline editor
│       ├── sprites.py       Cameo, VXL, SHP sprite endpoints
│       ├── assets.py        MIX asset browser
│       └── patch_view.py    Patch diff view and export
├── templates/               Jinja2 templates (base + partials + pages)
├── static/app.css           Dark theme CSS
├── tests/                   119 pytest tests
└── docs/                    Design specs and wiki
```

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11, Flask 3.0, SQLite (in-memory) |
| Frontend | Jinja2, HTMX 1.9.12, vanilla CSS |
| Rendering | Pillow 12+, numpy 2.4+ |
| MIX archives | ra2mix 1.0 |
| Package manager | Poetry |
| Testing | pytest |

## How It Works

1. **Startup** — MIX archives are extracted, INI files merged in the correct override order, CSF strings decoded, and all objects indexed into an in-memory SQLite database (2–5 seconds).

2. **Browse** — A card grid displays all objects of the selected type with cameo icons, faction badges, and metadata. Live search, side filtering, and tech-level filtering reduce results instantly via HTMX partial swaps.

3. **Preview** — Clicking an object reveals an 8-direction compass grid rendered from VXL voxel models (vehicles/aircraft) or SHP sprites (infantry/buildings). Vehicles with turrets show composite overlays.

4. **Edit** — Every INI property is an editable field. Changes are saved to `mypatch/rulesmd.ini` on blur, with visual diff indicators showing old vs. new values.

5. **Export** — The Patch view shows all pending changes as formatted INI. Download the patch file and drop it into your game directory.

## Running Tests

```bash
poetry run pytest
```

## Documentation

Extended documentation lives in [`docs/wiki/`](docs/wiki/):

- [Architecture Overview](docs/wiki/architecture.md)
- [RA2 Modding Concepts](docs/wiki/ra2-modding-concepts.md)
- [INI System & Merge Chain](docs/wiki/ini-system.md)
- [Rendering Pipeline](docs/wiki/rendering-pipeline.md)
- [Patch System](docs/wiki/patch-system.md)
- [Database & Indexing](docs/wiki/database-indexing.md)
- [API Routes & HTMX](docs/wiki/api-routes.md)

## External References

- [ModEnc — BuildingTypes](https://modenc.renegadeprojects.com/BuildingTypes) — Complete list of building INI flags
- [ModEnc — ActiveAnim](https://modenc.renegadeprojects.com/ActiveAnim) — Building animation overlay system
- [ModEnc — NewTheater](https://modenc.renegadeprojects.com/NewTheater) — Theater-specific SHP filename resolution
- [ModEnc — Art.ini](https://modenc.renegadeprojects.com/Art.ini) — Art INI documentation

## License

MIT
