def parse_ini(text: str) -> dict[str, dict[str, str]]:
    """Parse RA2 INI text.

    Handles: duplicate keys (last wins), duplicate sections (merged),
    keys without values, inline ; comments, [#include] directives,
    values containing = signs.
    """
    result: dict[str, dict[str, str]] = {}
    current: str | None = None

    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith(";"):
            continue

        # Section header
        if line.startswith("[") and "]" in line:
            current = line[1 : line.index("]")].strip()
            if current not in result:
                result[current] = {}
            continue

        if current is None:
            continue

        # Strip inline comment (semicolons after a space)
        ci = line.find(" ;")
        if ci >= 0:
            line = line[:ci].strip()

        if "=" in line:
            key, _, value = line.partition("=")
            result[current][key.strip()] = value.strip()
        else:
            result[current][line] = ""

    return result
