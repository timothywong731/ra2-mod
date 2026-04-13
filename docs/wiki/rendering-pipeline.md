# Rendering Pipeline

This page documents how RA2 Modder renders visual previews for game objects — VXL voxel models, SHP sprites, and cameo icons.

## Overview

The rendering pipeline serves PNG images on demand via the `/sprites/<obj_id>/vxl.png` route. Each request:

1. Resolves the object's `Image=` key to find the correct asset filename
2. Loads the raw binary data from the extracted game files
3. Parses the binary format (VXL or SHP)
4. Renders to a PIL RGBA Image
5. Serializes to PNG and returns it as an HTTP response

```
Request: GET /sprites/APOC/vxl.png?facing=2&mode=composite
    │
    ├─ _resolve_image_key("APOC") → "MTNK"
    ├─ Load mtnk.vxl, mtnktur.vxl, mtnkbarl.vxl
    ├─ _parse_vxl() → sections with voxel data
    ├─ _sections_to_world() → (wx, wy, wz, color) tuples
    ├─ _project_and_render() → 128×128 RGBA Image
    └─ Send PNG bytes
```

## Palette Loading

All RA2 graphics use indexed-colour images with 256-colour `.pal` palette files.

### PAL format

A PAL file is exactly **768 bytes**: 256 RGB triplets where each channel is stored as a **6-bit** value (0–63).

```python
def load_palette(data: bytes) -> list[tuple[int, int, int]]:
    palette = []
    for i in range(256):
        off = i * 3
        r = min(data[off] * 4, 255)      # 6-bit → 8-bit
        g = min(data[off + 1] * 4, 255)
        b = min(data[off + 2] * 4, 255)
        palette.append((r, g, b))
    return palette
```

### Palette selection

Different object types use different palettes:

| Palette file | Used for |
|---|---|
| `unittem.pal` / `unit.pal` | Vehicles and infantry |
| `cameo.pal` | Build queue cameo icons |
| `isotem.pal` / `temperat.pal` | Buildings and terrain |

Palette index **0** is always transparent by convention. Indices **16–31** are remap colours that change to match the player's team colour.

## VXL Voxel Rendering

VXL is Westwood's voxel model format. The renderer produces a 128×128 isometric projection.

### Binary format

```
VXL File Layout (total = 802 + N*28 + bodysize + N*92 bytes)

┌──────────────────────────────────────────────────┐
│ HEADER (802 bytes)                               │
│   Magic: "Voxel Animation\0"  (16 bytes)         │
│   Unknown: u32                                   │
│   NumLimbs: u32                                  │
│   NumLimbs2: u32                                 │
│   BodySize: u32                                  │
│   Unknown2: u16                                  │
│   InternalPalette: 768 bytes (256 × RGB, 6-bit)  │
├──────────────────────────────────────────────────┤
│ LIMB HEADERS (N × 28 bytes each)                 │
│   Name: char[16]                                 │
│   Unknown: 3 × u32                               │
├──────────────────────────────────────────────────┤
│ BODY (BodySize bytes)                             │
│   Per-limb data blocks:                          │
│     SpanStart[cols]: i32[]  (offsets into spans)  │
│     SpanEnd[cols]: i32[]                          │
│     SpanData: variable-length voxel spans         │
├──────────────────────────────────────────────────┤
│ TAILERS (N × 92 bytes each)                      │
│   SpanStartOff: u32                              │
│   SpanEndOff: u32                                │
│   SpanDataOff: u32                               │
│   Transform: float[4][4] (64 bytes)              │
│   Scale: float[3] (12 bytes — per OpenRA layout)  │
│   XSize, YSize, ZSize, NormalType: 4 × u8        │
└──────────────────────────────────────────────────┘
```

### Voxel span encoding

Each column (X, Y pair) in a limb has a vertical span of voxels. The span data encodes:

```
For each column:
  While Z < ZSize:
    Skip: u8    — number of empty Z levels to skip
    Count: u8   — number of voxels following
    Voxels: Count × (ColorIndex: u8, NormalIndex: u8)
    ClosingCount: u8  — repeat of Count (for validation)
```

Columns with `SpanStart[col] < 0` are entirely empty.

### Rendering pipeline stages

The VXL renderer uses a four-stage pipeline:

#### Stage 1: Parse (`_parse_vxl`)

Reads the binary format and produces a list of section dicts, each containing:

```python
{
    "x_size": int, "y_size": int, "z_size": int,
    "voxels": [(vx, vy, vz, color_idx, normal_idx), ...]
}
```

