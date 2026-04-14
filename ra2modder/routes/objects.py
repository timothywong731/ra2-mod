from flask import Blueprint, render_template, request, current_app, jsonify, redirect, url_for

from ra2modder.db.indexer import OBJECT_TYPES, build_index
from ra2modder.db.queries import list_objects, get_object, search_objects, get_distinct_sides, get_tech_tree
from ra2modder.patch.manager import save_field, revert_field
from ra2modder.routes.sprites import get_vxl_modes, get_available_theaters
from ra2modder.ini.rules import load_rules
from ra2modder.ini.art import load_art
from ra2modder.csf.reader import parse_csf

bp = Blueprint("objects", __name__)


@bp.route("/")
def index():
    """Redirect to the first object type."""
    db = current_app.config["DB"]
    obj_type = OBJECT_TYPES[0]
    return render_template(
        "pages/object_list.html",
        object_types=OBJECT_TYPES,
        current_type=obj_type,
        objects=list_objects(db, obj_type),
        available_sides=get_distinct_sides(db, obj_type),
        filter_side="",
        filter_tech_min="0",
        selected=None,
    )


@bp.route("/<obj_type>")
def object_list(obj_type: str):
    """List all objects of a given type."""
    db = current_app.config["DB"]
    q = request.args.get("q", "").strip()
    side = request.args.get("side", "").strip()
    tech_min_raw = request.args.get("tech_min", "0").strip()
    tech_min = int(tech_min_raw) if tech_min_raw.lstrip("-").isdigit() else None
    # Treat tech_min=0 as no filter (all tech levels start at 0)
    if tech_min == 0:
        tech_min = None

    if q:
        objects = search_objects(db, q)
    else:
        objects = list_objects(db, obj_type, side=side or None, tech_min=tech_min)

    available_sides = get_distinct_sides(db, obj_type)

    # HTMX partial?
    if request.headers.get("HX-Request"):
        return render_template(
            "partials/unit_cards.html",
            objects=objects,
            current_type=obj_type,
        )

    return render_template(
        "pages/object_list.html",
        object_types=OBJECT_TYPES,
        current_type=obj_type,
        objects=objects,
        available_sides=available_sides,
        filter_side=side,
        filter_tech_min=tech_min_raw or "0",
        selected=None,
    )


@bp.route("/<obj_type>/<obj_id>")
def object_detail(obj_type: str, obj_id: str):
    """Show object detail (full page or HTMX partial)."""
    db = current_app.config["DB"]
    obj = get_object(db, obj_id)
    if obj is None:
        return "Not found", 404

    config = current_app.config["GAME_CONFIG"]
    vxl_modes = get_vxl_modes(
        obj_id, current_app.config["ART"], current_app.config["RULES"],
        current_app.config["GAME_FILES"], obj_type=obj_type,
    )
    theaters = get_available_theaters(
        obj_id, current_app.config["ART"], current_app.config["RULES"],
        current_app.config["GAME_FILES"],
    )

    if request.headers.get("HX-Request"):
        return render_template(
            "partials/detail_tabs.html",
            obj=obj,
            mod_type=config.mod_type,
            vxl_modes=vxl_modes,
            theaters=theaters,
        )

    objects = list_objects(db, obj_type)
    return render_template(
        "pages/object_list.html",
        object_types=OBJECT_TYPES,
        current_type=obj_type,
        objects=objects,
        available_sides=get_distinct_sides(db, obj_type),
        filter_side="",
        filter_tech_min="0",
        selected=obj,
        mod_type=config.mod_type,
        vxl_modes=vxl_modes,
        theaters=theaters,
    )


@bp.route("/edit/<obj_id>/<field>", methods=["POST"])
def edit_field(obj_id: str, field: str):
    """Save an edited field value via HTMX."""
    config = current_app.config["GAME_CONFIG"]
    old_value = request.form.get("old_value", "")
    new_value = request.form.get("new_value", "")

    if old_value != new_value:
        save_field(config.patch_dir, obj_id, field, old_value, new_value)

    return render_template(
        "partials/diff_line.html",
        field=field,
        old_value=old_value,
        new_value=new_value,
        obj_id=obj_id,
    )


@bp.route("/revert/<obj_id>/<field>", methods=["POST"])
def revert(obj_id: str, field: str):
    """Revert a field edit via HTMX."""
    config = current_app.config["GAME_CONFIG"]
    revert_field(config.patch_dir, obj_id, field)
    return "", 200


@bp.route("/reindex", methods=["POST"])
def reindex():
    """Purge the SQLite index and rebuild from game files."""
    config = current_app.config["GAME_CONFIG"]
    game_files = current_app.config["GAME_FILES"]

    # Reload INI data (picks up any new patches)
    rules = load_rules(game_files, config.patch_dir)
    art = load_art(game_files, config.patch_dir)

    strings: dict[str, str] = {}
    for key in game_files:
        if key.lower().endswith(".csf"):
            strings.update(parse_csf(game_files[key]))

    # Close old DB connection
    old_db = current_app.config["DB"]
    old_db.close()

    # Build fresh index
    db = build_index(rules, art, strings)
    current_app.config["DB"] = db
    current_app.config["RULES"] = rules
    current_app.config["ART"] = art
    current_app.config["STRINGS"] = strings

    if request.headers.get("HX-Request"):
        return "", 200, {"HX-Redirect": "/"}
    return redirect("/")


@bp.route("/<obj_type>/<obj_id>/tree")
def tech_tree(obj_type: str, obj_id: str):
    """Return a tech tree partial for HTMX lazy loading."""
    db = current_app.config["DB"]
    # Parse type filter from query params (checkboxes)
    type_filter = request.args.getlist("types") or None
    tree = get_tech_tree(db, obj_id, type_filter=type_filter)
    return render_template(
        "partials/tech_tree.html",
        tree=tree,
        obj_id=obj_id,
        obj_type=obj_type,
        object_types=OBJECT_TYPES,
        selected_types=type_filter or OBJECT_TYPES,
    )
