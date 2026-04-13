def serialise_patch(diff: dict[str, dict[str, str]]) -> str:
    """Convert patch diff into a valid RA2 INI file string."""
    lines: list[str] = []
    for section, keys in sorted(diff.items()):
        lines.append(f"[{section}]")
        for key, value in sorted(keys.items()):
            lines.append(f"{key}={value}")
        lines.append("")
    return "\n".join(lines)
