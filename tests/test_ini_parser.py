from ra2modder.ini.parser import parse_ini


def test_basic_section_and_key():
    text = "[HTNK]\nStrength=300\nCost=900\n"
    result = parse_ini(text)
    assert result["HTNK"]["Strength"] == "300"
    assert result["HTNK"]["Cost"] == "900"


def test_duplicate_key_last_wins():
    text = "[ART]\nCrawls=yes\nCrawls=no\n"
    result = parse_ini(text)
    assert result["ART"]["Crawls"] == "no"


def test_duplicate_section_merges():
    text = "[HTNK]\nStrength=300\n[HTNK]\nCost=900\n"
    result = parse_ini(text)
    assert result["HTNK"]["Strength"] == "300"
    assert result["HTNK"]["Cost"] == "900"


def test_inline_comment_stripped():
    text = "[HTNK]\nStrength=300 ; this is health\n"
    result = parse_ini(text)
    assert result["HTNK"]["Strength"] == "300"


def test_standalone_comment_ignored():
    text = "; this is a comment\n[HTNK]\nStrength=300\n"
    result = parse_ini(text)
    assert "HTNK" in result


def test_key_without_value():
    text = "[FLAGS]\nSomeFlag\n"
    result = parse_ini(text)
    assert result["FLAGS"]["SomeFlag"] == ""


def test_empty_text():
    assert parse_ini("") == {}


def test_whitespace_stripped():
    text = "  [HTNK]  \n  Strength  =  300  \n"
    result = parse_ini(text)
    assert result["HTNK"]["Strength"] == "300"


def test_include_directive_collected():
    text = "[#include]\n0=extra_rules.ini\n1=more_rules.ini\n"
    result = parse_ini(text)
    assert result["#include"]["0"] == "extra_rules.ini"


def test_value_with_equals_sign():
    text = "[SEC]\nFormula=1+1=2\n"
    result = parse_ini(text)
    assert result["SEC"]["Formula"] == "1+1=2"


def test_comma_separated_list():
    text = "[HTNK]\nPrimary=MammothTusk\nSecondary=MammothTusk\nElitePrimary=MammothTusk\n"
    result = parse_ini(text)
    assert result["HTNK"]["Primary"] == "MammothTusk"


def test_index_list():
    text = "[VehicleTypes]\n0=HTNK\n1=MTNK\n2=LTNK\n"
    result = parse_ini(text)
    assert result["VehicleTypes"]["0"] == "HTNK"
    assert result["VehicleTypes"]["2"] == "LTNK"
