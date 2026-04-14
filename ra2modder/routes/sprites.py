import io
import struct

from flask import Blueprint, current_app, request, send_file
from PIL import Image, ImageDraw

from ra2modder.render.shp import render_shp, shp_frame_is_empty, find_first_nonempty_frame, render_shp_frames, shp_frame_count
from ra2modder.render.vxl import render_vxl, render_vxl_composite
from ra2modder.render.palette import load_palette, remap_player_colors

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

    # --- 2. art INI Cameo= key → try PCX then SHP ---
    cameo_key = art_section.get("Cameo", "")
    if cameo_key:
        base_name = cameo_key.lower()
        # Try PCX first (common in RA2/YR)
        pcx_try = base_name if base_name.endswith(".pcx") else base_name + ".pcx"
        if pcx_try in lower_files:
            try:
                img = Image.open(io.BytesIO(lower_files[pcx_try]))
                return send_file(_img_to_buf(img.convert("RGBA")), mimetype="image/png")
            except Exception:
                pass
        # Then SHP
        shp_name = base_name if base_name.endswith(".shp") else base_name + ".shp"
        if shp_name in lower_files:
            img = render_shp(lower_files[shp_name], palette, frame_index=0)
            if img.width > 0 and img.height > 0:
                return send_file(_img_to_buf(img), mimetype="image/png")

    # --- 3. Convention: <obj_id>cameo → try PCX then SHP ---
    conv_pcx = f"{obj_id.lower()}cameo.pcx"
    if conv_pcx in lower_files:
        try:
            img = Image.open(io.BytesIO(lower_files[conv_pcx]))
            return send_file(_img_to_buf(img.convert("RGBA")), mimetype="image/png")
        except Exception:
            pass
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
    lower_files = {k.lower(): v for k, v in game_files.items()}
    image_key, art_section = _resolve_image_key(obj_id, art, rules)
    base = image_key.lower()

    # --- VXL modes ---
    if f"{base}.vxl" in lower_files:
        has_turret = f"{base}tur.vxl" in lower_files
        has_barrel = f"{base}barl.vxl" in lower_files

        modes: list[tuple[str, str]] = []
        if has_turret or has_barrel:
            modes.append(("composite", "Full"))
        modes.append(("base", "Body"))
        if has_turret:
            modes.append(("turret", "Turret"))
        if has_barrel:
            modes.append(("barrel", "Barrel"))

        deployed_img = art_section.get("DeployedImage", "")
        if deployed_img and f"{deployed_img.lower()}.vxl" in lower_files:
            modes.append(("deployed", "Deployed"))
        elif f"{base}d.vxl" in lower_files:
            modes.append(("deployed", "Deployed"))

        return modes

    # --- SHP fallback ---
    shp_name = f"{base}.shp"
    # NewTheater: try theater-specific SHP first (default temperate 'G')
    if art_section.get("NewTheater", "").lower() in ("yes", "true", "1") and len(base) >= 2:
        theater_name = f"{base[0]}g{base[2:]}.shp"
        candidate = lower_files.get(theater_name)
        if candidate and not shp_frame_is_empty(candidate, 0):
            shp_name = theater_name
    if shp_name in lower_files or f"{base}.shp" in lower_files:
        actual_shp = shp_name if shp_name in lower_files else f"{base}.shp"
        if obj_type == "InfantryTypes":
            return [("shp_stand", "Stand")]
        elif obj_type == "BuildingTypes":
            modes = [("shp_building", "Building")]
            shp_data = lower_files.get(actual_shp)
            if shp_data and len(shp_data) >= 8:
                n_frames = struct.unpack_from("<H", shp_data, 6)[0]
                if n_frames >= 2:
                    modes.append(("shp_building_damaged", "Damaged"))
            # Discover animation overlays from art section
            _ANIM_KEYS = [
                ("ActiveAnim", "Active"),
                ("ActiveAnimTwo", "Active 2"),
                ("ActiveAnimThree", "Active 3"),
                ("ActiveAnimFour", "Active 4"),
                ("IdleAnim", "Idle"),
                ("SuperAnim", "Super"),
                ("SuperAnimTwo", "Super 2"),
                ("SuperAnimThree", "Super 3"),
                ("SuperAnimFour", "Super 4"),
                ("SpecialAnim", "Special"),
                ("SpecialAnimTwo", "Special 2"),
                ("SpecialAnimThree", "Special 3"),
                ("SpecialAnimFour", "Special 4"),
                ("ProductionAnim", "Production"),
                ("Buildup", "Buildup"),
            ]
            for anim_key, anim_label in _ANIM_KEYS:
                anim_name = art_section.get(anim_key, "")
                if anim_name and f"{anim_name.lower()}.shp" in lower_files:
                    modes.append((f"anim_{anim_key}", anim_label))
            return modes

    return []


