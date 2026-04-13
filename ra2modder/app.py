import os
from pathlib import Path

from flask import Flask

from ra2modder.config import default_config
from ra2modder.mix.loader import load_game_files
from ra2modder.ini.rules import load_rules
from ra2modder.ini.art import load_art
from ra2modder.csf.reader import parse_csf
from ra2modder.db.indexer import build_index


def create_app(game_dir: str) -> Flask:
    """Flask app factory. Loads game data at startup."""
    config = default_config(game_dir)

    # Ensure directories exist
    config.patch_dir.mkdir(parents=True, exist_ok=True)
    config.cache_dir.mkdir(parents=True, exist_ok=True)

    # Load game data
    game_files = load_game_files(config)
    rules = load_rules(game_files, config.patch_dir)
    art = load_art(game_files, config.patch_dir)

    # Load CSF strings from any available CSF file
    strings: dict[str, str] = {}
    for key in game_files:
        if key.lower().endswith(".csf"):
            strings.update(parse_csf(game_files[key]))

    # Build index
    db = build_index(rules, art, strings)

    # Create Flask app
    template_dir = Path(__file__).resolve().parent.parent / "templates"
    static_dir = Path(__file__).resolve().parent.parent / "static"
    app = Flask(
        __name__,
        template_folder=str(template_dir),
        static_folder=str(static_dir),
    )
    app.config["SECRET_KEY"] = os.urandom(24).hex()

    # Store on app for access in routes
    app.config["DB"] = db
    app.config["GAME_CONFIG"] = config
    app.config["GAME_FILES"] = game_files
    app.config["RULES"] = rules
    app.config["ART"] = art
    app.config["STRINGS"] = strings

    # Register blueprints
    from ra2modder.routes.objects import bp as objects_bp
    from ra2modder.routes.sprites import bp as sprites_bp
    from ra2modder.routes.assets import bp as assets_bp
    from ra2modder.routes.patch_view import bp as patch_bp

    app.register_blueprint(objects_bp)
    app.register_blueprint(sprites_bp)
    app.register_blueprint(assets_bp)
    app.register_blueprint(patch_bp)

    return app
