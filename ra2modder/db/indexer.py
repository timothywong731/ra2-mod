import json
import sqlite3


# Object types that correspond to registry sections in rules INI
OBJECT_TYPES = [
    "VehicleTypes",
    "InfantryTypes",
    "AircraftTypes",
    "BuildingTypes",
    "WeaponTypes",
    "Warheads",
    "Projectiles",
    "SuperWeaponTypes",
]


def build_index(
    rules: dict[str, dict[str, str]],
    art: dict[str, dict[str, str]],
    strings: dict[str, str],
) -> sqlite3.Connection:
    """Build an in-memory SQLite index of all game objects."""
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=OFF")

    conn.execute("""
        CREATE TABLE objects (
            id TEXT PRIMARY KEY,
            type TEXT NOT NULL,
            display_name TEXT NOT NULL,
            side TEXT NOT NULL DEFAULT '',
            tech_level INTEGER NOT NULL DEFAULT 0,
            props TEXT NOT NULL DEFAULT '{}',
            art TEXT NOT NULL DEFAULT '{}'
        )
    """)
    conn.execute("CREATE INDEX idx_type ON objects(type)")
    conn.execute(
        "CREATE INDEX idx_name ON objects(display_name COLLATE NOCASE)"
    )
    conn.execute("CREATE INDEX idx_tech ON objects(tech_level)")

    side_map = _resolve_sides(rules)

    for obj_type in OBJECT_TYPES:
        registry = rules.get(obj_type, {})
        for _idx, obj_id in registry.items():
            obj_section = rules.get(obj_id, {})
            image_key = obj_section.get("Image", obj_id)
            art_section = art.get(image_key, art.get(obj_id, {}))

            # Resolve display name from CSF
            name_key = obj_section.get("Name", "")
            display_name = strings.get(name_key, obj_id)

            # Resolve side from Owner
            side = _resolve_object_side(obj_section.get("Owner", ""), side_map)

            try:
                tech_level = int(obj_section.get("TechLevel", "0"))
            except ValueError:
                tech_level = 0

            conn.execute(
                "INSERT OR REPLACE INTO objects VALUES (?,?,?,?,?,?,?)",
                (
                    obj_id,
                    obj_type,
                    display_name,
                    side,
                    tech_level,
                    json.dumps(obj_section),
                    json.dumps(art_section),
                ),
            )

    conn.commit()
    return conn


def _resolve_sides(rules: dict[str, dict[str, str]]) -> dict[str, str]:
    """Build country->side mapping from rules data.

    Reads each country's Side= key for the actual faction name.
    """
    side_map: dict[str, str] = {}

    # Check each country section for a Side= key
    countries_section = rules.get("Countries", {})
    for _idx, country_id in countries_section.items():
        country_data = rules.get(country_id, {})
        side = country_data.get("Side", "")
        if side:
            side_map[country_id] = side

    return side_map


def _resolve_object_side(owner_str: str, side_map: dict[str, str]) -> str:
    """Resolve an object's side(s) from its Owner= value."""
    if not owner_str:
        return ""

    sides = set()
    for owner in owner_str.split(","):
        owner = owner.strip()
        side = side_map.get(owner, "")
        if side:
            sides.add(side)

    return ",".join(sorted(sides))