def get_available_theaters(obj_id: str, art: dict, rules: dict, game_files: dict) -> list[tuple[str, str]]:
    """Return available theater variants for a building as (theater_id, label) tuples.

    Only returns theaters that have a corresponding SHP file.
    """
    lower_files = {k.lower(): v for k, v in game_files.items()}
    image_key, art_section = _resolve_image_key(obj_id, art, rules)
    base = image_key.lower()

    if art_section.get("NewTheater", "").lower() not in ("yes", "true", "1"):
        return []
    if len(base) < 2:
        return []

    theaters = []
    _THEATERS = [
        ("temperate", "Temperate", "g"),
        ("snow", "Snow", "a"),
        ("urban", "Urban", "u"),
        ("newurban", "New Urban", "n"),
        ("lunar", "Lunar", "l"),
        ("desert", "Desert", "d"),
    ]
    for tid, label, letter in _THEATERS:
        theater_name = f"{base[0]}{letter}{base[2:]}.shp"
        if theater_name in lower_files:
            theaters.append((tid, label))
    return theaters


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
    side = request.args.get("side", "")
    theater = request.args.get("theater", "temperate")

    # --- SHP modes ---
    if mode.startswith("shp_") or mode.startswith("anim_"):
        return _serve_shp_preview(obj_id, art, rules, lower_files, facing, mode, side, theater)

    # --- VXL modes ---
    # Load unit palette
    pal_data = lower_files.get("unittem.pal") or lower_files.get("unit.pal")
    palette = load_palette(pal_data) if pal_data else _FALLBACK_PALETTE
    palette = remap_player_colors(palette, side)

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


# NewTheater suffix letter per theater
_THEATER_LETTERS = {
    "temperate": "g",
    "snow": "a",
    "urban": "u",
    "newurban": "n",
    "lunar": "l",
    "desert": "d",
}


def _resolve_building_shp(base: str, art_section: dict, lower_files: dict,
                          theater: str, frame_index: int = 0) -> bytes | None:
    """Resolve the best SHP data for a building, handling NewTheater and empty-frame fallback."""
    shp_data = None
    if art_section.get("NewTheater", "").lower() in ("yes", "true", "1") and len(base) >= 2:
        letter = _THEATER_LETTERS.get(theater, "g")
        theater_base = base[0] + letter + base[2:]
        candidate = lower_files.get(f"{theater_base}.shp")
        # Only use theater SHP if it actually has content in the needed frame
        if candidate and not shp_frame_is_empty(candidate, frame_index):
            shp_data = candidate
    if shp_data is None:
        shp_data = lower_files.get(f"{base}.shp")
    return shp_data


def _autocrop(img: Image.Image, padding: int = 4) -> Image.Image:
    """Crop transparent edges from an RGBA image, keeping a small padding."""
    bbox = img.getbbox()
    if bbox is None:
        return img
    x0, y0, x1, y1 = bbox
    x0 = max(0, x0 - padding)
    y0 = max(0, y0 - padding)
    x1 = min(img.width, x1 + padding)
    y1 = min(img.height, y1 + padding)
    return img.crop((x0, y0, x1, y1))


