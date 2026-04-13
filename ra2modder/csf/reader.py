import struct


def parse_csf(data: bytes) -> dict[str, str]:
    """Parse a C&C CSF string table binary file.

    CSF format:
    - Header: " FSC" magic, version(u32), num_labels(u32), num_strings(u32),
              unused(u32), language(u32) = 24 bytes
    - Per label: " LBL" magic, num_pairs(u32), name_len(u32), name(ascii),
                 then per pair: " RTS"/" STRW" magic, char_count(u32),
                 encoded_chars (UTF-16LE, each byte bitwise NOT'd)
    """
    if len(data) < 24:
        return {}

    magic = data[0:4]
    if magic != b" FSC":
        return {}

    _ver, num_labels, _num_strings, _unused, _lang = struct.unpack_from(
        "<5I", data, 4
    )

    result: dict[str, str] = {}
    pos = 24

    for _ in range(num_labels):
        if pos + 12 > len(data):
            break

        lbl_magic = data[pos : pos + 4]
        if lbl_magic != b" LBL":
            break

        num_pairs, name_len = struct.unpack_from("<II", data, pos + 4)
        pos += 12

        if pos + name_len > len(data):
            break
        name = data[pos : pos + name_len].decode("ascii", errors="replace")
        pos += name_len

        value = ""
        for _ in range(num_pairs):
            if pos + 8 > len(data):
                break

            str_magic = data[pos : pos + 4]
            char_count = struct.unpack_from("<I", data, pos + 4)[0]
            pos += 8

            byte_count = char_count * 2
            if pos + byte_count > len(data):
                break

            encoded = data[pos : pos + byte_count]
            decoded_bytes = bytes(~b & 0xFF for b in encoded)
            value = decoded_bytes.decode("utf-16-le", errors="replace")
            pos += byte_count

            # STRW has an extra string (skip it)
            if str_magic == b" WSTRW"[:4]:
                if pos + 4 <= len(data):
                    extra_len = struct.unpack_from("<I", data, pos)[0]
                    pos += 4 + extra_len

        result[name] = value

    return result
