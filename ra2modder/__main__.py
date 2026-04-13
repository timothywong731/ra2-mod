import argparse

from ra2modder.app import create_app


def main() -> None:
    parser = argparse.ArgumentParser(description="RA2 Modder web UI")
    parser.add_argument("--game-dir", required=True, help="Path to game directory")
    parser.add_argument("--port", type=int, default=5000)
    args = parser.parse_args()
    app = create_app(args.game_dir)
    app.run(debug=True, port=args.port, use_reloader=False)


if __name__ == "__main__":
    main()