def _building_palette(art_section: dict, lower_files: dict,
                      side: str = "") -> list[tuple[int, int, int]]:
    """Load the appropriate palette for a building."""
    if art_section.get("TerrainPalette", "").lower() in ("yes", "true", "1"):
        pal_data = lower_files.get("isotem.pal") or lower_files.get("iso.pal")
    else:
        pal_data = lower_files.get("unittem.pal") or lower_files.get("unit.pal")
    palette = load_palette(pal_data) if pal_data else _FALLBACK_PALETTE
    return remap_player_colors(palette, side)


# Animation keys whose first frame is composited onto the building's
# "normal" appearance.  Order matters — earlier keys are drawn first.
_ALWAYS_ON_ANIM_KEYS = [
    "ActiveAnim", "ActiveAnimTwo", "ActiveAnimThree", "ActiveAnimFour",
    "IdleAnim",
]


def _resolve_bib_shp(art_section: dict, lower_files: dict,
                     theater: str) -> bytes | None:
    """Return the BibShape SHP data for a building, or None if not defined.

    BibShape SHPs follow the same NewTheater 2nd-character substitution as
    the building itself.
    """
    bib_name = art_section.get("BibShape", "")
    if not bib_name:
        return None
    bib_lower = bib_name.lower()

    # Try theater-specific bib first
    if (art_section.get("NewTheater", "").lower() in ("yes", "true", "1")
            and len(bib_lower) >= 2):
        letter = _THEATER_LETTERS.get(theater, "g")
        theater_bib = f"{bib_lower[0]}{letter}{bib_lower[2:]}.shp"
        data = lower_files.get(theater_bib)
        if data:
            return data

    return lower_files.get(f"{bib_lower}.shp")


def _composite_building_layers(
    base_img: Image.Image,
    art_section: dict,
    lower_files: dict,
    palette: list[tuple[int, int, int]],
    theater: str = "temperate",
    frame_index: int = 0,
    exclude_anim_key: str = "",
) -> Image.Image:
    """Composite all building visual layers: bib → base → always-on anims.

    Returns a complete building image with all static layers applied.
    """
    # 1. BibShape foundation (drawn below the building)
    bib_data = _resolve_bib_shp(art_section, lower_files, theater)
    if bib_data:
        bib_frame = min(frame_index, 1)  # bib has fewer frames; 0=normal, 1=damaged
        bib_img = render_shp(bib_data, palette, frame_index=bib_frame)
        if bib_img.getbbox() is not None:
            composite = bib_img.copy()
            composite.paste(base_img, (0, 0), base_img)
            base_img = composite

    # 2. Always-on animation overlays (ActiveAnim*, IdleAnim)
    for key in _ALWAYS_ON_ANIM_KEYS:
        if key == exclude_anim_key:
            continue
        anim_name = art_section.get(key, "")
        if not anim_name:
            continue
        anim_shp = lower_files.get(f"{anim_name.lower()}.shp")
        if anim_shp is None:
            continue
        frame = render_shp(anim_shp, palette, frame_index=0)
        if frame.getbbox() is not None:
            base_img = base_img.copy()
            base_img.paste(frame, (0, 0), frame)

    return base_img


