import struct
import math

import numpy as np
from PIL import Image

_VXL_MAGIC = b"Voxel Animation\x00"
_HEADER_SIZE = 802  # 16 + 4*4 + 2 + 768
_LIMB_HEADER_SIZE = 28
_TAILER_SIZE = 92
_CANVAS = 200
_SUPERSAMPLE = 2  # render at 2× then downscale for anti-aliasing
_INTERNAL = _CANVAS * _SUPERSAMPLE
_ELEV = 30.0 * math.pi / 180.0

# Lighting parameters
_AMBIENT = 0.42
_DIFFUSE = 0.58
# Light direction in screen space (pointing TOWARD the light source)
# Upper-left light, slightly toward the viewer
_LIGHT_SCREEN = np.array([0.35, -0.65, 0.55], dtype=np.float64)
_LIGHT_SCREEN /= np.linalg.norm(_LIGHT_SCREEN)


def _gen_hemisphere_normals(count: int) -> np.ndarray:
    """Generate *count* normals distributed over the upper unit hemisphere.

    Uses a Fibonacci-spiral sampling that produces an even distribution.
    Index 0 points straight up; higher indices move toward the equator.
    """
    normals = np.empty((count, 3), dtype=np.float64)
    golden = (1.0 + math.sqrt(5.0)) / 2.0
    for i in range(count):
        z = 1.0 - (i / max(count - 1, 1))
        z = max(0.0, z)
        r = math.sqrt(max(0.0, 1.0 - z * z))
        phi = 2.0 * math.pi * i / golden
        normals[i] = (r * math.cos(phi), r * math.sin(phi), z)
    return normals


# Pre-computed normal lookup tables for each VXL normal type
_NORMAL_TABLES: dict[int, np.ndarray] = {
    1: _gen_hemisphere_normals(36),
    2: _gen_hemisphere_normals(36),
    3: _gen_hemisphere_normals(80),
    4: _gen_hemisphere_normals(244),
}


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
        normal_type = sections[0].get("normal_type", 4) if sections else 4
        world = _sections_to_world(sections)
        return _project_and_render(world, palette, facing, normal_type)
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
        world: list[tuple[float, float, float, int, int]] = []
        normal_type = 4
        for vxl_data, z_off in parts:
            sections = _parse_vxl(vxl_data)
            if sections:
                normal_type = sections[0].get("normal_type", 4)
            world.extend(_sections_to_world(sections, z_off))
        return _project_and_render(world, palette, facing, normal_type)
    except Exception:
        return Image.new("RGBA", (_CANVAS, _CANVAS), (0, 0, 0, 0))


def _sections_to_world(
    sections: list[dict], z_offset: float = 0.0,
) -> list[tuple[float, float, float, int, int]]:
    """Convert parsed VXL sections to world-space (wx, wy, wz, color_idx, normal_idx)."""
    voxels: list[tuple[float, float, float, int, int]] = []
    for sec in sections:
        cx = sec["x_size"] / 2.0
        cy = sec["y_size"] / 2.0
        cz = sec["z_size"] / 2.0
        for vx, vy, vz, cidx, nidx in sec["voxels"]:
            voxels.append((vx - cx, vy - cy, (vz - cz) + z_offset, cidx, nidx))
    return voxels


