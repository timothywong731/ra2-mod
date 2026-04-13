import io

from flask import Blueprint, current_app, request, send_file
from PIL import Image, ImageDraw

from ra2modder.render.shp import render_shp
from ra2modder.render.vxl import render_vxl, render_vxl_composite
from ra2modder.render.palette import load_palette

bp = Blueprint("sprites", __name__)

_FALLBACK_PALETTE = [(i, i, i) for i in range(256)]

# Faction → RGB colour for placeholder background
_SIDE_COLOURS: list[tuple[str, tuple[int, int, int]]] = [
    ("allied",     (30,  60, 160)),
    ("gdi",        (30,  60, 160)),
    ("soviet",     (160, 30,  30)),
    ("nod",        (160, 30,  30)),
    ("yuri",       (110, 30, 140)),
    ("thirdside",  (110, 30, 140)),
]


def _placeholder(side: str = "") -> io.BytesIO:
    """Return a faction-coloured 60×48 placeholder PNG."""
    side_l = side.lower()
    colour: tuple[int, int, int] = (45, 52, 70)  # default dark
    for key, col in _SIDE_COLOURS:
        if key in side_l:
            colour = col
            break
    img = Image.new("RGBA", (60, 48), (*colour, 210))
    # Accent strip at bottom
    bright = tuple(min(c + 70, 255) for c in colour)
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 44, 59, 47], fill=(*bright, 255))
    out = io.BytesIO()
    img.save(out, format="PNG")
    out.seek(0)
    return out


def _img_to_buf(img: Image.Image) -> io.BytesIO:
    out = io.BytesIO()
    img.save(out, format="PNG")
    out.seek(0)
    return out


@bp.route("/sprites/<obj_id>/cameo.png")
def cameo(obj_id: str):
    """Serve a cameo icon for the given object.

    Resolution order:
    1. Ares CameoPCX= PCX file
    2. art INI Cameo= key → <name>.shp rendered with cameo.pal
    3. Convention fallback → <obj_id>cameo.shp
    4. Faction-coloured placeholder
    """
    game_files = current_app.config["GAME_FILES"]
    art = current_app.config["ART"]
    lower_files = {k.lower(): v for k, v in game_files.items()}
    side = request.args.get("side", "")

    rules = current_app.config["RULES"]
    _image_key, art_section = _resolve_image_key(obj_id, art, rules)

    # --- 1. Explicit CameoPCX (Ares) ---
    pcx_name = art_section.get("CameoPCX", "") or f"{obj_id.lower()}cameo.pcx"
    if not pcx_name.lower().endswith(".pcx"):
        pcx_name += ".pcx"
    if pcx_name.lower() in lower_files:
        try:
            img = Image.open(io.BytesIO(lower_files[pcx_name.lower()]))
            return send_file(_img_to_buf(img.convert("RGBA")), mimetype="image/png")
        except Exception:
            pass

    # Load cameo palette
    pal_data = lower_files.get("cameo.pal")
    palette = load_palette(pal_data) if pal_data else _FALLBACK_PALETTE

    # --- 2. art INI Cameo= key → <name>.shp ---
    cameo_key = art_section.get("Cameo", "")
    if cameo_key:
        shp_name = cameo_key.lower()
        if not shp_name.endswith(".shp"):
            shp_name += ".shp"
        if shp_name in lower_files:
            img = render_shp(lower_files[shp_name], palette, frame_index=0)
            if img.width > 0 and img.height > 0:
                return send_file(_img_to_buf(img), mimetype="image/png")

    # --- 3. Convention: <obj_id>cameo.shp ---
    conv_shp = f"{obj_id.lower()}cameo.shp"
    if conv_shp in lower_files:
        img = render_shp(lower_files[conv_shp], palette, frame_index=0)
        if img.width > 0 and img.height > 0:
            return send_file(_img_to_buf(img), mimetype="image/png")

    # --- 4. Faction-coloured placeholder ---
    return send_file(_placeholder(side), mimetype="image/png")


def _resolve_image_key(obj_id: str, art: dict, rules: dict) -> tuple[str, dict]:
    """Resolve the Image key and art section for an object.

    In RA2 the rules section may redirect via Image= to a different art section.
    """
    rules_section = rules.get(obj_id, rules.get(obj_id.lower(), {}))
    image_key = rules_section.get("Image", obj_id)
    art_section = art.get(image_key, art.get(image_key.lower(),
                  art.get(obj_id, art.get(obj_id.lower(), {}))))
    return image_key, art_section


def get_vxl_modes(obj_id: str, art: dict, rules: dict, game_files: dict,
                   obj_type: str = "") -> list[tuple[str, str]]:
    """Return available preview modes for an object as (mode_id, label) tuples.

    Checks VXL first, then falls back to SHP for infantry/buildings.
    """
    lower_keys = {k.lower() for k in game_files}
    image_key, art_section = _resolve_image_key(obj_id, art, rules)
    base = image_key.lower()

    # --- VXL modes ---
    if f"{base}.vxl" in lower_keys:
        has_turret = f"{base}tur.vxl" in lower_keys
        has_barrel = f"{base}barl.vxl" in lower_keys

        modes: list[tuple[str, str]] = []
        if has_turret or has_barrel:
            modes.append(("composite", "Full"))
        modes.append(("base", "Body"))
        if has_turret:
            modes.append(("turret", "Turret"))
        if has_barrel:
            modes.append(("barrel", "Barrel"))

        deployed_img = art_section.get("DeployedImage", "")
        if deployed_img and f"{deployed_img.lower()}.vxl" in lower_keys:
            modes.append(("deployed", "Deployed"))
        elif f"{base}d.vxl" in lower_keys:
            modes.append(("deployed", "Deployed"))

        return modes

    # --- SHP fallback ---
    if f"{base}.shp" in lower_keys:
        if obj_type == "InfantryTypes":
            return [("shp_stand", "Stand")]
        elif obj_type == "BuildingTypes":
            return [("shp_building", "Building")]

    return []


