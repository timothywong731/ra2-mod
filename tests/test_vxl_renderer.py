import struct

import numpy as np
from PIL import Image

from ra2modder.render.vxl import render_vxl, render_vxl_composite
from ra2modder.render.palette import load_vpl, remap_player_colors
from ra2modder.routes.sprites import get_vxl_modes, _resolve_vxl_names, _get_infantry_ready_info


def _make_palette() -> list[tuple[int, int, int]]:
    """Palette where index 1 = bright red."""
    pal = [(0, 0, 0)] * 256
    pal[1] = (252, 0, 0)
    pal[2] = (0, 252, 0)
    return pal


def _make_vxl(
    voxels: list[tuple[int, int, int, int, int]],
    x_size: int = 4,
    y_size: int = 4,
    z_size: int = 4,
) -> bytes:
    """Build a minimal single-limb VXL file matching the real binary format.

    VXL layout: Header (802) + Limb headers (28) + Body (var) + Tailer (92)
    """
    n_limbs = 1
    col_count = x_size * y_size

    # --- Group voxels by column (x, y) ---
    columns: dict[tuple[int, int], list[tuple[int, int, int]]] = {}
    for vx, vy, vz, ci, ni in voxels:
        columns.setdefault((vx, vy), []).append((vz, ci, ni))

    # --- Build span data ---
    span_data = bytearray()
    span_starts = [-1] * col_count
    span_ends = [-1] * col_count

    for col_idx in range(col_count):
        cx = col_idx % x_size
        cy = col_idx // x_size
        col_voxels = sorted(columns.get((cx, cy), []))
        if not col_voxels:
            continue

        span_starts[col_idx] = len(span_data)

        # Group into contiguous Z runs
        groups: list[list[tuple[int, int, int]]] = []
        current_group: list[tuple[int, int, int]] = []
        for vz, color, normal in col_voxels:
            if current_group and vz != current_group[-1][0] + 1:
                groups.append(current_group)
                current_group = []
            current_group.append((vz, color, normal))
        if current_group:
            groups.append(current_group)

        for group in groups:
            skip_z = group[0][0]
            count = len(group)
            span_data += bytes([skip_z, count])
            for _vz, gc, gn in group:
                span_data += bytes([gc, gn])
            span_data += bytes([count])  # closing count byte

        span_ends[col_idx] = len(span_data)

    # --- Body: span_start_array + span_end_array + span_data ---
    span_start_array = struct.pack(f"<{col_count}i", *span_starts)
    span_end_array = struct.pack(f"<{col_count}i", *span_ends)

    span_start_off = 0
    span_end_off = col_count * 4
    span_data_off = col_count * 8

    body = span_start_array + span_end_array + bytes(span_data)
    bodysize = len(body)

    # --- Header (802 bytes) ---
    header = bytearray()
    header += b"Voxel Animation\x00"  # 16 bytes
    header += struct.pack("<I", 1)  # unknown = 1
    header += struct.pack("<I", n_limbs)
    header += struct.pack("<I", n_limbs)  # n_limbs2
    header += struct.pack("<I", bodysize)
    header += struct.pack("<H", 0x1F10)  # unknown2
    palette_bytes = bytearray(768)
    palette_bytes[1 * 3] = 63  # index 1 R (6-bit)
    header += palette_bytes
    assert len(header) == 802

    # --- Limb header (28 bytes) ---
    limb_hdr = b"body\x00" + b"\x00" * 11  # name[16]
    limb_hdr += struct.pack("<III", 0, 1, 0)
    assert len(limb_hdr) == 28

    # --- Limb tailer (92 bytes) ---
    tailer = struct.pack("<III", span_start_off, span_end_off, span_data_off)
    # transform[4][4] = identity
    transform = [
        1.0, 0.0, 0.0, 0.0,
        0.0, 1.0, 0.0, 0.0,
        0.0, 0.0, 1.0, 0.0,
        0.0, 0.0, 0.0, 1.0,
    ]
    tailer += struct.pack("<16f", *transform)
    # scale[3]
    tailer += struct.pack("<3f", 1.0, 1.0, 1.0)
    # x_size, y_size, z_size, normal_type(4=RA2)
    tailer += struct.pack("<4B", x_size, y_size, z_size, 4)
    assert len(tailer) == 92

    # Layout: header + limb_headers + bodies + tailers
    return bytes(header) + limb_hdr + body + tailer


def test_render_returns_pil_image():
    vxl = _make_vxl([(2, 2, 2, 1, 0)])
    img = render_vxl(vxl, None, _make_palette())
    assert isinstance(img, Image.Image)


def test_render_has_nonzero_size():
    vxl = _make_vxl([(1, 1, 1, 1, 0)])
    img = render_vxl(vxl, None, _make_palette())
    w, h = img.size
    assert w > 0 and h > 0


