from __future__ import annotations

import asyncio
import hmac
import json
import os
import secrets
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

from websockets.asyncio.client import connect
from websockets.asyncio.server import serve
from websockets.exceptions import ConnectionClosed

BRIDGE_PORT = 47831
MAX_MESSAGE = 32 * 1024 * 1024
EXTENSION_ID = "daanlgffjgmnpfkaajloicnoabmbdamb"


def settings_path() -> Path:
    return Path(os.environ["LOCALAPPDATA"]) / "SPIRIT" / "browser" / "bridge.json"


def bridge_settings() -> dict:
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        data = {"url": f"ws://127.0.0.1:{BRIDGE_PORT}", "token": secrets.token_urlsafe(32)}
        try:
            with path.open("x", encoding="utf-8") as stream:
                json.dump(data, stream)
        except FileExistsError:
            pass
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: dict) -> None:
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        temporary.write_text(json.dumps(value), encoding="utf-8")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def install_extension(source: Path, destination: Path | None = None) -> Path:
    config = bridge_settings()
    destination = (destination or settings_path().parent / "extension").resolve()
    if not (source / "manifest.json").is_file():
        raise ValueError("Extension source must contain manifest.json")
    destination.mkdir(parents=True, exist_ok=True)
    for item in source.iterdir():
        if item.is_file():
            shutil.copy2(item, destination / item.name)
    write_json(destination / "connection.json", config)
    registry = settings_path().parent / "extensions.json"
    paths = json.loads(registry.read_text(encoding="utf-8")) if registry.exists() else {}
    paths[str(destination)] = True
    write_json(registry, paths)
    return destination


class Broker:
    def __init__(self, token: str) -> None:
        self.token = token
        self.extension = None
        self.engines: dict[str, object] = {}
        self.pending: dict[str, tuple[str, object, object]] = {}

    async def handle(self, socket) -> None:
        owner = uuid.uuid4().hex
        role = None
        try:
            message = json.loads(await asyncio.wait_for(socket.recv(), 5))
            role = message.get("role")
            origin = socket.request.headers.get("Origin", "")
            valid_origin = (role == "engine" and not origin) or (
                role == "extension" and origin == "chrome-extension://" + EXTENSION_ID
            )
            token = message.get("token", "")
            if (
                not valid_origin
                or not isinstance(token, str)
                or not hmac.compare_digest(token, self.token)
            ):
                await socket.close(1008, "Authentication failed")
                return
            if role == "extension":
                if self.extension is not None:
                    await socket.close(1008, "An extension is already connected")
                    return
                self.extension = socket
            else:
                self.engines[owner] = socket
            await socket.send(json.dumps({"ready": True, "owner": owner}))
            async for raw in socket:
                message = json.loads(raw)
                if message.get("ping"):
                    await socket.send('{"pong":true}')
                    continue
                if role == "extension":
                    if "event" in message:
                        targets = (
                            [self.engines[message["owner"]]]
                            if message.get("owner") in self.engines
                            else list(self.engines.values())
                        )
                        for target in targets:
                            try:
                                await target.send(raw)
                            except ConnectionClosed:
                                pass
                    else:
                        pending = self.pending.pop(str(message.get("id")), None)
                        if pending:
                            _, target, original_id = pending
                            message["id"] = original_id
                            try:
                                await target.send(json.dumps(message))
                            except ConnectionClosed:
                                pass
                    continue
                if self.extension is None:
                    await socket.send(
                        json.dumps(
                            {
                                "id": message.get("id"),
                                "error": (
                                    "SPIRIT extension is not connected. "
                                    "Load the prepared extension in chrome://extensions "
                                    "and press Connect in its popup."
                                ),
                            }
                        )
                    )
                    continue
                if len(self.pending) >= 128:
                    await socket.close(1008, "Too many pending requests")
                    return
                request_id = uuid.uuid4().hex
                self.pending[request_id] = (owner, socket, message.get("id"))
                message.update(id=request_id, owner=owner)
                await self.extension.send(json.dumps(message))
        except (ConnectionClosed, TimeoutError, ValueError, TypeError):
            pass
        finally:
            if role == "extension" and self.extension is socket:
                self.extension = None
                for _, target, request_id in list(self.pending.values()):
                    try:
                        await target.send(
                            json.dumps(
                                {
                                    "id": request_id,
                                    "error": (
                                        "Extension disconnected. Outcome unknown; "
                                        "observe before retrying."
                                    ),
                                }
                            )
                        )
                    except ConnectionClosed:
                        pass
                self.pending.clear()
            self.engines.pop(owner, None)
            self.pending = {k: v for k, v in self.pending.items() if v[0] != owner}
            if role == "engine" and self.extension is not None:
                try:
                    await self.extension.send(json.dumps({"action": "release", "owner": owner}))
                except ConnectionClosed:
                    pass


