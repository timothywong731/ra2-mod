import struct

from PIL import Image

from ra2modder.render.shp import render_shp, _decode_rle_zero
from ra2modder.render.palette import load_palette


def _make_palette() -> list[tuple[int, int, int]]:
    """Create a test palette: index 0=black(transparent), 1=red, 2=green, etc."""
    pal = [(0, 0, 0)] * 256
    pal[1] = (255, 0, 0)
    pal[2] = (0, 255, 0)
    pal[3] = (0, 0, 255)
    pal[4] = (255, 255, 0)
    return pal


def _build_shp_uncompressed(
    full_w: int, full_h: int, frames: list[tuple[int, int, int, int, bytes]]
) -> bytes:
    """Build a minimal SHP binary with uncompressed frames.

    frames: list of (fx, fy, fw, fh, pixel_data)
    """
    n = len(frames)
    header = struct.pack("<4H", 0, full_w, full_h, n)

    # Calculate data offsets (header=8, frame_info_table=n*24, then pixel data)
    info_table_size = n * 24
    data_start = 8 + info_table_size

    info_entries = bytearray()
    pixel_blob = bytearray()
    current_offset = data_start

    for fx, fy, fw, fh, pixels in frames:
        flags = 0  # no RLE, no transparency flag needed (index 0 = transparent by convention)
        frame_color = b"\x00\x00\x00\x00"
        reserved = 0
        info_entries += struct.pack(
            "<4HI4sII",
            fx, fy, fw, fh, flags, frame_color, reserved, current_offset,
        )
        pixel_blob += pixels
        current_offset += len(pixels)

    return header + bytes(info_entries) + bytes(pixel_blob)


def _build_shp_rle(
    full_w: int, full_h: int, fx: int, fy: int, fw: int, fh: int,
    rle_data: bytes,
) -> bytes:
    """Build a minimal SHP binary with RLE-compressed frame."""
    header = struct.pack("<4H", 0, full_w, full_h, 1)
    data_offset = 8 + 24  # header + 1 frame info entry
    flags = 0x02  # UsesRle
    frame_color = b"\x00\x00\x00\x00"
    reserved = 0
    info = struct.pack(
        "<4HI4sII",
        fx, fy, fw, fh, flags, frame_color, reserved, data_offset,
    )
    return header + info + rle_data


def test_render_empty_data():
    img = render_shp(b"", _make_palette())
    assert isinstance(img, Image.Image)
    assert img.size == (48, 48)


def test_render_single_pixel():
    pixels = bytes([1])  # palette index 1 = red
    data = _build_shp_uncompressed(4, 4, [(0, 0, 1, 1, pixels)])
    pal = _make_palette()
    img = render_shp(data, pal, 0)
    assert img.size == (4, 4)
    # Check that pixel (0,0) is red
    r, g, b, a = img.getpixel((0, 0))
    assert (r, g, b, a) == (255, 0, 0, 255)


def test_render_transparent_pixel():
    pixels = bytes([0])  # index 0 = transparent
    data = _build_shp_uncompressed(4, 4, [(0, 0, 1, 1, pixels)])
    img = render_shp(data, _make_palette(), 0)
    r, g, b, a = img.getpixel((0, 0))
    assert a == 0  # transparent


def test_render_frame_at_offset():
    pixels = bytes([2])  # green
    data = _build_shp_uncompressed(8, 8, [(3, 4, 1, 1, pixels)])
    img = render_shp(data, _make_palette(), 0)
    assert img.size == (8, 8)
    r, g, b, a = img.getpixel((3, 4))
    assert (r, g, b) == (0, 255, 0)
    assert a == 255


def test_render_multiple_frames():
    pixels0 = bytes([1])  # red
    pixels1 = bytes([3])  # blue
    data = _build_shp_uncompressed(4, 4, [
        (0, 0, 1, 1, pixels0),
        (1, 1, 1, 1, pixels1),
    ])
    pal = _make_palette()

    img0 = render_shp(data, pal, 0)
    r, g, b, a = img0.getpixel((0, 0))
    assert (r, g, b) == (255, 0, 0)

    img1 = render_shp(data, pal, 1)
    r, g, b, a = img1.getpixel((1, 1))
    assert (r, g, b) == (0, 0, 255)


def test_render_invalid_frame_index():
    pixels = bytes([1])
    data = _build_shp_uncompressed(4, 4, [(0, 0, 1, 1, pixels)])
    img = render_shp(data, _make_palette(), 99)
    assert isinstance(img, Image.Image)


def test_rle_decode_simple():
    # 2x1 frame: line of [1, 2] — no RLE triggers
    line_data = bytes([1, 2])
    line_len = len(line_data)
    rle_bytes = struct.pack("<H", line_len) + line_data
    result = _decode_rle_zero(rle_bytes, 0, 2, 1)
    assert result == bytes([1, 2])


def test_rle_decode_with_zero_run():
    # 4x1 frame: [1, 0(x2), 3] → RLE: [1, 0x00, 0x02, 3]
    line_data = bytes([1, 0x00, 0x02, 3])
    line_len = len(line_data)
    rle_bytes = struct.pack("<H", line_len) + line_data
    result = _decode_rle_zero(rle_bytes, 0, 4, 1)
    assert result == bytes([1, 0, 0, 3])


def test_render_rle_frame():
    # 3x1 frame with RLE: [2, 0x00, 0x01, 3] → [2, 0, 3]
    line_data = bytes([2, 0x00, 0x01, 3])
    line_len = len(line_data)
    rle_data = struct.pack("<H", line_len) + line_data

    data = _build_shp_rle(4, 4, 0, 0, 3, 1, rle_data)
    pal = _make_palette()
    img = render_shp(data, pal, 0)
    # pixel 0 should be green (index 2)
    r, g, b, a = img.getpixel((0, 0))
    assert (r, g, b, a) == (0, 255, 0, 255)
    # pixel 1 should be transparent (index 0)
    r, g, b, a = img.getpixel((1, 0))
    assert a == 0
    # pixel 2 should be blue (index 3)
    r, g, b, a = img.getpixel((2, 0))
    assert (r, g, b, a) == (0, 0, 255, 255)


def test_load_palette():
    # 768 bytes, 6-bit values
    data = bytearray(768)
    data[0] = 0; data[1] = 0; data[2] = 0  # index 0: black
    data[3] = 63; data[4] = 0; data[5] = 0  # index 1: bright red
    data[6] = 0; data[7] = 63; data[8] = 0  # index 2: bright green
    pal = load_palette(bytes(data))
    assert len(pal) == 256
    assert pal[0] == (0, 0, 0)
    assert pal[1] == (252, 0, 0)  # 63*4
    assert pal[2] == (0, 252, 0)
