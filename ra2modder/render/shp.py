import struct

import numpy as np
from PIL import Image


def render_shp(
    data: bytes,
    palette: list[tuple[int, int, int]],
    frame_index: int = 0,
) -> Image.Image:
    """Render a TS/RA2 SHP frame to a PIL RGBA Image.

    TS/RA2 SHP format:
    - Header: 8 bytes (Empty:u16, FullWidth:u16, FullHeight:u16, NrOfFrames:u16)
    - Frame info table: NrOfFrames * 24 bytes each
      (FrameX:u16, FrameY:u16, FrameWidth:u16, FrameHeight:u16,
       Flags:u32, FrameColor:4B, Reserved:u32, DataOffset:u32)
    - Flags: bit 1 = HasTransparency, bit 2 = UsesRle
    - RLE: Westwood RLE-Zero per line
    """
    try:
        return _render(data, palette, frame_index)
    except Exception:
        return Image.new("RGBA", (48, 48), (0, 0, 0, 0))


def _render(
    data: bytes,
    palette: list[tuple[int, int, int]],
    frame_index: int,
) -> Image.Image:
    if len(data) < 8:
        return Image.new("RGBA", (48, 48), (0, 0, 0, 0))

    _zero, full_w, full_h, n_frames = struct.unpack_from("<4H", data, 0)

    if n_frames == 0 or frame_index >= n_frames:
        return Image.new("RGBA", (full_w or 48, full_h or 48), (0, 0, 0, 0))

    # Parse frame info (24 bytes per frame, starting at offset 8)
    fi_off = 8 + frame_index * 24
    if fi_off + 24 > len(data):
        return Image.new("RGBA", (full_w, full_h), (0, 0, 0, 0))

    fx, fy, fw, fh = struct.unpack_from("<4H", data, fi_off)
    flags = struct.unpack_from("<I", data, fi_off + 8)[0]
    data_offset = struct.unpack_from("<I", data, fi_off + 20)[0]

    uses_rle = bool(flags & 0x02)

    if data_offset == 0 or fw == 0 or fh == 0:
        return Image.new("RGBA", (full_w, full_h), (0, 0, 0, 0))

    # Decode frame pixels
    if uses_rle:
        pixels = _decode_rle_zero(data, data_offset, fw, fh)
    else:
        size = fw * fh
        pixels = data[data_offset : data_offset + size]

    # Build full-size RGBA image using numpy for speed
    img_array = np.zeros((full_h, full_w, 4), dtype=np.uint8)

    pal_array = np.array(palette, dtype=np.uint8)  # (256, 3)

    for y in range(fh):
        for x in range(fw):
            idx = y * fw + x
            if idx >= len(pixels):
                break
            ci = pixels[idx]
            if ci == 0:
                continue  # transparent
            py = fy + y
            px = fx + x
            if 0 <= py < full_h and 0 <= px < full_w:
                img_array[py, px, 0] = pal_array[ci, 0]
                img_array[py, px, 1] = pal_array[ci, 1]
                img_array[py, px, 2] = pal_array[ci, 2]
                img_array[py, px, 3] = 255

    return Image.fromarray(img_array, "RGBA")


def _decode_rle_zero(
    data: bytes, offset: int, width: int, height: int
) -> bytes:
    """Decode Westwood RLE-Zero compressed frame data (TS/RA2 variant).

    Each line: u16 line_length, then RLE data where 0x00 triggers a run
    (next byte = count of zero-value pixels).
    """
    result = bytearray()
    pos = offset

    for _line in range(height):
        if pos + 2 > len(data):
            result.extend(b"\x00" * width)
            continue

        line_len = struct.unpack_from("<H", data, pos)[0]
        pos += 2
        line_end = pos + line_len
        row = bytearray()

        while pos < line_end and len(row) < width:
            b = data[pos]
            pos += 1
            if b == 0:
                if pos < line_end:
                    count = data[pos]
                    pos += 1
                    row.extend(b"\x00" * count)
                else:
                    row.append(0)
            else:
                row.append(b)

        # Pad or trim to exact width
        if len(row) < width:
            row.extend(b"\x00" * (width - len(row)))
        result.extend(row[:width])

    return bytes(result)
