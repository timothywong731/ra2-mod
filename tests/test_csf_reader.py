import struct

from ra2modder.csf.reader import parse_csf


def _build_csf(labels: dict[str, str]) -> bytes:
    """Build a minimal CSF binary for testing."""
    buf = bytearray()
    # Header: " FSC" (little-endian "CSF "), version 3, num_labels, num_strings, unused, lang
    num = len(labels)
    buf += struct.pack("<4sIIIII", b" FSC", 3, num, num, 0, 0)

    for name, value in labels.items():
        # Label header: " LBL", num_pairs, name_len, name
        name_bytes = name.encode("ascii")
        buf += struct.pack("<4sII", b" LBL", 1, len(name_bytes))
        buf += name_bytes

        # String value: " RTS", char_count, encoded_chars (UTF-16LE, bitwise NOT)
        encoded = value.encode("utf-16-le")
        inverted = bytes(~b & 0xFF for b in encoded)
        buf += struct.pack("<4sI", b" RTS", len(value))
        buf += inverted

    return bytes(buf)


def test_parse_single_label():
    data = _build_csf({"Name:HTNK": "Apocalypse Tank"})
    result = parse_csf(data)
    assert result["Name:HTNK"] == "Apocalypse Tank"


def test_parse_multiple_labels():
    data = _build_csf({"Name:HTNK": "Apocalypse Tank", "Name:MTNK": "Rhino Tank"})
    result = parse_csf(data)
    assert result["Name:HTNK"] == "Apocalypse Tank"
    assert result["Name:MTNK"] == "Rhino Tank"


def test_parse_empty_csf():
    data = _build_csf({})
    result = parse_csf(data)
    assert result == {}


def test_parse_unicode_value():
    data = _build_csf({"Test:Unicode": "Einheit"})
    result = parse_csf(data)
    assert result["Test:Unicode"] == "Einheit"


def test_parse_truncated_returns_partial():
    data = _build_csf({"Name:HTNK": "Apocalypse Tank"})
    # Truncate to just the header + first label header
    result = parse_csf(data[:30])
    assert isinstance(result, dict)
