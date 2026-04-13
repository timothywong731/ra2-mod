import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from ra2modder.app import create_app


@pytest.fixture
def app(tmp_path):
    """Create app with a minimal fake game directory."""
    game_dir = tmp_path / "game"
    game_dir.mkdir()

    # Create fake game files: a minimal rules and art INI
    rules_ini = (
        b"[VehicleTypes]\n0=HTNK\n"
        b"[HTNK]\nName=Name:HTNK\nStrength=600\nCost=1750\n"
        b"[InfantryTypes]\n0=E1\n"
        b"[E1]\nName=Name:E1\nImage=GI\nStrength=125\n"
        b"[BuildingTypes]\n0=GAPOWR\n"
        b"[GAPOWR]\nName=Name:GAPOWR\nStrength=750\n"
        b"[Sides]\n0=Americans\n1=Russians\n"
        b"[Countries]\n0=Americans\n1=Russians\n"
        b"[Americans]\nSide=Allied\n"
        b"[Russians]\nSide=Soviet\n"
    )
    art_ini = (
        b"[HTNK]\nVoxel=yes\n"
        b"[GI]\nSequence=GISequence\n"
        b"[GISequence]\nReady=0,1,1\n"
        b"[GAPOWR]\n"
    )

    fake_files = {
        "rulesmd.ini": rules_ini,
        "artmd.ini": art_ini,
    }

    with patch("ra2modder.mix.loader.ra2mix") as mock_ra2mix:
        mock_ra2mix.read.return_value = {}
        # Put the fake files as loose INI files in game dir
        (game_dir / "rulesmd.ini").write_bytes(rules_ini)
        (game_dir / "artmd.ini").write_bytes(art_ini)

        application = create_app(str(game_dir))
        application.config["TESTING"] = True

    return application


@pytest.fixture
def client(app):
    return app.test_client()


