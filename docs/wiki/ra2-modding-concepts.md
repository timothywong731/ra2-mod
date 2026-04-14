# RA2 Modding Concepts

This page covers the fundamental concepts of Red Alert 2 / Yuri's Revenge modding that RA2 Modder is built around. Understanding these concepts is essential for working with the codebase.

## Game Data Architecture

RA2/YR stores its game data in a layered system of archives and configuration files:

```
Game Directory
├── ra2.mix          Base RA2 archive
├── ra2md.mix        Yuri's Revenge override archive
├── langmd.mix       Localized strings and UI assets
├── expandmd01.mix   Official expansion patches
├── expandmo94.mix   }
├── expandmo97.mix   } Mod-specific archives (e.g. Mental Omega)
├── expandmo99.mix   }
├── rulesmd.ini      (loose) User/mod override for rules
├── artmd.ini        (loose) User/mod override for art
└── mypatch/
    └── rulesmd.ini  User's mod patch (RA2 Modder output)
```

### MIX Archives

MIX files are Westwood's proprietary archive format. They contain hundreds of game assets — INI files, sprites (SHP), voxel models (VXL), palettes (PAL), string tables (CSF), and more.

Key characteristics:
- **Flat structure** — no directories inside a MIX file
- **Hashed filenames** — files are identified by a CRC32 hash of their name
- **Nested archives** — a MIX can contain other MIX files (e.g. `local.mix` inside `ra2md.mix`)
- **Override order** — later MIX files in the load order override earlier ones for the same filename

The app uses the `ra2mix` library to extract MIX contents at startup. It handles nested MIX resolution automatically.

### Load Order

The order in which files are loaded determines which version of a key "wins" when there are conflicts:

```
1. ra2.mix          (base RA2 data)
2. ra2md.mix        (Yuri's Revenge overrides)
3. langmd.mix       (localized strings)
4. expandmd*.mix    (expansion patches, sorted alphabetically)
5. expandmo*.mix    (mod archives, sorted alphabetically)
6. Loose .ini files (in game directory — highest priority)
7. mypatch/*.ini    (user patch — applied last)
```

Each layer can add new sections, add new keys to existing sections, or overwrite key values from previous layers.

## INI File System

RA2/YR uses INI files as its primary configuration format. Two files control nearly all game behaviour:

### rules.ini / rulesmd.ini

Defines **all game objects and their properties**. This is the "rules" of the game — what units cost, how fast they move, what weapons they fire.

```ini
[VehicleTypes]
0=HTNK
1=MTNK
2=SREF

[HTNK]
Name=Name:HTNK
UIName=Name:HTNK
Cost=1750
Strength=800
Armor=heavy
Speed=4
Primary=120mm
Secondary=FlakGuy
Image=HTNK
Owner=Russians
TechLevel=10
```

#### Registry sections

The INI contains **registry sections** that list all objects of a given type:

| Section | Contains |
|---|---|
| `VehicleTypes` | All ground vehicles (tanks, APCs, MCVs) |
| `InfantryTypes` | All infantry units (GIs, engineers, dogs) |
| `AircraftTypes` | All aircraft (helicopters, jets, missiles) |
| `BuildingTypes` | All structures (power plants, barracks) |
| `WeaponTypes` | Weapon definitions |
| `Warheads` | Damage type definitions |
| `Projectiles` | Projectile behaviour |
| `SuperWeaponTypes` | Superweapons (nukes, weather storms) |

Each entry in a registry is `index=OBJECT_ID`, and the object's own section `[OBJECT_ID]` contains all its properties.

#### Key properties

| Property | Type | Example | Description |
|---|---|---|---|
| `Name` | CSF key | `Name:HTNK` | Localized display name |
| `Cost` | integer | `1750` | Build cost |
| `Strength` | integer | `800` | Hit points |
| `Armor` | enum | `heavy` | Armor class |
| `Speed` | integer | `4` | Movement speed |
| `Primary` | weapon ID | `120mm` | Primary weapon |
| `Owner` | CSV | `Russians,Libyans` | Which countries can build this |
| `TechLevel` | integer | `10` | Tech tree requirement (-1 = unbuildable) |
| `Image` | art ID | `MTNK` | Redirects to a different art section |
| `Prerequisite` | CSV | `NAWEAP,NARADR` | Buildings needed before unlocking |