def _resolve_vxl_names(obj_id: str, art: dict, rules: dict, lower_files: dict, mode: str) -> tuple[str, str]:
    """Return (vxl_filename, hva_filename) for the given mode."""
    image_key, art_section = _resolve_image_key(obj_id, art, rules)
    base = image_key.lower()

    if mode == "turret":
        return f"{base}tur.vxl", f"{base}tur.hva"
    elif mode == "barrel":
        return f"{base}barl.vxl", f"{base}barl.hva"
    elif mode == "deployed":
        deployed_img = art_section.get("DeployedImage", "")
        if deployed_img and f"{deployed_img.lower()}.vxl" in lower_files:
            dep = deployed_img.lower()
            return f"{dep}.vxl", f"{dep}.hva"
        return f"{base}d.vxl", f"{base}d.hva"
    else:
        return f"{base}.vxl", f"{base}.hva"


@bp.route("/sprites/<obj_id>/vxl.png")
def vxl_preview(obj_id: str):
    """Serve a VXL or SHP render for the given object.

    Query params:
      facing: 0-7 (default 4 = SE)
      mode: base|turret|barrel|deployed|composite|shp_stand|shp_building
    """
    game_files = current_app.config["GAME_FILES"]
    art = current_app.config["ART"]
    rules = current_app.config["RULES"]
    lower_files = {k.lower(): v for k, v in game_files.items()}

    facing = request.args.get("facing", "4")
    facing = int(facing) if facing.isdigit() and 0 <= int(facing) <= 7 else 4
    mode = request.args.get("mode", "base")

    # --- SHP modes ---
    if mode.startswith("shp_"):
        return _serve_shp_preview(obj_id, art, rules, lower_files, facing, mode)

    # --- VXL modes ---
    # Load unit palette
    pal_data = lower_files.get("unittem.pal") or lower_files.get("unit.pal")
    palette = load_palette(pal_data) if pal_data else _FALLBACK_PALETTE

    if mode == "composite":
        image_key, _art_sec = _resolve_image_key(obj_id, art, rules)
        base = image_key.lower()
        body_data = lower_files.get(f"{base}.vxl")
        if body_data is None:
            return send_file(_placeholder(), mimetype="image/png")

        # Determine body Z height for turret offset
        from ra2modder.render.vxl import _parse_vxl
        body_sections = _parse_vxl(body_data)
        body_z = max((s["z_size"] for s in body_sections), default=0)
        turret_z_off = body_z * 0.35

        parts: list[tuple[bytes, float]] = [(body_data, 0.0)]
        tur_data = lower_files.get(f"{base}tur.vxl")
        if tur_data:
            parts.append((tur_data, turret_z_off))
        barl_data = lower_files.get(f"{base}barl.vxl")
        if barl_data:
            parts.append((barl_data, turret_z_off))

        img = render_vxl_composite(parts, palette, facing=facing)
        return send_file(_img_to_buf(img), mimetype="image/png")

    vxl_name, hva_name = _resolve_vxl_names(obj_id, art, rules, lower_files, mode)

    vxl_data = lower_files.get(vxl_name)
    if vxl_data is None:
        return send_file(_placeholder(), mimetype="image/png")

    hva_data = lower_files.get(hva_name)
    img = render_vxl(vxl_data, hva_data, palette, facing=facing)
    return send_file(_img_to_buf(img), mimetype="image/png")


def _serve_shp_preview(
    obj_id: str, art: dict, rules: dict, lower_files: dict,
    facing: int, mode: str,
):
    """Serve an SHP-rendered preview for infantry or buildings."""
    image_key, art_section = _resolve_image_key(obj_id, art, rules)
    base = image_key.lower()
    shp_data = lower_files.get(f"{base}.shp")
    if shp_data is None:
        return send_file(_placeholder(), mimetype="image/png")

    if mode == "shp_stand":
        # Infantry standing frame: parse Sequence to find Ready start frame
        pal_data = lower_files.get("unittem.pal") or lower_files.get("unit.pal")
        palette = load_palette(pal_data) if pal_data else _FALLBACK_PALETTE
        start_frame, frames_per_facing = _get_infantry_ready_info(art_section, art)
        frame_index = start_frame + facing * frames_per_facing
        img = render_shp(shp_data, palette, frame_index=frame_index)
    elif mode == "shp_building":
        # Building: render frame 0, use isometric palette
        pal_data = (lower_files.get("isotem.pal")
                    or lower_files.get("temperat.pal")
                    or lower_files.get("unittem.pal")
                    or lower_files.get("unit.pal"))
        palette = load_palette(pal_data) if pal_data else _FALLBACK_PALETTE
        img = render_shp(shp_data, palette, frame_index=0)
    else:
        return send_file(_placeholder(), mimetype="image/png")

    return send_file(_img_to_buf(img), mimetype="image/png")


def _get_infantry_ready_info(art_section: dict, art: dict) -> tuple[int, int]:
    """Parse the infantry sequence to find the Ready (standing) start frame and frames-per-facing.

    Returns (start_frame, frames_per_facing). Defaults to (0, 1).
    """
    seq_name = art_section.get("Sequence", "")
    if seq_name:
        seq_data = art.get(seq_name, art.get(seq_name.lower(), {}))
        ready = seq_data.get("Ready", "")
        if ready:
            parts = ready.split(",")
            try:
                start = int(parts[0])
                fcount = int(parts[1]) if len(parts) > 1 else 1
                return start, fcount
            except (ValueError, IndexError):
                pass
    return 0, 1