#### Stage 2: World transform (`_sections_to_world`)

Centres each section's voxels around the origin and applies an optional Z offset (for composite rendering):

```python
for vx, vy, vz, cidx, _nidx in section["voxels"]:
    wx = vx - x_size / 2
    wy = vy - y_size / 2
    wz = (vz - z_size / 2) + z_offset
```

#### Stage 3: Projection (`_project_and_render`)

Applies rotation and isometric projection to convert 3D world coordinates to 2D screen coordinates:

**Rotation** (yaw around the vertical axis):

```python
# VXL models face -X by default; offset by -90° so facing 0 = North
angle = -facing * π/4 - π/2

rx = cos(angle) * wx - sin(angle) * wy
ry = sin(angle) * wx + cos(angle) * wy
```

**Isometric projection** (30° elevation):

```python
elevation = 30° (π/6)
sx = rx                                    # screen X
sy = -(ry * sin(elev) + wz * cos(elev))   # screen Y (inverted)
sz = ry * cos(elev) - wz * sin(elev)      # depth
```

#### Stage 4: Rasterization

**Auto-fit**: The projected extents are measured and a zoom factor is calculated to fill the 128×128 canvas with a 10% margin.

**Depth-buffered rendering**: Each projected voxel is drawn as a filled square (size based on zoom factor). A depth buffer ensures closer voxels occlude farther ones:

```python
for sx, sy, sz, cidx in projected:
    px, py = int(sx * zoom + offset_x), int(sy * zoom + offset_y)
    for dy in range(pixel_size):
        for dx in range(pixel_size):
            if sz < depth[py+dy, px+dx]:
                depth[py+dy, px+dx] = sz
                canvas[py+dy, px+dx] = palette[cidx] + [255]
```

### Facing system

| Facing | Direction | Angle |
|---|---|---|
| 0 | North | 0° |
| 1 | NE | 45° |
| 2 | East | 90° |
| 3 | SE | 135° |
| 4 | South | 180° (default game view) |
| 5 | SW | 225° |
| 6 | West | 270° |
| 7 | NW | 315° |

RA2 facings are **clockwise**, which requires negating the mathematical (counter-clockwise) rotation angle. The additional -90° offset accounts for VXL models being natively oriented along the -X axis.

### Composite rendering

Vehicles with turrets and barrels are rendered as a composite overlay. The `render_vxl_composite()` function:

1. Parses each VXL part (`body.vxl`, `tur.vxl`, `barl.vxl`)
2. Converts each to world-space voxels with a Z offset (turret/barrel sit atop the body)
3. Merges all voxels into a single list
4. Runs the shared projection and rasterization

The turret Z offset is calculated as **35% of the body's Z height**:

```python
body_z = max(section["z_size"] for section in body_sections)
turret_z_off = body_z * 0.35
```

### VXL naming convention

| File | Purpose |
|---|---|
| `<base>.vxl` | Body (hull) |
| `<base>tur.vxl` | Turret |
| `<base>barl.vxl` | Barrel |
| `<base>d.vxl` | Deployed state |
| `<base>.hva` | Animation transforms (companion) |

The `<base>` name comes from the `Image=` key resolution chain, not necessarily the object ID.


## SHP Sprite Rendering

SHP is Westwood's 2D sprite format used for infantry, buildings, and UI icons.

### Binary format

```
SHP File Layout

┌────────────────────────────────────────┐
│ HEADER (8 bytes)                       │
│   Zero: u16                            │
│   FullWidth: u16                       │
│   FullHeight: u16                      │
│   NumFrames: u16                       │
├────────────────────────────────────────┤
│ FRAME INFO TABLE (NumFrames × 24 each) │
│   FrameX: u16     FrameY: u16         │
│   FrameWidth: u16 FrameHeight: u16    │
│   Flags: u32 (bit 1=transparent,       │
│                bit 2=RLE compressed)   │
│   FrameColor: 4 bytes                 │
│   Reserved: u32                        │
│   DataOffset: u32                      │
├────────────────────────────────────────┤
│ FRAME DATA                             │
│   Raw pixels or RLE-Zero encoded data  │
└────────────────────────────────────────┘
```

### RLE-Zero compression

The TS/RA2 SHP format uses **RLE-Zero** encoding where transparent runs are compressed:

```
Per line:
  LineLength: u16    (total bytes of compressed data for this line)
  Data bytes:
    0x00 → next byte = count of transparent (zero) pixels
    other → literal colour index pixel
```

