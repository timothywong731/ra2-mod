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


def get_prerequisites(conn: sqlite3.Connection, obj_id: str) -> list[dict]:
    """Return prerequisite objects for a given object.

    Reads the Prerequisite CSV field from the object's props JSON.
    Returns list of dicts with id, type, display_name, side.
    """
    obj = get_object(conn, obj_id)
    if obj is None:
        return []
    prereq_str = obj["props"].get("Prerequisite", "")
    if not prereq_str:
        return []
    prereq_ids = [p.strip() for p in prereq_str.split(",") if p.strip()]
    results = []
    for pid in prereq_ids:
        row = conn.execute(
            "SELECT id, type, display_name, side FROM objects WHERE id = ?",
            (pid,),
        ).fetchone()
        if row:
            results.append(dict(row))
    return results


def get_dependents(conn: sqlite3.Connection, obj_id: str) -> list[dict]:
    """Return objects that list *obj_id* as a prerequisite.

    Scans all objects whose props JSON Prerequisite field contains obj_id.
    """
    # Use SQL LIKE to find objects with this ID in their Prerequisite field
    pattern = f'%"{obj_id}"%'
    # Prerequisite is stored inside the props JSON string, so we search the raw JSON
    rows = conn.execute(
        """SELECT id, type, display_name, side FROM objects
           WHERE props LIKE ?
           ORDER BY display_name""",
        (pattern,),
    ).fetchall()
    # Filter precisely: the LIKE above may match other fields, so verify
    results = []
    for row in rows:
        d = dict(row)
        full = get_object(conn, d["id"])
        if full:
            prereqs = full["props"].get("Prerequisite", "")
            prereq_ids = [p.strip() for p in prereqs.split(",")]
            if obj_id in prereq_ids:
                results.append(d)
    return results


def get_tech_tree(
    conn: sqlite3.Connection,
    obj_id: str,
    type_filter: list[str] | None = None,
) -> dict:
    """Build a prerequisite tree rooted at *obj_id*.

    Returns a dict with:
      - "object": the root object info
      - "prerequisites": list of prerequisite tree dicts (recursive upstream)
      - "dependents": list of dependent tree dicts (recursive downstream)
    type_filter: if provided, only include objects of these types.
    """
    visited_up: set[str] = set()
    visited_down: set[str] = set()

    def _walk_up(oid: str) -> dict | None:
        if oid in visited_up:
            return None
        visited_up.add(oid)
        row = conn.execute(
            "SELECT id, type, display_name, side FROM objects WHERE id = ?",
            (oid,),
        ).fetchone()
        if row is None:
            return None
        node = dict(row)
        if type_filter and node["type"] not in type_filter:
            return None
        prereqs = get_prerequisites(conn, oid)
        node["prerequisites"] = []
        for p in prereqs:
            child = _walk_up(p["id"])
            if child:
                node["prerequisites"].append(child)
        return node

    def _walk_down(oid: str) -> dict | None:
        if oid in visited_down:
            return None
        visited_down.add(oid)
        row = conn.execute(
            "SELECT id, type, display_name, side FROM objects WHERE id = ?",
            (oid,),
        ).fetchone()
        if row is None:
            return None
        node = dict(row)
        if type_filter and node["type"] not in type_filter:
            return None
        deps = get_dependents(conn, oid)
        node["dependents"] = []
        for d in deps:
            child = _walk_down(d["id"])
            if child:
                node["dependents"].append(child)
        return node

    root_row = conn.execute(
        "SELECT id, type, display_name, side FROM objects WHERE id = ?",
        (obj_id,),
    ).fetchone()
    if root_row is None:
        return {"object": None, "prerequisites": [], "dependents": []}

    root = dict(root_row)
    prereqs = get_prerequisites(conn, obj_id)
    upstream = []
    for p in prereqs:
        node = _walk_up(p["id"])
        if node:
            upstream.append(node)

    dependents = get_dependents(conn, obj_id)
    downstream = []
    for d in dependents:
        node = _walk_down(d["id"])
        if node:
            downstream.append(node)

    return {"object": root, "prerequisites": upstream, "dependents": downstream}