def test_render_rgba_mode():
    vxl = _make_vxl([(0, 0, 0, 1, 0)])
    img = render_vxl(vxl, None, _make_palette())
    assert img.mode == "RGBA"


def test_bad_data_returns_placeholder():
    img = render_vxl(b"\x00" * 8, None, _make_palette())
    assert isinstance(img, Image.Image)
    assert img.mode == "RGBA"


def test_voxel_colour_applied():
    """A red voxel (palette index 1) should produce red pixels."""
    vxl = _make_vxl([(2, 2, 2, 1, 0)])
    palette = _make_palette()
    img = render_vxl(vxl, None, palette)
    arr = np.array(img)
    reds = arr[(arr[:, :, 0] > 100) & (arr[:, :, 3] > 0)]
    assert len(reds) > 0


def test_empty_vxl_renders():
    """VXL with no voxels should still return a valid image."""
    vxl = _make_vxl([])
    img = render_vxl(vxl, None, _make_palette())
    assert isinstance(img, Image.Image)


def test_multiple_voxels():
    """Multiple voxels in different columns."""
    voxels = [
        (0, 0, 0, 1, 0),
        (1, 1, 1, 2, 0),
        (2, 2, 2, 1, 0),
        (3, 3, 3, 2, 0),
    ]
    vxl = _make_vxl(voxels)
    img = render_vxl(vxl, None, _make_palette())
    arr = np.array(img)
    coloured = arr[arr[:, :, 3] > 0]
    assert len(coloured) >= 4


def test_facing_changes_output():
    """Different facings should produce different images."""
    vxl = _make_vxl([(0, 0, 0, 1, 0), (3, 0, 0, 1, 0)])
    pal = _make_palette()
    img_north = render_vxl(vxl, None, pal, facing=0)
    img_se = render_vxl(vxl, None, pal, facing=4)
    assert img_north.tobytes() != img_se.tobytes()


def test_contiguous_z_column():
    """Voxels stacked in the same column at consecutive Z values."""
    voxels = [(1, 1, 0, 1, 0), (1, 1, 1, 1, 0), (1, 1, 2, 1, 0)]
    vxl = _make_vxl(voxels)
    img = render_vxl(vxl, None, _make_palette())
    arr = np.array(img)
    coloured = arr[arr[:, :, 3] > 0]
    assert len(coloured) >= 1


# --- VXL mode detection tests ---


def test_get_vxl_modes_base_only():
    art = {"HTNK": {"Image": "HTNK"}}
    rules = {"HTNK": {}}
    files = {"htnk.vxl": b"", "htnk.hva": b""}
    modes = get_vxl_modes("HTNK", art, rules, files)
    assert modes == [("base", "Body")]


def test_get_vxl_modes_with_turret_barrel():
    art = {"HTNK": {"Image": "HTNK"}}
    rules = {"HTNK": {}}
    files = {"htnk.vxl": b"", "htnktur.vxl": b"", "htnkbarl.vxl": b""}
    modes = get_vxl_modes("HTNK", art, rules, files)
    assert modes[0] == ("composite", "Full")
    assert ("base", "Body") in modes
    assert ("turret", "Turret") in modes
    assert ("barrel", "Barrel") in modes


def test_get_vxl_modes_deployed_via_art_key():
    art = {"SREF": {"DeployedImage": "SREFD"}}
    rules = {"SREF": {}}
    files = {"sref.vxl": b"", "srefd.vxl": b""}
    modes = get_vxl_modes("SREF", art, rules, files)
    assert ("deployed", "Deployed") in modes


def test_get_vxl_modes_deployed_via_suffix():
    art = {"UNIT": {}}
    rules = {"UNIT": {}}
    files = {"unit.vxl": b"", "unitd.vxl": b""}
    modes = get_vxl_modes("UNIT", art, rules, files)
    assert ("deployed", "Deployed") in modes


def test_get_vxl_modes_no_vxl():
    """Objects without VXL or known type return no modes."""
    art = {"GI": {}}
    rules = {"GI": {}}
    files = {"gi.shp": b""}
    modes = get_vxl_modes("GI", art, rules, files)
    assert modes == []


def test_get_vxl_modes_infantry_shp():
    """Infantry without VXL but with SHP returns shp_stand mode."""
    art = {"GI": {}}
    rules = {"GI": {}}
    files = {"gi.shp": b""}
    modes = get_vxl_modes("GI", art, rules, files, obj_type="InfantryTypes")
    assert modes == [("shp_stand", "Stand")]


def test_get_vxl_modes_building_shp():
    """Building without VXL but with SHP returns shp_building mode."""
    art = {"GAPOWR": {}}
    rules = {"GAPOWR": {}}
    files = {"gapowr.shp": b""}
    modes = get_vxl_modes("GAPOWR", art, rules, files, obj_type="BuildingTypes")
    assert modes == [("shp_building", "Building")]


