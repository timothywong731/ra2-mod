from pathlib import Path

from ra2modder.ini.parser import parse_ini


_BASE_NAMES = ["rules.ini", "rulesmd.ini"]


def load_rules(
    game_files: dict[str, bytes], patch_dir: Path
) -> dict[str, dict[str, str]]:
    """Merge rules INI chain: base -> expansions -> user patch.

    Expansion INIs are auto-discovered from game_files keys
    (rulesmo*.ini sorted alphabetically).
    Handles Ares [#include] directives.
    """
    merged: dict[str, dict[str, str]] = {}
    lower = {k.lower(): v for k, v in game_files.items()}

    # 1. Base rules
    for name in _BASE_NAMES:
        data = lower.get(name)
        if data:
            parsed = parse_ini(data.decode("latin-1", errors="replace"))
            _resolve_includes(parsed, lower)
            _merge(merged, parsed)

    # 2. Expansion rules (auto-discovered, sorted)
    expand_names = sorted(
        k for k in lower if k.startswith("rulesmo") and k.endswith(".ini")
    )
    for name in expand_names:
        parsed = parse_ini(lower[name].decode("latin-1", errors="replace"))
        _resolve_includes(parsed, lower)
        _merge(merged, parsed)

    # 3. User patch
    patch = patch_dir / "rulesmd.ini"
    if patch.exists():
        _merge(merged, parse_ini(patch.read_text(encoding="latin-1")))

    return merged


def _resolve_includes(
    parsed: dict[str, dict[str, str]],
    game_files: dict[str, bytes],
) -> None:
    """Resolve [#include] directives by merging referenced files."""
    includes = parsed.pop("#include", None)
    if not includes:
        return
    for _idx, filename in sorted(includes.items()):
        data = game_files.get(filename.lower())
        if data:
            included = parse_ini(data.decode("latin-1", errors="replace"))
            _resolve_includes(included, game_files)
            _merge(parsed, included)


def _merge(base: dict, override: dict) -> None:
    for section, keys in override.items():
        base.setdefault(section, {}).update(keys)
