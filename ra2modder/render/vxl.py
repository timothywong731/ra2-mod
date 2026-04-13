import struct
import math

import numpy as np
from PIL import Image

_VXL_MAGIC = b"Voxel Animation\x00"
_HEADER_SIZE = 802  # 16 + 4*4 + 2 + 768
_LIMB_HEADER_SIZE = 28
_TAILER_SIZE = 92
_CANVAS = 128
_ELEV = 30.0 * math.pi / 180.0


def render_vxl(
    vxl_data: bytes,
    hva_data: bytes | None,
    palette: list[tuple[int, int, int]],
    facing: int = 4,
) -> Image.Image:
    """Render a VXL voxel model to a PIL RGBA Image.

    facing: 0-7 (0=N, clockwise). Default 4 = SE (standard RA2 game view).
    """
    try:
        sections = _parse_vxl(vxl_data)
        world = _sections_to_world(sections)
        return _project_and_render(world, palette, facing)
    except Exception:
        return Image.new("RGBA", (_CANVAS, _CANVAS), (0, 0, 0, 0))


def render_vxl_composite(
    parts: list[tuple[bytes, float]],
    palette: list[tuple[int, int, int]],
    facing: int = 4,
) -> Image.Image:
    """Render multiple VXL parts overlaid on the same canvas.

    parts: list of (vxl_data, z_offset) tuples.
    z_offset shifts the part upward in world space.
    """
    try:
        world: list[tuple[float, float, float, int]] = []
        for vxl_data, z_off in parts:
            sections = _parse_vxl(vxl_data)
            world.extend(_sections_to_world(sections, z_off))
        return _project_and_render(world, palette, facing)
    except Exception:
        return Image.new("RGBA", (_CANVAS, _CANVAS), (0, 0, 0, 0))


def _sections_to_world(
    sections: list[dict], z_offset: float = 0.0,
) -> list[tuple[float, float, float, int]]:
    """Convert parsed VXL sections to world-space (wx, wy, wz, color_idx)."""
    voxels: list[tuple[float, float, float, int]] = []
    for sec in sections:
        cx = sec["x_size"] / 2.0
        cy = sec["y_size"] / 2.0
        cz = sec["z_size"] / 2.0
        for vx, vy, vz, cidx, _nidx in sec["voxels"]:
            voxels.append((vx - cx, vy - cy, (vz - cz) + z_offset, cidx))
    return voxels


def _project_and_render(
    world_voxels: list[tuple[float, float, float, int]],
    palette: list[tuple[int, int, int]],
    facing: int,
) -> Image.Image:
    """Project world-space voxels and render to canvas."""
    if not world_voxels:
        return Image.new("RGBA", (_CANVAS, _CANVAS), (0, 0, 0, 0))

    # VXL models face -X by default; offset by -90° so facing 0 (N) points up
    angle = -facing * math.pi / 4 - math.pi / 2
    cos_a = math.cos(angle)
    sin_a = math.sin(angle)
    cos_e = math.cos(_ELEV)
    sin_e = math.sin(_ELEV)

    projected: list[tuple[float, float, float, int]] = []
    for wx, wy, wz, cidx in world_voxels:
        rx = cos_a * wx - sin_a * wy
        ry = sin_a * wx + cos_a * wy

        sx = rx
        sy = -(ry * sin_e + wz * cos_e)
        sz = ry * cos_e - wz * sin_e
        projected.append((sx, sy, sz, cidx))

    # Auto-fit: find extent and scale to fill canvas with margin
    xs = [p[0] for p in projected]
    ys = [p[1] for p in projected]
    extent_x = max(xs) - min(xs) + 1
    extent_y = max(ys) - min(ys) + 1
    margin = _CANVAS * 0.1
    usable = _CANVAS - 2 * margin
    zoom = min(usable / extent_x, usable / extent_y) if extent_x > 0 and extent_y > 0 else 1.0
    offset_x = _CANVAS / 2 - (max(xs) + min(xs)) / 2 * zoom
    offset_y = _CANVAS / 2 - (max(ys) + min(ys)) / 2 * zoom

    # Render with depth buffer, drawing filled squares
    canvas = np.zeros((_CANVAS, _CANVAS, 4), dtype=np.uint8)
    depth = np.full((_CANVAS, _CANVAS), np.inf)
    pixel_size = max(1, int(math.ceil(zoom)))

    for sx, sy, sz, cidx in projected:
        px = int(sx * zoom + offset_x)
        py = int(sy * zoom + offset_y)

        for dy in range(pixel_size):
            for dx in range(pixel_size):
                qx = px + dx
                qy = py + dy
                if 0 <= qx < _CANVAS and 0 <= qy < _CANVAS:
                    if sz < depth[qy, qx]:
                        depth[qy, qx] = sz
                        r, g, b = palette[cidx % 256]
                        canvas[qy, qx] = [r, g, b, 255]

    return Image.fromarray(canvas, "RGBA")


def _parse_vxl(data: bytes) -> list[dict]:
    """Parse a VXL binary file into a list of section dicts.

    VXL layout:
      Header (802 bytes) -> Limb headers (n*28) -> Bodies (bodysize) -> Tailers (n*92)
    """
    if len(data) < _HEADER_SIZE:
        return []
    if data[:16] != _VXL_MAGIC:
        return []

    n_limbs = struct.unpack_from("<I", data, 20)[0]
    bodysize = struct.unpack_from("<I", data, 28)[0]

    body_start = _HEADER_SIZE + n_limbs * _LIMB_HEADER_SIZE
    tailer_start = body_start + bodysize

    if tailer_start + n_limbs * _TAILER_SIZE > len(data):
        return []

    sections = []
    for i in range(n_limbs):
        t_off = tailer_start + i * _TAILER_SIZE

        span_start_off = struct.unpack_from("<I", data, t_off)[0]
        span_end_off = struct.unpack_from("<I", data, t_off + 4)[0]
        span_data_off = struct.unpack_from("<I", data, t_off + 8)[0]

        # Tailer layout per OpenRA: offsets(12) + scale(4) + transform(48) + bounds(24) + sizes(3) + type(1)
        x_size, y_size, z_size, _normal_type = struct.unpack_from(
            "<4B", data, t_off + 88
        )

        col_count = x_size * y_size
        if col_count == 0:
            continue

        ss_addr = body_start + span_start_off
        se_addr = body_start + span_end_off
        sd_addr = body_start + span_data_off

        if ss_addr + col_count * 4 > len(data):
            continue
        if se_addr + col_count * 4 > len(data):
            continue

        span_starts = struct.unpack_from(f"<{col_count}i", data, ss_addr)
        span_ends = struct.unpack_from(f"<{col_count}i", data, se_addr)

        voxels: list[tuple[int, int, int, int, int]] = []
        for col in range(col_count):
            cx = col % x_size
            cy = col // x_size
            s_off = span_starts[col]

            if s_off < 0:
                continue

            pos = sd_addr + s_off
            z = 0

            # Read spans until z covers the full column height
            while z < z_size and pos + 1 < len(data):
                skip = data[pos]
                pos += 1
                count = data[pos]
                pos += 1
                z += skip
                for _ in range(count):
                    if pos + 1 >= len(data):
                        break
                    color_idx = data[pos]
                    pos += 1
                    normal_idx = data[pos]
                    pos += 1
                    voxels.append((cx, cy, z, color_idx, normal_idx))
                    z += 1
                # closing count byte
                if pos < len(data):
                    pos += 1

        sections.append(
            {
                "x_size": x_size,
                "y_size": y_size,
                "z_size": z_size,
                "voxels": voxels,
            }
        )

    return sections