### art.ini / artmd.ini

Defines **how objects look**. Controls sprite filenames, animation sequences, VXL model references, remapping, and cameo icons.

```ini
[HTNK]
Voxel=yes
Remapable=yes
TurretOffset=0,0,-20
PrimaryFireFLH=200,0,200

[GI]
Sequence=GISequence
Cameo=GIICON

[GISequence]
Ready=0,1,1
Walk=8,6,6
FireUp=164,6,6
Die1=134,15,0
```

Key art concepts:

| Key | Purpose |
|---|---|
| `Voxel=yes` | Object uses VXL 3D model instead of SHP sprites |
| `Sequence=` | Points to an infantry animation sequence section |
| `Cameo=` | Points to cameo icon SHP name |
| `CameoPCX=` | (Ares) Points to PCX cameo icon |
| `DeployedImage=` | Alternate art section for deployed state |
| `Image=` | Redirects to a shared art definition |

### The Image= Key

One of the most important concepts in RA2 modding. The `Image=` key in a **rules** section redirects the engine to use a different object's **art** section for all visual data.

Example: The Apocalypse Tank (`APOC`) uses `Image=MTNK`, so its VXL files are named `mtnk.vxl`, `mtnktur.vxl`, `mtnkbarl.vxl` — not `apoc.vxl`.

```
rules[APOC].Image = MTNK
    → look up art[MTNK] for visual properties
    → look for mtnk.vxl, mtnkbarl.vxl, mtnktur.vxl
```

The resolution chain in RA2 Modder:

```python
rules_section = rules.get(obj_id)          # e.g. rules["APOC"]
image_key = rules_section.get("Image", obj_id)  # "MTNK" (or "APOC" if no Image key)
art_section = art.get(image_key)           # art["MTNK"]
vxl_base = image_key.lower()              # "mtnk"
# → mtnk.vxl, mtnktur.vxl, mtnkbarl.vxl
```

## Object Types

### Vehicles (VehicleTypes)

Ground vehicles use **VXL voxel models** for 3D appearance. A vehicle typically consists of:

- **Body** — `<image>.vxl` — the main hull
- **Turret** — `<image>tur.vxl` — a rotating turret (optional)
- **Barrel** — `<image>barl.vxl` — a gun barrel on the turret (optional)

Each VXL file has a companion `.hva` (Hierarchy Voxel Animation) file that stores transform matrices for animation frames.

Vehicles also have a **cameo icon** (the small build queue image) stored as an SHP or PCX file.

### Infantry (InfantryTypes)

Infantry use **SHP sprite sheets** with multiple frames for different animations and facings. A typical infantry SHP contains hundreds of frames organized by animation **sequences**.

A sequence definition in the art INI:

```ini
[GISequence]
Ready=0,1,1
Walk=8,6,6
FireUp=164,6,6
Prone=86,1,6
Crawl=86,6,6
Die1=134,15,0
Idle1=56,15,0,S
```

Format: `Action=StartFrame,FrameCount,FacingCount[,Flags]`

- **StartFrame** — first frame index in the SHP
- **FrameCount** — frames per facing per animation cycle
- **FacingCount** — number of facings (1, 6, or 8); determines total frames
- For 8 facings: total frames = FrameCount × 8, starting at StartFrame

RA2 Modder renders the **Ready** (standing) frame for each facing when showing the compass preview grid.

### Aircraft (AircraftTypes)

Aircraft use VXL models like vehicles but typically without turrets. They include jets (BPLN), helicopters (APACHE), and special projectile units (V3ROCKET).

### Buildings (BuildingTypes)

Buildings use **SHP sprites** rendered in isometric view. A standard RA2/YR building SHP has **6 frames** with a fixed layout:

| Frame | Content |
|---|---|
| 0 | Undamaged building |
| 1 | Damaged building |
| 2 | Rubble/destroyed |
| 3 | Shadow (undamaged) |
| 4 | Shadow (damaged) |
| 5 | Shadow (rubble) |

Frame 0 is the undamaged building, frame 1 is damaged. Frames 3–5 are shadow overlays (dark palette indices, not useful for previews).

Buildings typically use `unittem.pal` (the same as vehicles and infantry). Objects with `TerrainPalette=yes` in their art section use `isotem.pal` instead.

Some special buildings use VXL models (e.g. Yuri's Gatling Cannon, `YAGGUN`).

#### NewTheater System

Buildings with `NewTheater=yes` in art.ini use theater-specific SHP files. The 2nd character of the filename changes per theater:

| Theater | Suffix letter | Example |
|---|---|---|
| Temperate | G | `naweap` → `ngweap.shp` |
| Snow | A | `naweap` → `naweap.shp` (2nd char already `a`) |
| Urban | U | `naweap` → `nuweap.shp` |
| New Urban | N | `naweap` → `nnweap.shp` |
| Lunar | L | `naweap` → `nlweap.shp` |
| Desert | D | `naweap` → `ndweap.shp` |

Vanilla RA2/YR only ships Temperate and Snow variants. RA2 Modder shows radio buttons for available theaters.

See: [ModEnc — NewTheater](https://modenc.renegadeprojects.com/NewTheater)

#### Building Animation System

Buildings can have separate SHP files for animations, composited on top of the base building frame. Animation SHPs share the same `FullWidth × FullHeight` coordinate space as the building SHP, so they are composited at position (0, 0):

| Art key | Purpose | Max count |
|---|---|---|
| `ActiveAnim` | Active/powered state (e.g. lightning bolts on power plant) | 4 |
| `IdleAnim` | Idle state animation | 1 |
| `SuperAnim` | Superweapon charging animation | 4 |
| `SpecialAnim` | Special mode animation (e.g. refinery/grinder) | 4 |
| `ProductionAnim` | Unit production animation | 1 |
| `Buildup` | Construction animation | 1 |

Building animations use the **same palette as the building** (`unittem.pal` or `isotem.pal`), not `anim.pal`.

See: [ModEnc — ActiveAnim](https://modenc.renegadeprojects.com/ActiveAnim) · [ModEnc — BuildingTypes](https://modenc.renegadeprojects.com/BuildingTypes)

#### Prerequisite System

Buildings (and other objects) declare prerequisites via the `Prerequisite=` key — a CSV list of object IDs that must be built first:

```ini
[NATECH]
Prerequisite=NAWEAP,NARADR
```

This forms a **tech tree**: Construction Yard → War Factory + Radar → Battle Lab → advanced units. RA2 Modder visualizes this tree showing both what an object requires (upstream) and what it unlocks (downstream).

### Non-visual types

Weapons, Warheads, Projectiles, and SuperWeapons have no sprite — they're pure data definitions. They appear in the browser with faction-colored placeholder icons.

## Faction System

RA2 organizes factions through two INI constructs:

### Countries

```ini
[Countries]
0=Americans
1=Russians
2=Libyans

[Americans]
Side=Allied

[Russians]
Side=Soviet
```

### Sides

Countries belong to **sides** (Allied, Soviet, Yuri/ThirdSide). The side determines team colouring, unit access, and AI behaviour.

The `Owner=` key on an object lists which countries can build it:

```ini
[HTNK]
Owner=Russians,Libyans,Cubans,Iraqis
```

RA2 Modder resolves the Owner list through the Countries→Sides mapping to determine a displayable faction label (e.g. "Soviet", "Allied,Soviet" for shared units).

## Palette System

RA2 uses indexed-color images with 256-color palettes stored as `.pal` files.

### PAL format

- 768 bytes: 256 RGB triplets
- Each channel is **6-bit** (0–63), not 8-bit
- Conversion: `8bit = min(6bit × 4, 255)`
- Index 0 is **always transparent** by convention

### Key palettes

| Palette | Used for |
|---|---|
| `unittem.pal` / `unit.pal` | Vehicles, infantry, and most buildings |
| `cameo.pal` | Build queue icons |
| `isotem.pal` / `temperat.pal` | Objects with `TerrainPalette=yes` (terrain overlays) |
| `anim.pal` | Building animation overlays |

### Faction remapping

Palette indices 16–31 are reserved for **remap colours** — these change to match the player's team colour. The same unit sprite looks red for Soviet and blue for Allied by remapping these indices.

## CSF String Localization

Display names (e.g. "Apocalypse Tank") are stored in CSF (C&C String File) binary archives, not in INI files. The INI stores a reference key:

```ini
[HTNK]
Name=Name:HTNK   ; ← reference to CSF label
```

The CSF file contains the actual string:

```
Label "Name:HTNK" → "Apocalypse Tank"
Label "Name:MTNK" → "Rhino Heavy Tank"
```

CSF uses UTF-16LE encoding with each byte bitwise inverted (`~byte & 0xFF`).

## Mod Extensions

### Ares

[Ares](https://ares.strategy-x.com/) is a popular RA2/YR engine extension DLL that adds new INI tags and gameplay features. Examples:

- `Shield.Strength=` — gives units energy shields
- `CloakStages=` — configurable cloaking phases
- `PassengerTurret=` — passengers control individual turrets
- `[#include]` — include other INI files

RA2 Modder detects Ares by the presence of `ares.dll` in the game directory and loads the Ares tag schema for display in the editor.

### Phobos

[Phobos](https://phobos.readthedocs.io/) is a newer extension building on Ares, adding features like:

- Custom shields with more options
- LaserTrail= for projectile effects
- More detailed veterancy control

RA2 Modder detects Phobos via `phobos.dll` and enables Phobos-specific editor tabs.

### Ares `[#include]` Directive

Ares adds a special `[#include]` section that instructs the INI parser to include other INI files:

```ini
[#include]
0=extra_rules.ini
1=more_units.ini
```

RA2 Modder resolves these recursively during the INI merge step, looking up the referenced filenames in the extracted game files.

## The VXL Voxel Format

VXL is Westwood's voxel model format used for 3D objects (tanks, aircraft, ships). Technical details are covered in the [Rendering Pipeline](rendering-pipeline.md) page, but key concepts:

- Voxels are stored per-column (X×Y grid), with Z spans describing vertical runs of coloured blocks
- Each voxel has a **colour index** (into the PAL palette) and a **normal index** (for lighting)
- Models can have multiple **limbs** (body sections), each with their own origin and transform
- **VXL naming convention**: `<name>.vxl` (body), `<name>tur.vxl` (turret), `<name>barl.vxl` (barrel), `<name>d.vxl` (deployed)

## The SHP Sprite Format

SHP (SHaPe) is Westwood's 2D sprite format used for infantry, buildings, and UI elements. The TS/RA2 variant uses:

- Per-frame info table with position offsets and flags
- **RLE-Zero** compression (run-length encoding for transparent pixels)
- Indexed colour using PAL palette
- Hundreds of frames per file (infantry can have 600+ frames for all animations and facings)

## Facing System

RA2 uses an 8-direction facing system with clockwise numbering:

```
    7  0  1
     ╲ │ ╱
  6 ── ╳ ── 2
     ╱ │ ╲
    5  4  3
```

| Index | Direction | Degrees |
|---|---|---|
| 0 | North | 0° |
| 1 | NE | 45° |
| 2 | East | 90° |
| 3 | SE | 135° |
| 4 | South | 180° |
| 5 | SW | 225° |
| 6 | West | 270° |
| 7 | NW | 315° |

The default game view uses facing **4 (South)** — the standard isometric perspective where the camera looks down from the south.

Infantry SHP files store frames in this facing order, so frame `start + facing × count` gives the correct directional sprite.

VXL models are rotated mathematically to achieve the desired facing.