def test_get_vxl_modes_building_with_vxl_prefers_vxl():
    """Building with VXL uses VXL modes, not SHP."""
    art = {"YAGGUN": {}}
    rules = {"YAGGUN": {}}
    files = {"yaggun.vxl": b"", "yaggun.shp": b""}
    modes = get_vxl_modes("YAGGUN", art, rules, files, obj_type="BuildingTypes")
    assert modes == [("base", "Body")]


def test_get_vxl_modes_image_redirect():
    """Image= in rules redirects VXL lookup to a different name."""
    art = {"MTNK": {"Voxel": "yes"}}
    rules = {"APOC": {"Image": "MTNK"}}
    files = {"mtnk.vxl": b"", "mtnktur.vxl": b""}
    modes = get_vxl_modes("APOC", art, rules, files)
    assert modes[0] == ("composite", "Full")
    assert ("base", "Body") in modes
    assert ("turret", "Turret") in modes


def test_resolve_vxl_names_base():
    art = {"HTNK": {}}
    rules = {"HTNK": {}}
    vxl, hva = _resolve_vxl_names("HTNK", art, rules, {}, "base")
    assert vxl == "htnk.vxl"
    assert hva == "htnk.hva"


def test_resolve_vxl_names_turret():
    art = {"HTNK": {}}
    rules = {"HTNK": {}}
    vxl, hva = _resolve_vxl_names("HTNK", art, rules, {}, "turret")
    assert vxl == "htnktur.vxl"
    assert hva == "htnktur.hva"


def test_resolve_vxl_names_deployed_art_key():
    art = {"SREF": {"DeployedImage": "SREFD"}}
    rules = {"SREF": {}}
    lower = {"srefd.vxl": b"data"}
    vxl, hva = _resolve_vxl_names("SREF", art, rules, lower, "deployed")
    assert vxl == "srefd.vxl"


def test_resolve_vxl_names_deployed_fallback_suffix():
    art = {"UNIT": {}}
    rules = {"UNIT": {}}
    vxl, hva = _resolve_vxl_names("UNIT", art, rules, {}, "deployed")
    assert vxl == "unitd.vxl"


def test_resolve_vxl_names_image_redirect():
    """Image= in rules redirects VXL filename."""
    art = {"MTNK": {}}
    rules = {"APOC": {"Image": "MTNK"}}
    vxl, hva = _resolve_vxl_names("APOC", art, rules, {}, "base")
    assert vxl == "mtnk.vxl"
    assert hva == "mtnk.hva"


# --- Composite rendering tests ---


def test_composite_renders_image():
    """Composite render with two VXLs returns a valid image."""
    body = _make_vxl([(2, 2, 0, 1, 0), (2, 2, 1, 1, 0)], z_size=4)
    turret = _make_vxl([(1, 1, 0, 2, 0)], x_size=2, y_size=2, z_size=2)
    img = render_vxl_composite([(body, 0.0), (turret, 2.0)], _make_palette())
    assert isinstance(img, Image.Image)
    assert img.mode == "RGBA"
    arr = np.array(img)
    assert arr[arr[:, :, 3] > 0].shape[0] > 0


def test_composite_empty_parts():
    """Composite with no parts returns transparent image."""
    img = render_vxl_composite([], _make_palette())
    assert isinstance(img, Image.Image)
    arr = np.array(img)
    assert arr[:, :, 3].sum() == 0


def test_composite_has_more_pixels_than_single():
    """Composite body+turret should have more coloured pixels than body alone."""
    body = _make_vxl([(2, 2, 0, 1, 0), (2, 2, 1, 1, 0), (2, 2, 2, 1, 0)], z_size=4)
    turret = _make_vxl([(1, 1, 0, 2, 0), (1, 1, 1, 2, 0)], x_size=2, y_size=2, z_size=2)
    pal = _make_palette()
    body_only = render_vxl(body, None, pal)
    composite = render_vxl_composite([(body, 0.0), (turret, 3.0)], pal)
    body_px = np.array(body_only)[:, :, 3].astype(bool).sum()
    comp_px = np.array(composite)[:, :, 3].astype(bool).sum()
    assert comp_px >= body_px


# --- Infantry sequence parsing tests ---


def test_get_infantry_ready_info_default():
    """No Sequence key returns (0, 1) default."""
    assert _get_infantry_ready_info({}, {}) == (0, 1)


def test_get_infantry_ready_info_parsed():
    """Parses Ready=start,count from sequence section."""
    art_section = {"Sequence": "GISequence"}
    art = {"GISequence": {"Ready": "0,1,1"}}
    assert _get_infantry_ready_info(art_section, art) == (0, 1)


