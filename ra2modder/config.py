from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class GameConfig:
    game_dir: Path
    patch_dir: Path
    cache_dir: Path
    mix_load_order: list[str] = field(default_factory=list)
    mod_type: str = "vanilla"  # "vanilla", "ares", "phobos"


def default_config(game_dir: str) -> GameConfig:
    p = Path(game_dir)
    mod_type = detect_mod_type(p)
    return GameConfig(
        game_dir=p,
        patch_dir=p / "mypatch",
        cache_dir=Path.home() / ".ra2modder" / "cache" / "sprites",
        mix_load_order=_mix_order_for(p, mod_type),
        mod_type=mod_type,
    )


def detect_mod_type(game_dir: Path) -> str:
    """Auto-detect mod type from DLLs present in game directory."""
    files_lower = {f.name.lower() for f in game_dir.iterdir() if f.is_file()}
    if "phobos.dll" in files_lower:
        return "phobos"
    if "ares.dll" in files_lower:
        return "ares"
    return "vanilla"


def _mix_order_for(game_dir: Path, mod_type: str) -> list[str]:
    """Build MIX load order based on mod type and files present.

    Order: ra2.mix, ra2md.mix first (contain nested local.mix/localmd.mix
    with base rules/art), then expandmd*.mix, then expandmo*.mix.
    """
    base = ["ra2.mix", "ra2md.mix", "langmd.mix"]
    if mod_type == "vanilla":
        return base

    # Ares / Phobos: discover expandmd*.mix and expandmo*.mix files
    expand = sorted(f.name for f in game_dir.glob("expand*.mix"))
    return base + expand
