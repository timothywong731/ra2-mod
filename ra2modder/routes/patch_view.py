from flask import Blueprint, render_template, current_app, Response

from ra2modder.patch.manager import get_diff
from ra2modder.patch.writer import serialise_patch

bp = Blueprint("patch", __name__)


@bp.route("/patch")
def patch_view():
    """View all pending patch changes."""
    config = current_app.config["GAME_CONFIG"]
    diff = get_diff(config.patch_dir)
    return render_template("pages/patch.html", diff=diff)


@bp.route("/patch/export")
def patch_export():
    """Download the patch as an INI file."""
    config = current_app.config["GAME_CONFIG"]
    diff = get_diff(config.patch_dir)
    text = serialise_patch(diff)
    return Response(
        text,
        mimetype="text/plain",
        headers={"Content-Disposition": "attachment; filename=rulesmd.ini"},
    )