def test_get_infantry_ready_info_walk_offset():
    """Parses a non-zero start frame."""
    art_section = {"Sequence": "TestSeq"}
    art = {"TestSeq": {"Ready": "8,3,3"}}
    assert _get_infantry_ready_info(art_section, art) == (8, 3)


# --- VPL (Voxel Palette Lookup) tests ---


def _make_vpl_data() -> bytes:
    """Build a realistic VPL file: 16-byte header + 768-byte palette + 8192-byte table."""
    header = b"\x10\x00\x00\x00" * 4             # 16 bytes
    internal_pal = bytes(range(256)) * 3             # 768 bytes
    table = bytes(range(256)) * 32                   # 8192 bytes
    return header + internal_pal + table


def test_load_vpl_valid():
    """Valid VPL data (16-byte header + 768-byte palette + table) returns 8192 ints."""
    vpl = load_vpl(_make_vpl_data())
    assert vpl is not None
    assert len(vpl) == 256 * 32


def test_load_vpl_headerless():
    """Headerless VPL (exactly 8192 bytes) also works."""
    data = bytes(range(256)) * 32
    vpl = load_vpl(data)
    assert vpl is not None
    assert len(vpl) == 256 * 32


def test_load_vpl_reads_correct_offset():
    """VPL sections start after the 16-byte header and 768-byte palette."""
    header = b"\x00" * 16
    internal_pal = b"\xff" * 768
    # First section byte = 42, rest zeros
    table = bytes([42]) + b"\x00" * 8191
    data = header + internal_pal + table
    vpl = load_vpl(data)
    assert vpl is not None
    assert vpl[0] == 42


def test_load_vpl_too_short():
    """VPL data shorter than 8192 bytes returns None."""
    assert load_vpl(b"\x00" * 100) is None


def test_render_vxl_direct_palette_index():
    """Color index maps directly to palette without VPL."""
    vxl = _make_vxl([(2, 2, 2, 1, 0)])  # color index 1 = red
    palette = _make_palette()
    img = render_vxl(vxl, None, palette)
    arr = np.array(img)
    reds = arr[(arr[:, :, 0] > 100) & (arr[:, :, 3] > 0)]
    assert len(reds) > 0


# --- Building damaged mode tests ---


def _build_minimal_shp(n_frames: int, full_w: int = 8, full_h: int = 8) -> bytes:
    """Build a minimal SHP binary with the given number of empty frames."""
    header = struct.pack("<4H", 0, full_w, full_h, n_frames)
    info_entries = bytearray()
    for _ in range(n_frames):
        info_entries += struct.pack("<4HI4sII", 0, 0, 0, 0, 0, b"\x00" * 4, 0, 0)
    return header + bytes(info_entries)


def test_get_vxl_modes_building_damaged():
    """Building with multiple SHP frames gets a Damaged mode."""
    shp_data = _build_minimal_shp(4)
    art = {"GAPOWR": {}}
    rules = {"GAPOWR": {}}
    files = {"gapowr.shp": shp_data}
    modes = get_vxl_modes("GAPOWR", art, rules, files, obj_type="BuildingTypes")
    assert ("shp_building", "Building") in modes
    assert ("shp_building_damaged", "Damaged") in modes


def test_get_vxl_modes_building_single_frame_no_damaged():
    """Building with only 1 SHP frame should not have Damaged mode."""
    shp_data = _build_minimal_shp(1)
    art = {"GAPOWR": {}}
    rules = {"GAPOWR": {}}
    files = {"gapowr.shp": shp_data}
    modes = get_vxl_modes("GAPOWR", art, rules, files, obj_type="BuildingTypes")
    assert modes == [("shp_building", "Building")]


# --- Player colour remap tests ---


def test_remap_player_colors_allied():
    """Allied side produces blue gradient at indices 16-31."""
    pal = [(0, 0, 0)] * 256
    remapped = remap_player_colors(pal, "GDI")
    r, g, b = remapped[31]
    assert b > r and b > g and b > 100


def test_remap_player_colors_soviet():
    """Soviet side produces red gradient at indices 16-31."""
    pal = [(0, 0, 0)] * 256
    remapped = remap_player_colors(pal, "Nod")
    r, g, b = remapped[31]
    assert r > g and r > b and r > 100


def test_remap_player_colors_default():
    """Unknown side still produces a gradient (default house colour)."""
    pal = [(0, 0, 0)] * 256
    remapped = remap_player_colors(pal, "")
    assert remapped[31] != (0, 0, 0)


def test_remap_preserves_non_player_indices():
    """Indices outside 16-31 are not modified."""
    pal = [(i, i, i) for i in range(256)]
    remapped = remap_player_colors(pal, "GDI")
    assert remapped[0] == (0, 0, 0)
    assert remapped[15] == (15, 15, 15)
    assert remapped[32] == (32, 32, 32)
    assert remapped[255] == (255, 255, 255)
