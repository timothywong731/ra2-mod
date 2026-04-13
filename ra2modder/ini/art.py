from pathlib import Path

from ra2modder.ini.parser import parse_ini


_BASE_NAMES = ["art.ini", "artmd.ini"]


def load_art(
    game_files: dict[str, bytes], patch_dir: Path
) -> dict[str, dict[str, str]]:
    """Merge art INI chain: base -> mod overrides -> user patch.

    Similar structure to rules merger but with art INI filenames.
    """
    merged: dict[str, dict[str, str]] = {}
    lower = {k.lower(): v for k, v in game_files.items()}

    # 1. Base art
    for name in _BASE_NAMES:
        data = lower.get(name)
        if data:
            parsed = parse_ini(data.decode("latin-1", errors="replace"))
            _merge(merged, parsed)

    # 2. Expansion art (auto-discovered, sorted)
    expand_names = sorted(
        k for k in lower if k.startswith("artmo") and k.endswith(".ini")
    )
    for name in expand_names:
        parsed = parse_ini(lower[name].decode("latin-1", errors="replace"))
        _merge(merged, parsed)

    # 3. User patch
    patch = patch_dir / "artmd.ini"
    if patch.exists():
        _merge(merged, parse_ini(patch.read_text(encoding="latin-1")))

    return merged


def _merge(base: dict, override: dict) -> None:
    for section, keys in override.items():
        base.setdefault(section, {}).update(keys)
