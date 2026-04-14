def load_palette(data: bytes) -> list[tuple[int, int, int]]:
    """Load a 256-color palette from a .pal file.

    PAL files are 768 bytes: 256 RGB triplets, each 6-bit (0-63).
    Returned values are scaled to 8-bit (0-255).
    Index 0 is treated as transparent by convention.
    """
    palette: list[tuple[int, int, int]] = []

    for i in range(256):
        off = i * 3
        if off + 3 <= len(data):
            r = min(data[off] * 4, 255)
            g = min(data[off + 1] * 4, 255)
            b = min(data[off + 2] * 4, 255)
            palette.append((r, g, b))
        else:
            palette.append((0, 0, 0))

    return palette


# VPL file layout constants.
_VPL_HEADER_SIZE = 16       # 4 DWORDs: remap_start, remap_end, section_count, reserved
_VPL_INTERNAL_PAL = 768     # 256×3 internal palette (ignored by engine)
_VPL_SECTIONS = 32          # max shade levels
_VPL_SECTION_SIZE = 256     # 256 colour indices per section
_VPL_TABLE_SIZE = _VPL_SECTIONS * _VPL_SECTION_SIZE  # 8192
_VPL_FULL_SIZE = _VPL_HEADER_SIZE + _VPL_INTERNAL_PAL + _VPL_TABLE_SIZE  # 8976


def load_vpl(data: bytes) -> list[int] | None:
    """Load a VPL (Voxel Palette Lookup) file.

    VPL format (8976 bytes):
      Header  : 16 bytes  (remap_start, remap_end, section_count, reserved – all u32le)
      Palette : 768 bytes (internal 256×RGB palette, ignored by the engine)
      Sections: 32 × 256 bytes (shade lookup tables)

    Each section is a 256-byte lookup table: section[colour_index] → shaded
    colour index in unittem.pal.  Section 0 is darkest; section 31 brightest.

    Returns a flat list of 8192 ints (sections concatenated), or None.
    """
    data_offset = _VPL_HEADER_SIZE + _VPL_INTERNAL_PAL  # 784
    if len(data) >= data_offset + _VPL_TABLE_SIZE:
        return list(data[data_offset:data_offset + _VPL_TABLE_SIZE])
    # Fallback: headerless / raw table
    if len(data) >= _VPL_TABLE_SIZE:
        return list(data[:_VPL_TABLE_SIZE])
    return None


# House/player colour gradients for palette indices 16-31.
# Maps side keywords to base RGB colours.
_HOUSE_COLOURS: dict[str, tuple[int, int, int]] = {
    "gdi":       (80, 120, 255),
    "allied":    (80, 120, 255),
    "nod":       (220, 40, 20),
    "soviet":    (220, 40, 20),
    "yuri":      (160, 40, 200),
    "thirdside": (160, 40, 200),
}
_DEFAULT_HOUSE_COLOUR = (160, 180, 240)  # neutral blue


def remap_player_colors(
    palette: list[tuple[int, int, int]],
    side: str = "",
) -> list[tuple[int, int, int]]:
    """Replace palette indices 16-31 with a house colour gradient.

    RA2 reserves palette indices 16-31 for player/house colours.
    In the raw .pal file these contain placeholder values; the game
    replaces them at runtime with the owning player's colour ramp.
    """
    side_l = side.lower()
    base = _DEFAULT_HOUSE_COLOUR
    for key, colour in _HOUSE_COLOURS.items():
        if key in side_l:
            base = colour
            break

    new_palette = list(palette)
    r, g, b = base
    for i in range(16):
        t = i / 15.0  # 0.0 (darkest) → 1.0 (brightest)
        brightness = 0.18 + 0.82 * t
        new_palette[16 + i] = (
            min(255, int(r * brightness)),
            min(255, int(g * brightness)),
            min(255, int(b * brightness)),
        )
    return new_palette
