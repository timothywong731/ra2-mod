from pathlib import Path

from ra2modder.ini.parser import parse_ini


def save_field(
    patch_dir: Path, section: str, key: str, old_value: str, new_value: str
) -> None:
    """Save a single field change to the patch INI file."""
    patch_file = patch_dir / "rulesmd.ini"
    patch_dir.mkdir(parents=True, exist_ok=True)

    existing = _load_patch(patch_file)
    existing.setdefault(section, {})[key] = new_value
    _write_patch(patch_file, existing)


def revert_field(patch_dir: Path, section: str, key: str) -> None:
    """Remove a single field from the patch INI file."""
    patch_file = patch_dir / "rulesmd.ini"
    existing = _load_patch(patch_file)

    if section in existing:
        existing[section].pop(key, None)
        if not existing[section]:
            del existing[section]

    _write_patch(patch_file, existing)


def get_diff(patch_dir: Path) -> dict[str, dict[str, str]]:
    """Return all pending changes as {section: {key: value}}."""
    patch_file = patch_dir / "rulesmd.ini"
    return _load_patch(patch_file)


def _load_patch(patch_file: Path) -> dict[str, dict[str, str]]:
    if not patch_file.exists():
        return {}
    return parse_ini(patch_file.read_text(encoding="latin-1"))


def _write_patch(
    patch_file: Path, data: dict[str, dict[str, str]]
) -> None:
    lines: list[str] = []
    for section, keys in sorted(data.items()):
        lines.append(f"[{section}]")
        for key, value in sorted(keys.items()):
            lines.append(f"{key}={value}")
        lines.append("")
    patch_file.write_text("\n".join(lines), encoding="latin-1")
