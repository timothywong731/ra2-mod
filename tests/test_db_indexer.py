import pytest

from ra2modder.db.indexer import build_index
from ra2modder.db.queries import list_objects, get_object, search_objects


@pytest.fixture
def sample_rules():
    return {
        "VehicleTypes": {"0": "HTNK", "1": "MTNK"},
        "InfantryTypes": {"0": "E1"},
        "BuildingTypes": {"0": "GAWEAP"},
        "AircraftTypes": {"0": "ORCA"},
        "HTNK": {
            "Name": "Name:HTNK",
            "Strength": "600",
            "Cost": "1750",
            "Owner": "Russians,Cubans",
            "Primary": "MammothTusk",
            "Image": "HTNK",
        },
        "MTNK": {
            "Name": "Name:MTNK",
            "Strength": "300",
            "Cost": "900",
            "Owner": "Russians",
        },
        "E1": {
            "Name": "Name:E1",
            "Strength": "125",
            "Cost": "200",
            "Owner": "Americans",
        },
        "GAWEAP": {
            "Name": "Name:GAWEAP",
            "Strength": "1000",
            "Cost": "2000",
            "Owner": "Americans",
        },
        "ORCA": {
            "Name": "Name:ORCA",
            "Strength": "150",
            "Cost": "1200",
            "Owner": "Americans",
        },
        "Sides": {"0": "Americans", "1": "Russians,Cubans"},
        "Countries": {"0": "Americans", "1": "Russians", "2": "Cubans"},
        "Americans": {"Side": "Allied"},
        "Russians": {"Side": "Soviet"},
        "Cubans": {"Side": "Soviet"},
    }


@pytest.fixture
def sample_art():
    return {
        "HTNK": {"Voxel": "yes", "Remapable": "yes"},
        "MTNK": {"Voxel": "yes"},
        "E1": {"Sequence": "InfantrySequence"},
        "GAWEAP": {"Foundation": "3x3"},
    }


@pytest.fixture
def sample_strings():
    return {
        "Name:HTNK": "Apocalypse Tank",
        "Name:MTNK": "Rhino Tank",
        "Name:E1": "Conscript",
        "Name:GAWEAP": "War Factory",
        "Name:ORCA": "Harrier",
    }


@pytest.fixture
def db(sample_rules, sample_art, sample_strings):
    return build_index(sample_rules, sample_art, sample_strings)


def test_build_index_creates_objects(db):
    vehicles = list_objects(db, "VehicleTypes")
    assert len(vehicles) == 2
    ids = {v["id"] for v in vehicles}
    assert "HTNK" in ids
    assert "MTNK" in ids


def test_list_objects_returns_display_name(db):
    vehicles = list_objects(db, "VehicleTypes")
    htnk = next(v for v in vehicles if v["id"] == "HTNK")
    assert htnk["display_name"] == "Apocalypse Tank"


def test_list_objects_returns_side(db):
    vehicles = list_objects(db, "VehicleTypes")
    htnk = next(v for v in vehicles if v["id"] == "HTNK")
    # Owner "Russians,Cubans" -> both Soviet
    assert "Soviet" in htnk["side"]


def test_get_object_returns_full_detail(db):
    obj = get_object(db, "HTNK")
    assert obj is not None
    assert obj["id"] == "HTNK"
    assert obj["props"]["Strength"] == "600"
    assert obj["props"]["Cost"] == "1750"


def test_get_object_includes_art(db):
    obj = get_object(db, "HTNK")
    assert obj["art"]["Voxel"] == "yes"


def test_get_object_missing_returns_none(db):
    assert get_object(db, "NONEXISTENT") is None


def test_search_objects(db):
    results = search_objects(db, "tank")
    ids = {r["id"] for r in results}
    assert "HTNK" in ids
    assert "MTNK" in ids


def test_search_objects_no_match(db):
    results = search_objects(db, "zzzzzzz")
    assert len(results) == 0


def test_infantry_indexed(db):
    infantry = list_objects(db, "InfantryTypes")
    assert len(infantry) == 1
    assert infantry[0]["id"] == "E1"


def test_building_indexed(db):
    buildings = list_objects(db, "BuildingTypes")
    assert len(buildings) == 1
    assert buildings[0]["id"] == "GAWEAP"


def test_aircraft_indexed(db):
    aircraft = list_objects(db, "AircraftTypes")
    assert len(aircraft) == 1
    assert aircraft[0]["id"] == "ORCA"
