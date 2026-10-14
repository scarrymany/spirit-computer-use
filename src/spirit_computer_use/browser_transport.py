from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.parse import urlsplit

from .browser_bridge import RpcSocket, connect_bridge


def validate_endpoint(endpoint: str) -> str:
    parsed = urlsplit(endpoint)
    if (
        parsed.scheme != "ws"
        or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or not parsed.port
        or not parsed.path.startswith("/devtools/browser/")
    ):
        raise ValueError("Use a loopback ws:// endpoint ending in /devtools/browser/<id>")
    return endpoint


def chrome_endpoint() -> str:
    path = Path(os.environ["LOCALAPPDATA"]) / "Google/Chrome/User Data/DevToolsActivePort"
    if not path.is_file():
        raise RuntimeError(
            "Chrome remote debugging is off. In your existing Chrome (144+), open "
            "chrome://inspect/#remote-debugging, enable it, then allow the connection "
            "when Chrome asks. Do not relaunch your default profile with debugging flags."
        )
    lines = path.read_text(encoding="ascii").splitlines()
    if len(lines) < 2:
        raise ValueError("Chrome DevToolsActivePort is incomplete")
    return validate_endpoint(f"ws://127.0.0.1:{int(lines[0])}{lines[1]}")


class BrowserTransport:
    def __init__(self) -> None:
        self.rpc: RpcSocket | None = None
        self.mode = "extension"
        self.roots: dict[str, str] = {}
        self.on_event = lambda _: None

    async def connect(self, mode: str, endpoint: str | None = None) -> dict:
        self.mode = mode
        if mode == "extension":
            self.rpc = await connect_bridge()
            self.rpc.on_event = self.on_event
            return await self.rpc.request({"action": "status"})
        self.rpc = RpcSocket()
        await self.rpc.open(validate_endpoint(endpoint) if endpoint else chrome_endpoint())
        self.rpc.on_event = self._direct_event
        return await self.rpc.request({"method": "Browser.getVersion"})

    def _direct_event(self, message: dict) -> None:
        if message.get("event") == "disconnected":
            self.on_event(message)
            return
        session = message.get("sessionId")
        tab = next((tab for tab, root in self.roots.items() if root == session), None)
        self.on_event(
            {
                "event": "cdp",
                "tab": tab,
                "session": None if tab else session,
                "method": message.get("method"),
                "params": message.get("params", {}),
            }
        )

    async def request(self, action: str, **args):
        if self.rpc is None:
            raise RuntimeError("Call browser_connect first")
        if self.mode == "extension":
            return await self.rpc.request(
                {"action": action, **args}, timeout=115 if action == "confirm" else 30
            )
        if action == "tabs":
            result = await self.rpc.request({"method": "Target.getTargets"})
            return [
                {
                    "id": t["targetId"],
                    "title": t["title"],
                    "url": t["url"],
                    "active": None,
                    "controlled": t["targetId"] in self.roots,
                }
                for t in result["targetInfos"]
                if t["type"] == "page"
            ]
        if action == "open":
            result = await self.rpc.request(
                {
                    "method": "Target.createTarget",
                    "params": {"url": args["url"], "background": True},
                }
            )
            return {"id": result["targetId"]}
        if action == "claim":
            if args["tab"] not in self.roots:
                result = await self.rpc.request(
                    {
                        "method": "Target.attachToTarget",
                        "params": {"targetId": args["tab"], "flatten": True},
                    }
                )
                self.roots[args["tab"]] = result["sessionId"]
            return {}
        if action in {"select", "close"}:
            method = "Target.activateTarget" if action == "select" else "Target.closeTarget"
            return await self.rpc.request({"method": method, "params": {"targetId": args["tab"]}})
        if action == "cdp":
            params = {"method": args["method"], "params": args.get("params", {})}
            if not args["method"].startswith("Browser."):
                params["sessionId"] = args.get("session") or self.roots[args["tab"]]
            return await self.rpc.request(params)
        if action == "confirm":
            # The approval UI belongs to the extension, never to the controlled page.
            bridge = await connect_bridge()
            try:
                return await bridge.request({"action": "confirm", **args}, timeout=115)
            finally:
                await bridge.close()
        if action == "release":
            for session in list(self.roots.values()):
                await self.rpc.request(
                    {"method": "Target.detachFromTarget", "params": {"sessionId": session}}
                )
            self.roots.clear()
            return {}
        raise RuntimeError(f"{action} requires the SPIRIT extension")

    async def cdp(self, tab: str, method: str, params: dict | None = None, session=None):
        return await self.request(
            "cdp", tab=tab, method=method, params=params or {}, session=session
        )

    async def close(self) -> None:
        if self.rpc:
            try:
                await self.request("release")
            except (RuntimeError, OSError, TimeoutError):
                pass
            await self.rpc.close()
            self.rpc = None


def expression_call(function: str, *args) -> str:
    return f"({function})({','.join(json.dumps(arg) for arg in args)})"
