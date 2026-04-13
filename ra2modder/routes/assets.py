import os

from flask import Blueprint, render_template, current_app

bp = Blueprint("assets", __name__)


@bp.route("/assets")
def asset_list():
    """Browse all files extracted from MIX archives."""
    game_files = current_app.config["GAME_FILES"]

    # Group by extension
    by_ext: dict[str, list[tuple[str, int]]] = {}
    for name, data in sorted(game_files.items()):
        ext = os.path.splitext(name)[1].lower() or "(none)"
        by_ext.setdefault(ext, []).append((name, len(data)))

    return render_template(
        "pages/assets.html",
        by_ext=by_ext,
        total=len(game_files),
    )
