from unittest.mock import patch, MagicMock
from pathlib import Path

from ra2modder.config import GameConfig
from ra2modder.mix.loader import load_game_files


def _make_config(tmp_path: Path, mix_order=None) -> GameConfig:
    return GameConfig(
        game_dir=tmp_path,
        patch_dir=tmp_path / "mypatch",
        cache_dir=tmp_path / "cache",
        mix_load_order=mix_order or ["ra2md.mix"],
    )


def test_loads_files_from_mix(tmp_path):
    (tmp_path / "ra2md.mix").write_bytes(b"\x00" * 16)
    fake_files = {"rulesmd.ini": b"[HTNK]\nStrength=300\n"}
    with patch("ra2mix.read", return_value=fake_files):
        result = load_game_files(_make_config(tmp_path))
    assert result["rulesmd.ini"] == b"[HTNK]\nStrength=300\n"


def test_missing_mix_skipped(tmp_path):
    result = load_game_files(_make_config(tmp_path))
    assert result == {}


def test_later_mix_overrides_earlier(tmp_path):
    (tmp_path / "ra2md.mix").write_bytes(b"\x00")
    (tmp_path / "expand01.mix").write_bytes(b"\x00")
    cfg = _make_config(tmp_path, ["ra2md.mix", "expand01.mix"])

    def fake_read(mix_filepath=None, mix_data=None):
        if mix_filepath and "ra2md" in mix_filepath:
            return {"rulesmd.ini": b"base"}
        if mix_filepath and "expand01" in mix_filepath:
            return {"rulesmd.ini": b"override"}
        return {}

    with patch("ra2mix.read", side_effect=fake_read):
        result = load_game_files(cfg)
    assert result["rulesmd.ini"] == b"override"


def test_nested_mix_extracted(tmp_path):
    (tmp_path / "ra2md.mix").write_bytes(b"\x00")
    inner_files = {"rulesmd.ini": b"[INNER]\nKey=Val\n"}

    call_count = {"n": 0}

    def fake_read(mix_filepath=None, mix_data=None):
        call_count["n"] += 1
        if mix_filepath:
            return {"localmd.mix": b"nested_data"}
        if mix_data == b"nested_data":
            return inner_files
        return {}

    with patch("ra2mix.read", side_effect=fake_read):
        result = load_game_files(_make_config(tmp_path))
    assert result["rulesmd.ini"] == b"[INNER]\nKey=Val\n"


def test_loose_ini_files_picked_up(tmp_path):
    (tmp_path / "art.ini").write_text("[HTNK]\nVoxel=yes\n", encoding="latin-1")
    result = load_game_files(_make_config(tmp_path))
    assert "art.ini" in result
    assert b"Voxel=yes" in result["art.ini"]


def test_read_error_skipped(tmp_path):
    (tmp_path / "ra2md.mix").write_bytes(b"\x00")
    with patch("ra2mix.read", side_effect=Exception("corrupt")):
        result = load_game_files(_make_config(tmp_path))
    assert result == {}
