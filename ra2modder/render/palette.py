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