def _project_and_render(
    world_voxels: list[tuple[float, float, float, int, int]],
    palette: list[tuple[int, int, int]],
    facing: int,
    normal_type: int = 4,
) -> Image.Image:
    """Project world-space voxels and render to canvas with lighting."""
    if not world_voxels:
        return Image.new("RGBA", (_CANVAS, _CANVAS), (0, 0, 0, 0))

    normal_table = _NORMAL_TABLES.get(normal_type, _NORMAL_TABLES[4])

    # RA2 VXL models face +X in local space.  Offset by +π/2 so
    # facing 0 (N) renders with the model's front pointing upward.
    angle = -facing * math.pi / 4 + math.pi / 2
    cos_a = math.cos(angle)
    sin_a = math.sin(angle)
    cos_e = math.cos(_ELEV)
    sin_e = math.sin(_ELEV)

    # Vectorised projection using numpy
    arr = np.array(world_voxels, dtype=np.float64)  # (N, 5)
    wx, wy, wz = arr[:, 0], arr[:, 1], arr[:, 2]
    cidx = arr[:, 3].astype(np.int32)
    nidx = arr[:, 4].astype(np.int32)

    # Yaw rotation
    rx = cos_a * wx - sin_a * wy
    ry = sin_a * wx + cos_a * wy

    # Isometric projection with elevation
    sx = rx
    sy = -(ry * sin_e + wz * cos_e)
    sz = ry * cos_e - wz * sin_e  # depth

    # --- Lighting ---
    # Rotate normals from model space through yaw + elevation to screen space
    normals = normal_table[nidx % len(normal_table)]  # (N, 3)
    nx, ny_n, nz = normals[:, 0], normals[:, 1], normals[:, 2]
    # Yaw
    rnx = cos_a * nx - sin_a * ny_n
    rny = sin_a * nx + cos_a * ny_n
    # Elevation
    snx = rnx
    sny = -(rny * sin_e + nz * cos_e)
    snz = rny * cos_e - nz * sin_e

    # Diffuse lighting (dot product with screen-space light direction)
    dots = snx * _LIGHT_SCREEN[0] + sny * _LIGHT_SCREEN[1] + snz * _LIGHT_SCREEN[2]
    intensity = _AMBIENT + _DIFFUSE * np.clip(dots, 0.0, 1.0)

    # --- Auto-fit to internal canvas ---
    extent_x = sx.max() - sx.min() + 1
    extent_y = sy.max() - sy.min() + 1
    margin = _INTERNAL * 0.08
    usable = _INTERNAL - 2 * margin
    zoom = min(usable / extent_x, usable / extent_y) if extent_x > 0 and extent_y > 0 else 1.0
    offset_x = _INTERNAL / 2 - (sx.max() + sx.min()) / 2 * zoom
    offset_y = _INTERNAL / 2 - (sy.max() + sy.min()) / 2 * zoom

    px = (sx * zoom + offset_x).astype(np.int32)
    py = (sy * zoom + offset_y).astype(np.int32)

    # Sort front-to-back by depth (smallest sz = closest to camera)
    order = np.argsort(sz)
    px, py, sz_sorted = px[order], py[order], sz[order]
    cidx, intensity = cidx[order], intensity[order]

    # Render with depth buffer at internal resolution
    size = _INTERNAL
    canvas = np.zeros((size, size, 4), dtype=np.uint8)
    depth = np.full((size, size), np.inf, dtype=np.float64)

    pal_arr = np.array(palette, dtype=np.float64)  # (256, 3)

    pixel_size = max(2, int(math.ceil(zoom)))

    for i in range(len(order)):
        x0, y0 = int(px[i]), int(py[i])
        z_val = sz_sorted[i]
        ci = int(cidx[i]) % 256
        lit = float(intensity[i])

        r = min(255, int(pal_arr[ci, 0] * lit))
        g = min(255, int(pal_arr[ci, 1] * lit))
        b = min(255, int(pal_arr[ci, 2] * lit))

        for dy in range(pixel_size):
            qy = y0 + dy
            if qy < 0 or qy >= size:
                continue
            for dx in range(pixel_size):
                qx = x0 + dx
                if 0 <= qx < size and z_val < depth[qy, qx]:
                    depth[qy, qx] = z_val
                    canvas[qy, qx] = (r, g, b, 255)

    # Downscale from internal resolution to output canvas (anti-aliased)
    img = Image.fromarray(canvas, "RGBA")
    if _SUPERSAMPLE > 1:
        img = img.resize((_CANVAS, _CANVAS), Image.LANCZOS)
    return img


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
                "normal_type": _normal_type,
                "voxels": voxels,
            }
        )

    return sections