```python
while pos < line_end and len(row) < width:
    b = data[pos]; pos += 1
    if b == 0:
        count = data[pos]; pos += 1
        row.extend(b"\x00" * count)    # transparent run
    else:
        row.append(b)                  # literal pixel
```

### Infantry SHP rendering

Infantry sprites contain hundreds of frames organized by animation sequences. The art INI defines:

```ini
[GISequence]
Ready=0,1,1       ; StartFrame=0, FramesPerFacing=1, FacingCount=1
Walk=8,6,6         ; StartFrame=8, FramesPerFacing=6, FacingCount=6
```

For the compass preview grid, RA2 Modder renders the **Ready** (standing) frame for each of 8 facings:

```python
start_frame, frames_per_facing = _get_infantry_ready_info(art_section, art)
frame_index = start_frame + facing * frames_per_facing
img = render_shp(shp_data, palette, frame_index=frame_index)
```

The sequence parser reads the `Ready=` value from the art section's `Sequence=` reference:

```python
seq_data = art.get(art_section["Sequence"])
ready = seq_data["Ready"]       # e.g. "0,1,1"
start, fcount, _ = ready.split(",")
# start=0, fcount=1 → frame_index = 0 + facing * 1
```

### Building SHP rendering

Buildings use a simple SHP with a small number of frames (undamaged, half-damaged, destroyed). RA2 Modder renders **frame 0** (the undamaged state) as a single preview:

```python
img = render_shp(shp_data, palette, frame_index=0)
```

Buildings use the isometric palette (`isotem.pal` or `temperat.pal`) rather than the unit palette.


## Cameo Icon Resolution

Cameo icons (build queue thumbnails) follow a four-step resolution chain:

```python
# 1. Ares CameoPCX= → PCX image file
pcx_name = art_section.get("CameoPCX", "")

# 2. art INI Cameo= → SHP rendered with cameo.pal
cameo_key = art_section.get("Cameo", "")

# 3. Convention fallback → <obj_id>cameo.shp
conv_shp = f"{obj_id.lower()}cameo.shp"

# 4. Faction-colored placeholder
_placeholder(side)
```

The placeholder generates a coloured 60×48 image based on the unit's faction:

| Faction | Colour |
|---|---|
| Allied / GDI | Blue `(30, 60, 160)` |
| Soviet / Nod | Red `(160, 30, 30)` |
| Yuri / ThirdSide | Purple `(110, 30, 140)` |
| Other | Dark grey `(45, 52, 70)` |


## Preview Mode System

The `get_vxl_modes()` function determines which preview modes are available for an object:

### VXL objects (vehicles, aircraft)

| Mode | ID | When shown |
|---|---|---|
| Full composite | `composite` | Turret or barrel exists |
| Body only | `base` | Always |
| Turret | `turret` | `<base>tur.vxl` exists |
| Barrel | `barrel` | `<base>barl.vxl` exists |
| Deployed | `deployed` | `DeployedImage=` or `<base>d.vxl` exists |

### SHP objects (fallback)

| Mode | ID | When shown |
|---|---|---|
| Standing infantry | `shp_stand` | Object type = `InfantryTypes` and `<base>.shp` exists |
| Building preview | `shp_building` | Object type = `BuildingTypes` and `<base>.shp` exists |

VXL is always preferred over SHP when both exist. For objects with neither (weapons, warheads), no preview section is shown.

## Image= Key Resolution

The `Image=` key is critical to the rendering pipeline. It lives in the **rules** section (not art) and redirects visual lookups:

```python
def _resolve_image_key(obj_id, art, rules):
    rules_section = rules.get(obj_id, {})
    image_key = rules_section.get("Image", obj_id)
    art_section = art.get(image_key, art.get(obj_id, {}))
    return image_key, art_section
```

Example: `APOC` has `Image=MTNK` in rules, so:
- VXL files: `mtnk.vxl`, `mtnktur.vxl`, `mtnkbarl.vxl`
- Art section: `art["MTNK"]`
- Cameo lookup: uses art `MTNK`'s `Cameo=` key


## Error Handling

Every renderer follows the **"return placeholder, never crash"** pattern:

- `render_vxl()` → 128×128 transparent RGBA on any exception
- `render_shp()` → 48×48 transparent RGBA on any exception
- `cameo()` → faction-coloured 60×48 placeholder PNG
- `vxl_preview()` → placeholder PNG for missing data

This ensures the UI always renders something, even if a particular model is corrupt or missing from the game files.
