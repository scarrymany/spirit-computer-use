from __future__ import annotations

import argparse
import base64
import json
import platform
import sys
from importlib.metadata import version
from pathlib import Path

from . import __version__
from .config import CLIENTS, generate_config


def emit(value) -> None:
    print(json.dumps(value, ensure_ascii=False), flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="spirit", description="SPIRIT Computer Use for Windows 11"
    )
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)
    serve = sub.add_parser("serve", help="Run the local MCP server over stdio")
    serve.add_argument(
        "--no-overlay", action="store_true", help="Hide visuals; emergency stop remains"
    )
    config = sub.add_parser(
        "config", help="Print a configuration snippet without editing client files"
    )
    config.add_argument("client", choices=CLIENTS)
    config.add_argument("--python", dest="python_path")
    sub.add_parser("doctor", help="Check runtime dependencies and desktop access")
    sub.add_parser("windows", help="Print currently visible window identities as JSON")
    session = sub.add_parser(
        "session", help="Persistent JSON-lines CLI; one operation per input line"
    )
    session.add_argument("--no-overlay", action="store_true")
    capture = sub.add_parser("capture", help="Capture a selected HWND into a PNG file")
    capture.add_argument("window_id", type=int)
    capture.add_argument("output", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "config":
            print(generate_config(args.client, args.python_path), end="")
            return 0
        if args.command == "serve":
            from .server import create_server

            create_server(overlay=not args.no_overlay).run(transport="stdio")
            return 0
        from .controller import Controller

        with Controller(overlay=not getattr(args, "no_overlay", False)) as controller:
            if args.command == "doctor":
                from . import native

                native.initialize()
                native.ensure_desktop()
                emit(
                    {
                        "version": __version__,
                        "python": sys.version.split()[0],
                        "windows": platform.version(),
                        "executable": sys.executable,
                        "dependencies": {
                            name: version(name)
                            for name in ("mcp", "windows-capture", "pywinauto", "Pillow")
                        },
                        "engine": controller.call("status"),
                    }
                )
            elif args.command == "windows":
                emit(controller.call("list_windows"))
            elif args.command == "capture":
                window = controller.call("get_window", id=args.window_id)
                state = controller.call("get_window_state", window=window)
                # Refuse overwrite so a diagnostic command cannot destroy an existing file.
                with args.output.open("xb") as output:
                    output.write(state.pop("png"))
                state["file"] = str(args.output.resolve())
                emit(state)
            elif args.command == "session":
                for line in sys.stdin:
                    try:
                        request = json.loads(line)
                        result = controller.call(
                            request["operation"], **request.get("arguments", {})
                        )
                        if isinstance(result, dict) and "png" in result:
                            result["image_base64"] = base64.b64encode(result.pop("png")).decode(
                                "ascii"
                            )
                        emit({"ok": True, "result": result})
                    except Exception as error:
                        emit({"ok": False, "error": str(error)})
        return 0
    except Exception as error:
        print(f"SPIRIT: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
