import ra2mix

from ra2modder.config import GameConfig


def load_game_files(config: GameConfig) -> dict[str, bytes]:
    """Extract all game files from MIX archives.

    Uses config.mix_load_order. Later files override earlier ones.
    Nested .mix files are resolved recursively.
    Loose INI/CSF/PAL files in game_dir are also picked up.
    """
    result: dict[str, bytes] = {}

    for mix_name in config.mix_load_order:
        mix_path = config.game_dir / mix_name
        if not mix_path.exists():
            continue
        try:
            files = ra2mix.read(mix_filepath=str(mix_path))
        except Exception:
            continue

        # Resolve nested .mix archives
        nested_keys = [k for k in files if k.lower().endswith(".mix")]
        for nk in nested_keys:
            try:
                inner = ra2mix.read(mix_data=files[nk])
                result.update(inner)
            except Exception:
                pass

        # Add/override with top-level files (excluding .mix blobs)
        for k, v in files.items():
            if not k.lower().endswith(".mix"):
                result[k] = v

    # Pick up loose INI/CSF/PAL files from game directory
    if config.game_dir.is_dir():
        for p in config.game_dir.iterdir():
            if p.is_file() and p.suffix.lower() in (".ini", ".csf", ".pal", ".vpl"):
                result[p.name] = p.read_bytes()

    return result
