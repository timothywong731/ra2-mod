# Architecture Overview

This document describes the high-level architecture, design patterns, and data flow of RA2 Modder.

## Design Principles

1. **Non-destructive** — The app never writes to original game files. All edits produce patch INI files that layer on top of the base data.
2. **Fail gracefully** — Every parser and renderer returns default/placeholder data on error instead of raising exceptions. A corrupt MIX archive won't crash the app; it will be silently skipped.
3. **Startup-heavy, request-light** — Expensive operations (MIX extraction, INI merging, indexing) happen once at startup. Request handlers do lightweight DB queries and on-demand sprite rendering.
4. **Last-write-wins** — INI keys merge by overwriting. Later files in the merge chain take precedence, matching how the RA2 engine resolves conflicts.

## Application Lifecycle

```
Game Directory (read-only)
    │
    ▼
┌──────────────────────────────────────┐
│  STARTUP (2–5 seconds)               │
│                                      │
│  1. Config detection                 │
│     detect_mod_type() → DLL check    │
│     _mix_order_for() → load list     │
│                                      │
│  2. MIX extraction                   │
│     load_game_files(config)          │
│     ├── ra2mix.read(filepath)        │
│     ├── nested .mix resolution       │
│     └── loose file pickup            │
│     → dict[str, bytes]              │
│                                      │
│  3. INI merge chain                  │
│     load_rules(game_files, patch)    │
│     load_art(game_files, patch)      │
│     → dict[section → dict[key→val]] │
│                                      │
│  4. String localization              │
│     parse_csf(data) for each .csf    │
│     → dict["Name:HTNK" → "Apoc..."]│
│                                      │
│  5. SQLite indexing                   │
│     build_index(rules, art, strings) │
│     → in-memory sqlite3.Connection   │
│                                      │
│  6. Blueprint registration           │
│     objects, sprites, assets, patch   │
└──────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────┐
│  REQUEST HANDLING                    │
│                                      │
│  GET /VehicleTypes                   │
│    → list_objects(db, "VehicleTypes")│
│    → render template with cards      │
│                                      │
│  GET /VehicleTypes/HTNK  (HTMX)     │
│    → get_object(db, "HTNK")         │
│    → get_vxl_modes(...)             │
│    → render detail_tabs partial      │
│                                      │
│  GET /sprites/HTNK/vxl.png          │
│    → render_vxl(data, pal, facing)  │
│    → send PNG bytes                  │
│                                      │
│  POST /edit/HTNK/Cost               │
│    → save_field(patch_dir, ...)     │
│    → render diff_line partial        │
└──────────────────────────────────────┘
```

## Flask App Factory

The application uses the **app factory pattern** in `app.py`. The `create_app(game_dir)` function:

1. Creates the Flask instance with configured template and static directories
2. Runs the full startup sequence (config → MIX → INI → CSF → SQLite)
3. Stores all startup data on `app.config` for thread-safe access
4. Registers all four route blueprints

```python
def create_app(game_dir: str) -> Flask:
    config = default_config(game_dir)
    game_files = load_game_files(config)
    rules = load_rules(game_files, config.patch_dir)
    art = load_art(game_files, config.patch_dir)
    # ... index, register blueprints
    return app
```

This means the app can be instantiated multiple times (e.g. for testing) with different game directories, and all state is encapsulated within the Flask app object.

### Config stored on `app.config`

| Key | Type | Description |
|---|---|---|
| `DB` | `sqlite3.Connection` | In-memory SQLite database |
| `GAME_CONFIG` | `GameConfig` | Paths, mod type, MIX order |
| `GAME_FILES` | `dict[str, bytes]` | All extracted game files |
| `RULES` | `dict[str, dict]` | Merged rules INI data |
| `ART` | `dict[str, dict]` | Merged art INI data |
| `STRINGS` | `dict[str, str]` | CSF localization strings |

## Blueprint Architecture

Routes are organized into four Flask Blueprints:

| Blueprint | Mount | Purpose |
|---|---|---|
| `objects` | `/` | Object browser, detail, inline editor, reindex |
| `sprites` | `/sprites/` | Cameo icons, VXL renders, SHP previews |
| `assets` | `/assets` | MIX file browser |
| `patch_view` | `/patch` | Patch diff and export |

