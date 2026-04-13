import hashlib
from pathlib import Path


def cache_path(cache_dir: Path, key: str, suffix: str = ".png") -> Path:
    """Compute the cache file path for a given key."""
    h = hashlib.md5(key.encode()).hexdigest()
    return cache_dir / f"{h}{suffix}"


def get_cached(cache_dir: Path, key: str) -> bytes | None:
    """Get cached data, or None if not cached."""
    p = cache_path(cache_dir, key)
    if p.exists():
        return p.read_bytes()
    return None


def save_cached(cache_dir: Path, key: str, data: bytes) -> None:
    """Save data to cache."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path(cache_dir, key).write_bytes(data)
