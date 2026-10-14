from __future__ import annotations

import argparse
import asyncio
import json
import platform
import sys
from importlib.metadata import version
from pathlib import Path

from . import __version__
from .config import CLIENTS, generate_config


def main() -> int:
    parser = argparse.ArgumentParser(prog="spirit", description="SPIRIT Browser for Windows 11")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)
    serve = sub.add_parser("serve", help="Run browser MCP over stdio")
    serve.add_argument("--browser-mode", choices=["auto", "extension", "cdp"], default="auto")
    serve.add_argument("--cdp-endpoint", help="Explicit loopback browser WebSocket endpoint")
    config = sub.add_parser("config", help="Print a client configuration snippet")
    config.add_argument("client", choices=CLIENTS)
    config.add_argument("--python", dest="python_path")
    sub.add_parser("doctor", help="Check browser runtime and extension setup")
    sub.add_parser("browser-bridge", help="Run the shared loopback extension bridge")
    setup = sub.add_parser("browser-setup", help="Prepare the unpacked Chrome extension")
    setup.add_argument(
        "--source",
        type=Path,
        default=(
            Path(__file__).parent / "extension"
            if (Path(__file__).parent / "extension").is_dir()
            else Path(__file__).resolve().parents[2] / "extension"
        ),
    )
    setup.add_argument("--destination", type=Path, help="Directory to load in Chrome")
    args = parser.parse_args()
    try:
        if args.command == "config":
            print(generate_config(args.client, args.python_path), end="")
        elif args.command == "serve":
            from .server import create_server

            create_server(browser_mode=args.browser_mode, endpoint=args.cdp_endpoint).run(
                transport="stdio"
            )
        elif args.command == "browser-bridge":
            from .browser_bridge import run_bridge

            asyncio.run(run_bridge())
        elif args.command == "browser-setup":
            from .browser_bridge import connect_bridge, install_extension

            async def start():
                client = await connect_bridge()
                await client.close()

            asyncio.run(start())
            destination = install_extension(args.source, args.destination)
            print(
                json.dumps(
                    {
                        "extension": str(destination),
                        ("next"): (
                            "Open chrome://extensions, enable Developer mode, Load unpack"
                            "ed and select this folder."
                        ),
                    }
                )
            )
        elif args.command == "doctor":
            from .browser_bridge import settings_path

            print(
                json.dumps(
                    {
                        "version": __version__,
                        "python": sys.version.split()[0],
                        "windows": platform.version(),
                        "executable": sys.executable,
                        "dependencies": {
                            name: version(name) for name in ("mcp", "websockets", "Pillow")
                        },
                        "extension_prepared": (
                            settings_path().parent / "extension/manifest.json"
                        ).is_file(),
                        "desktop_control": False,
                    }
                )
            )
        return 0
    except Exception as error:
        print(f"SPIRIT: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
