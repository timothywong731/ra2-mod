from pathlib import Path

from ra2modder.ini.rules import load_rules
from ra2modder.ini.art import load_art


def test_load_rules_base_only():
    files = {"rulesmd.ini": b"[HTNK]\nStrength=300\n"}
    result = load_rules(files, Path("/nonexistent"))
    assert result["HTNK"]["Strength"] == "300"


def test_load_rules_expansion_overrides_base():
    files = {
        "rulesmd.ini": b"[HTNK]\nStrength=300\nCost=900\n",
        "rulesmo99.ini": b"[HTNK]\nStrength=400\n",
    }
    result = load_rules(files, Path("/nonexistent"))
    assert result["HTNK"]["Strength"] == "400"
    assert result["HTNK"]["Cost"] == "900"


def test_load_rules_patch_overrides_all(tmp_path):
    (tmp_path / "rulesmd.ini").write_text("[HTNK]\nCost=750\n", encoding="latin-1")
    files = {"rulesmd.ini": b"[HTNK]\nStrength=300\nCost=900\n"}
    result = load_rules(files, tmp_path)
    assert result["HTNK"]["Cost"] == "750"
    assert result["HTNK"]["Strength"] == "300"


def test_load_art_merges_base_and_mod():
    files = {
        "art.ini": b"[HTNK]\nVoxel=yes\n",
        "artmd.ini": b"[HTNK]\nRemapable=yes\n",
    }
    result = load_art(files, Path("/nonexistent"))
    assert result["HTNK"]["Voxel"] == "yes"
    assert result["HTNK"]["Remapable"] == "yes"


def test_load_rules_case_insensitive_filenames():
    files = {"RULESMD.INI": b"[HTNK]\nStrength=300\n"}
    result = load_rules(files, Path("/nonexistent"))
    assert result["HTNK"]["Strength"] == "300"


def test_include_directive_resolved():
    files = {
        "rulesmd.ini": b"[#include]\n0=extra.ini\n[HTNK]\nStrength=300\n",
        "extra.ini": b"[MTNK]\nCost=1200\n",
    }
    result = load_rules(files, Path("/nonexistent"))
    assert result["HTNK"]["Strength"] == "300"
    assert result["MTNK"]["Cost"] == "1200"


def test_load_rules_multiple_expansions_in_order():
    files = {
        "rulesmd.ini": b"[HTNK]\nStrength=300\n",
        "rulesmo94.ini": b"[HTNK]\nStrength=400\n",
        "rulesmo99.ini": b"[HTNK]\nStrength=500\n",
    }
    result = load_rules(files, Path("/nonexistent"))
    assert result["HTNK"]["Strength"] == "500"


def test_load_art_patch_overrides(tmp_path):
    (tmp_path / "artmd.ini").write_text("[HTNK]\nVoxel=no\n", encoding="latin-1")
    files = {"artmd.ini": b"[HTNK]\nVoxel=yes\nRemapable=yes\n"}
    result = load_art(files, tmp_path)
    assert result["HTNK"]["Voxel"] == "no"
    assert result["HTNK"]["Remapable"] == "yes"