def test_index_page(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"RA2 Modder" in resp.data


def test_object_list(client):
    resp = client.get("/VehicleTypes")
    assert resp.status_code == 200
    assert b"HTNK" in resp.data


def test_object_detail(client):
    resp = client.get("/VehicleTypes/HTNK")
    assert resp.status_code == 200
    assert b"600" in resp.data  # Strength
    assert b"1750" in resp.data  # Cost


def test_object_detail_htmx(client):
    resp = client.get("/VehicleTypes/HTNK", headers={"HX-Request": "true"})
    assert resp.status_code == 200
    assert b"Strength" in resp.data


def test_object_not_found(client):
    resp = client.get("/VehicleTypes/NONEXIST")
    assert resp.status_code == 404


def test_search(client):
    resp = client.get("/VehicleTypes?q=HTNK", headers={"HX-Request": "true"})
    assert resp.status_code == 200
    assert b"HTNK" in resp.data


def test_cameo_returns_png(client):
    resp = client.get("/sprites/HTNK/cameo.png")
    assert resp.status_code == 200
    assert resp.content_type == "image/png"


def test_assets_page(client):
    resp = client.get("/assets")
    assert resp.status_code == 200


def test_patch_page(client):
    resp = client.get("/patch")
    assert resp.status_code == 200
    assert b"Pending Changes" in resp.data


def test_patch_export_empty(client):
    resp = client.get("/patch/export")
    assert resp.status_code == 200


def test_vxl_preview_returns_png(client):
    """VXL preview route returns a PNG even without VXL data (placeholder)."""
    resp = client.get("/sprites/HTNK/vxl.png")
    assert resp.status_code == 200
    assert resp.content_type == "image/png"


def test_vxl_preview_mode_param(client):
    """VXL preview accepts mode parameter without error."""
    resp = client.get("/sprites/HTNK/vxl.png?facing=2&mode=turret")
    assert resp.status_code == 200
    assert resp.content_type == "image/png"


def test_detail_shows_vxl_modes(client, app):
    """Detail includes vxl_modes in context when VXL exists."""
    # Add a fake VXL file to game_files
    with app.app_context():
        app.config["GAME_FILES"]["htnk.vxl"] = b"fakedata"
    resp = client.get("/VehicleTypes/HTNK", headers={"HX-Request": "true"})
    assert resp.status_code == 200
    # The template should contain the compass grid markup
    assert b"vxl-compass" in resp.data


def test_reindex_redirects(client):
    """POST /reindex rebuilds the DB and redirects to /."""
    resp = client.post("/reindex")
    assert resp.status_code == 302


def test_reindex_htmx(client):
    """POST /reindex with HTMX returns HX-Redirect header."""
    resp = client.post("/reindex", headers={"HX-Request": "true"})
    assert resp.status_code == 200
    assert resp.headers.get("HX-Redirect") == "/"


def test_reindex_preserves_data(client):
    """After reindex, objects are still queryable."""
    client.post("/reindex")
    resp = client.get("/VehicleTypes")
    assert resp.status_code == 200
    assert b"HTNK" in resp.data


def test_shp_infantry_preview(client, app):
    """SHP infantry preview returns a PNG."""
    import struct
    # Create a minimal SHP file: 8 frames (one per facing), 4x4 pixels
    n_frames = 8
    header = struct.pack("<4H", 0, 4, 4, n_frames)
    frame_infos = b""
    for i in range(n_frames):
        # Each frame: fx=0, fy=0, fw=4, fh=4, flags=0, color=0, res=0, offset=0
        frame_infos += struct.pack("<4H", 0, 0, 4, 4)
        frame_infos += struct.pack("<I", 0)  # flags
        frame_infos += b"\x00" * 4  # color
        frame_infos += struct.pack("<I", 0)  # reserved
        frame_infos += struct.pack("<I", 0)  # data_offset (0 = empty)
    shp_data = header + frame_infos
    with app.app_context():
        app.config["GAME_FILES"]["gi.shp"] = shp_data
    resp = client.get("/sprites/E1/vxl.png?facing=0&mode=shp_stand")
    assert resp.status_code == 200
    assert resp.content_type == "image/png"


def test_shp_building_preview(client, app):
    """SHP building preview returns a PNG."""
    import struct
    header = struct.pack("<4H", 0, 20, 20, 1)
    frame_info = struct.pack("<4H", 0, 0, 20, 20)
    frame_info += struct.pack("<I", 0)
    frame_info += b"\x00" * 4
    frame_info += struct.pack("<I", 0)
    frame_info += struct.pack("<I", 0)
    shp_data = header + frame_info
    with app.app_context():
        app.config["GAME_FILES"]["gapowr.shp"] = shp_data
    resp = client.get("/sprites/GAPOWR/vxl.png?mode=shp_building")
    assert resp.status_code == 200
    assert resp.content_type == "image/png"


def test_detail_shows_infantry_compass(client, app):
    """Infantry detail with SHP shows compass grid."""
    import struct
    header = struct.pack("<4H", 0, 4, 4, 8)
    frame_infos = b""
    for i in range(8):
        frame_infos += struct.pack("<4H", 0, 0, 4, 4)
        frame_infos += struct.pack("<I", 0)
        frame_infos += b"\x00" * 4
        frame_infos += struct.pack("<I", 0)
        frame_infos += struct.pack("<I", 0)
    shp_data = header + frame_infos
    with app.app_context():
        app.config["GAME_FILES"]["gi.shp"] = shp_data
    resp = client.get("/InfantryTypes/E1", headers={"HX-Request": "true"})
    assert resp.status_code == 200
    assert b"vxl-compass" in resp.data


def test_detail_shows_building_preview(client, app):
    """Building detail with SHP shows building preview."""
    import struct
    header = struct.pack("<4H", 0, 20, 20, 1)
    frame_info = struct.pack("<4H", 0, 0, 20, 20)
    frame_info += struct.pack("<I", 0)
    frame_info += b"\x00" * 4
    frame_info += struct.pack("<I", 0)
    frame_info += struct.pack("<I", 0)
    shp_data = header + frame_info
    with app.app_context():
        app.config["GAME_FILES"]["gapowr.shp"] = shp_data
    resp = client.get("/BuildingTypes/GAPOWR", headers={"HX-Request": "true"})
    assert resp.status_code == 200
    assert b"vxl-building-preview" in resp.data
