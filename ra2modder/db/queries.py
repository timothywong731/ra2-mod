import json
import sqlite3


def list_objects(
    conn: sqlite3.Connection,
    obj_type: str,
    side: str | None = None,
    tech_min: int | None = None,
) -> list[dict]:
    """List all objects of a given type with optional side/tech filters."""
    sql = "SELECT id, type, display_name, side, tech_level FROM objects WHERE type = ?"
    params: list = [obj_type]
    if side:
        sql += " AND side LIKE ?"
        params.append(f"%{side}%")
    if tech_min is not None:
        sql += " AND tech_level >= ?"
        params.append(tech_min)
    sql += " ORDER BY display_name"
    rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def get_distinct_sides(conn: sqlite3.Connection, obj_type: str) -> list[str]:
    """Return sorted unique individual side names for a given object type."""
    rows = conn.execute(
        "SELECT DISTINCT side FROM objects WHERE type = ? AND side != ''",
        (obj_type,),
    ).fetchall()
    sides: set[str] = set()
    for row in rows:
        for s in row[0].split(","):
            s = s.strip()
            if s:
                sides.add(s)
    return sorted(sides)


def get_object(conn: sqlite3.Connection, obj_id: str) -> dict | None:
    """Get full details of a single object."""
    row = conn.execute(
        "SELECT id, type, display_name, side, props, art FROM objects WHERE id = ?",
        (obj_id,),
    ).fetchone()
    if row is None:
        return None
    d = dict(row)
    d["props"] = json.loads(d["props"])
    d["art"] = json.loads(d["art"])
    return d


def search_objects(conn: sqlite3.Connection, query: str) -> list[dict]:
    """Search objects by display name or ID (case-insensitive)."""
    pattern = f"%{query}%"
    rows = conn.execute(
        """SELECT id, type, display_name, side, tech_level FROM objects
           WHERE display_name LIKE ? COLLATE NOCASE
              OR id LIKE ? COLLATE NOCASE
           ORDER BY display_name
           LIMIT 100""",
        (pattern, pattern),
    ).fetchall()
    return [dict(r) for r in rows]