Each blueprint is a standalone module in `ra2modder/routes/` with its own URL prefix and helper functions.

## HTMX Integration Pattern

The app uses [HTMX](https://htmx.org/) for seamless partial page updates without client-side JavaScript frameworks:

### Dual-response pattern

Every route that serves both full pages and HTMX partials uses a header check:

```python
if request.headers.get("HX-Request"):
    return render_template("partials/detail_tabs.html", ...)
else:
    return render_template("pages/object_list.html", ...)
```

This means:
- **Direct navigation** (bookmark, refresh) → full HTML page with layout
- **HTMX request** (click, search) → just the changed partial, swapped into the DOM

### Key HTMX patterns used

| Pattern | Where | How |
|---|---|---|
| Click-to-load detail | Card grid | `hx-get="/VehicleTypes/HTNK"` → swaps into `#detail-panel` |
| Live search | Toolbar | `hx-get` with `hx-trigger="keyup changed delay:300ms"` |
| Filter chips | Faction buttons | Radio buttons with `hx-get` on change |
| Inline editing | Property table | `<input hx-post="/edit/HTNK/Cost" hx-trigger="change">` |
| Confirm dialog | Reindex button | `hx-confirm="Purge index and rebuild?"` |
| Loading indicator | Reindex button | `hx-indicator=".reindex-spinner"` |
| Redirect after POST | Reindex response | `HX-Redirect: /` header |

### Template hierarchy

```
base.html                 ← Shell: sidebar nav + main area + HTMX script
├── pages/
│   ├── object_list.html  ← Full page: toolbar + card grid + detail panel
│   ├── assets.html       ← Asset browser
│   └── patch.html        ← Patch diff view
└── partials/
    ├── unit_cards.html   ← Card grid (HTMX swap target for search/filter)
    ├── unit_card.html    ← Single card (included in grid)
    ├── detail_tabs.html  ← Tabbed editor + VXL compass (HTMX swap target)
    └── diff_line.html    ← Inline diff after field edit
```

## Error-Handling Philosophy

The codebase follows a **"return defaults, never crash"** pattern across all layers:

| Layer | Error Strategy |
|---|---|
| MIX loading | Missing/corrupt archives silently skipped |
| INI parsing | Malformed lines skipped; partial parse returned |
| CSF decoding | Truncated data returns partial dict |
| SHP rendering | Bad data → 48×48 transparent placeholder |
| VXL rendering | Bad data → 128×128 transparent placeholder |
| Database queries | Missing object → `None` |
| Routes | Missing sprite → faction-coloured placeholder PNG |
| Patch system | Missing patch file → empty dict |

This ensures the user always sees *something* — even if some game data is corrupt or missing, the rest of the app continues to function.

## Concurrency Model

- **Single writer** — The SQLite database is populated once at startup. Request handlers only read.
- **Thread safety** — `check_same_thread=False` allows Flask's threaded request handling to query the DB safely.
- **No journaling** — `PRAGMA journal_mode=OFF` disables WAL since the DB is in-memory and read-only after startup.
- **Reindex** — The `POST /reindex` route is the only write operation after startup. It closes the old connection and builds a new one atomically.

## Module Dependency Graph

```
__main__.py
    └── app.py (create_app)
            ├── config.py (default_config, detect_mod_type)
            ├── mix/loader.py (load_game_files)
            │       └── ra2mix (external)
            ├── ini/parser.py (parse_ini)
            ├── ini/rules.py (load_rules)
            │       └── ini/parser.py
            ├── ini/art.py (load_art)
            │       └── ini/parser.py
            ├── csf/reader.py (parse_csf)
            ├── db/indexer.py (build_index)
            │       └── db/queries.py
            └── routes/
                    ├── objects.py
                    │       ├── db/queries.py
                    │       └── routes/sprites.py (get_vxl_modes)
                    ├── sprites.py
                    │       ├── render/vxl.py
                    │       ├── render/shp.py
                    │       └── render/palette.py
                    ├── assets.py
                    └── patch_view.py
                            └── patch/manager.py
```