async def run_bridge() -> None:
    settings = bridge_settings()
    broker = Broker(settings["token"])
    async with serve(broker.handle, "127.0.0.1", BRIDGE_PORT, max_size=MAX_MESSAGE):
        settings["token"] = secrets.token_urlsafe(32)
        broker.token = settings["token"]
        write_json(settings_path(), settings)
        registry = settings_path().parent / "extensions.json"
        paths = json.loads(registry.read_text(encoding="utf-8")) if registry.exists() else {}
        paths[str(settings_path().parent / "extension")] = True
        for folder in paths:
            extension_config = Path(folder) / "connection.json"
            if extension_config.parent.is_dir():
                write_json(extension_config, settings)
        await asyncio.Future()


class RpcSocket:
    def __init__(self) -> None:
        self.socket = None
        self.reader = None
        self.pending: dict[int, asyncio.Future] = {}
        self.sequence = 0
        self.on_event = lambda _: None
        self.closing = False

    async def open(self, url: str, auth: dict | None = None) -> None:
        self.socket = await connect(url, max_size=MAX_MESSAGE, open_timeout=10, proxy=None)
        if auth is not None:
            await self.socket.send(json.dumps(auth))
            reply = json.loads(await asyncio.wait_for(self.socket.recv(), 10))
            if not reply.get("ready"):
                raise RuntimeError("Bridge authentication failed")
        self.reader = asyncio.create_task(self._read())

    async def _read(self) -> None:
        try:
            async for raw in self.socket:
                message = json.loads(raw)
                future = self.pending.pop(message.get("id"), None)
                if future is not None and not future.done():
                    if "error" in message:
                        future.set_exception(RuntimeError(str(message["error"])))
                    else:
                        future.set_result(message.get("result", {}))
                else:
                    self.on_event(message)
        except (ConnectionClosed, ValueError):
            pass
        finally:
            for future in self.pending.values():
                if not future.done():
                    future.set_exception(RuntimeError("Browser connection lost; outcome unknown"))
            self.pending.clear()
            if not self.closing:
                self.on_event({"event": "disconnected"})

    async def request(self, message: dict, timeout: float = 30) -> dict:
        self.sequence += 1
        identifier = self.sequence
        future = asyncio.get_running_loop().create_future()
        self.pending[identifier] = future
        try:
            await self.socket.send(json.dumps({"id": identifier, **message}))
            return await asyncio.wait_for(future, timeout)
        finally:
            self.pending.pop(identifier, None)

    async def close(self) -> None:
        self.closing = True
        if self.socket:
            await self.socket.close()
        if self.reader:
            await self.reader


async def connect_bridge() -> RpcSocket:
    settings = bridge_settings()
    auth = {"role": "engine", "token": settings["token"]}
    client = RpcSocket()
    try:
        await client.open(settings["url"], auth)
    except OSError:
        subprocess.Popen(
            [sys.executable, "-m", "spirit_computer_use", "browser-bridge"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        for attempt in range(30):
            await asyncio.sleep(0.1)
            try:
                settings = bridge_settings()
                await client.open(settings["url"], {"role": "engine", "token": settings["token"]})
                break
            except ConnectionClosed:
                if bridge_settings()["token"] == settings["token"]:
                    raise
                client = RpcSocket()
            except OSError:
                if attempt == 29:
                    raise RuntimeError("Could not start the local SPIRIT bridge") from None
    return client
