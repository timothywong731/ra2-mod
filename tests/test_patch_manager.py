from pathlib import Path

from ra2modder.patch.manager import save_field, revert_field, get_diff


def test_save_field_creates_patch_file(tmp_path):
    save_field(tmp_path, "HTNK", "Cost", "900", "750")
    patch = tmp_path / "rulesmd.ini"
    assert patch.exists()
    assert "Cost=750" in patch.read_text(encoding="latin-1")


def test_save_multiple_fields_same_section(tmp_path):
    save_field(tmp_path, "HTNK", "Cost", "900", "750")
    save_field(tmp_path, "HTNK", "Strength", "300", "400")
    text = (tmp_path / "rulesmd.ini").read_text(encoding="latin-1")
    assert "Cost=750" in text
    assert "Strength=400" in text


def test_revert_field_removes_key(tmp_path):
    save_field(tmp_path, "HTNK", "Cost", "900", "750")
    revert_field(tmp_path, "HTNK", "Cost")
    text = (tmp_path / "rulesmd.ini").read_text(encoding="latin-1")
    assert "Cost" not in text


def test_get_diff_returns_changes(tmp_path):
    save_field(tmp_path, "HTNK", "Cost", "900", "750")
    diff = get_diff(tmp_path)
    assert diff["HTNK"]["Cost"] == "750"


def test_get_diff_empty_when_no_patch(tmp_path):
    assert get_diff(tmp_path) == {}


def test_save_multiple_sections(tmp_path):
    save_field(tmp_path, "HTNK", "Cost", "900", "750")
    save_field(tmp_path, "MTNK", "Strength", "300", "400")
    diff = get_diff(tmp_path)
    assert "HTNK" in diff
    assert "MTNK" in diff


def test_revert_removes_empty_section(tmp_path):
    save_field(tmp_path, "HTNK", "Cost", "900", "750")
    revert_field(tmp_path, "HTNK", "Cost")
    diff = get_diff(tmp_path)
    assert "HTNK" not in diff