def _serve_shp_preview(
    obj_id: str, art: dict, rules: dict, lower_files: dict,
    facing: int, mode: str, side: str = "", theater: str = "temperate",
):
    """Serve an SHP-rendered preview for infantry or buildings."""
    image_key, art_section = _resolve_image_key(obj_id, art, rules)
    base = image_key.lower()

    # Determine which frame we need for the building modes
    building_frame = 0
    if mode == "shp_building_damaged":
        building_frame = 1

    # NewTheater: try theater-specific SHP first, with empty-frame fallback
    shp_data = None
    if mode in ("shp_building", "shp_building_damaged") or mode.startswith("anim_"):
        shp_data = _resolve_building_shp(base, art_section, lower_files, theater, building_frame)
    else:
        # Infantry / generic
        if art_section.get("NewTheater", "").lower() in ("yes", "true", "1") and len(base) >= 2:
            letter = _THEATER_LETTERS.get(theater, "g")
            theater_base = base[0] + letter + base[2:]
            shp_data = lower_files.get(f"{theater_base}.shp")
        if shp_data is None:
            shp_data = lower_files.get(f"{base}.shp")
    if shp_data is None:
        return send_file(_placeholder(), mimetype="image/png")

    if mode == "shp_stand":
        # Infantry standing frame: parse Sequence to find Ready start frame
        pal_data = lower_files.get("unittem.pal") or lower_files.get("unit.pal")
        palette = load_palette(pal_data) if pal_data else _FALLBACK_PALETTE
        palette = remap_player_colors(palette, side)
        start_frame, frames_per_facing = _get_infantry_ready_info(art_section, art)
        frame_index = start_frame + facing * frames_per_facing
        img = render_shp(shp_data, palette, frame_index=frame_index)
    elif mode in ("shp_building", "shp_building_damaged"):
        # Buildings: use terrain palette if TerrainPalette=yes, otherwise unit palette
        palette = _building_palette(art_section, lower_files, side)
        frame_index = building_frame
        if frame_index > 0 and shp_frame_is_empty(shp_data, frame_index):
            frame_index = 0  # fallback to undamaged if damaged frame is empty
        img = render_shp(shp_data, palette, frame_index=frame_index)

        # Composite all building layers: bib + always-on anims
        img = _composite_building_layers(img, art_section, lower_files, palette,
                                          theater=theater, frame_index=frame_index)
        img = _autocrop(img)
    elif mode.startswith("anim_"):
        # Animation overlay mode — render as animated GIF
        anim_key = mode[5:]  # strip "anim_" prefix
        anim_name = art_section.get(anim_key, "")
        if not anim_name:
            return send_file(_placeholder(), mimetype="image/png")
        anim_shp = lower_files.get(f"{anim_name.lower()}.shp")
        if anim_shp is None:
            return send_file(_placeholder(), mimetype="image/png")

        # Building animations use the same palette as the building itself
        palette = _building_palette(art_section, lower_files, side)

        # Render base building frame 0 + bib + other always-on overlays as background
        base_img = render_shp(shp_data, palette, frame_index=0)
        base_img = _composite_building_layers(base_img, art_section, lower_files, palette,
                                               theater=theater, frame_index=0,
                                               exclude_anim_key=anim_key)

        # Render all animation frames (anim SHPs share the same coordinate space)
        anim_frames = render_shp_frames(anim_shp, palette)
        if not anim_frames:
            return send_file(_img_to_buf(_autocrop(base_img)), mimetype="image/png")

        # Composite each animation frame onto the base building at (0,0)
        gif_frames = []
        for anim_frame in anim_frames:
            composite = base_img.copy()
            composite.paste(anim_frame, (0, 0), anim_frame)
            gif_frames.append(composite)

        # Auto-crop all frames consistently using the union bounding box
        all_bboxes = [f.getbbox() for f in gif_frames]
        valid = [b for b in all_bboxes if b is not None]
        if valid:
            pad = 4
            x0 = max(0, min(b[0] for b in valid) - pad)
            y0 = max(0, min(b[1] for b in valid) - pad)
            x1 = min(gif_frames[0].width, max(b[2] for b in valid) + pad)
            y1 = min(gif_frames[0].height, max(b[3] for b in valid) + pad)
            gif_frames = [f.crop((x0, y0, x1, y1)) for f in gif_frames]

        if len(gif_frames) == 1:
            return send_file(_img_to_buf(gif_frames[0]), mimetype="image/png")

        # Encode as animated GIF
        out = io.BytesIO()
        gif_frames[0].save(
            out, format="GIF", save_all=True,
            append_images=gif_frames[1:],
            duration=100, loop=0, transparency=0,
            disposal=2,
        )
        out.seek(0)
        return send_file(out, mimetype="image/gif")
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
