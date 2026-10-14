import asyncio
import json

import pytest
from websockets.asyncio.client import connect
from websockets.asyncio.server import serve
from websockets.exceptions import ConnectionClosed

from spirit_computer_use.browser_bridge import EXTENSION_ID, Broker, RpcSocket
from spirit_computer_use.browser_keys import key_events
from spirit_computer_use.browser_transport import validate_endpoint


@pytest.mark.parametrize(
    "endpoint",
    [
        "ws://attacker.test:9222/devtools/browser/1",
        "ws://127.0.0.1:9222/devtools/page/1",
        "ws://name:secret@localhost:9222/devtools/browser/1",
        "http://127.0.0.1:9222",
        "ws://127.0.0.1:9222/devtools/browser/1?token=x",
    ],
)
def test_only_explicit_local_browser_endpoints(endpoint):
    with pytest.raises(ValueError):
        validate_endpoint(endpoint)


def test_bridge_auth_origin_and_routing():
    async def run():
        broker = Broker("test-secret")
        async with serve(broker.handle, "127.0.0.1", 0) as server:
            url = f"ws://127.0.0.1:{server.sockets[0].getsockname()[1]}"
            for role, origin, token in [
                ("extension", "https://evil.test", "test-secret"),
                ("extension", "chrome-extension://" + "a" * 32, "test-secret"),
                ("engine", "http://localhost", "test-secret"),
                ("engine", None, "wrong-token"),
            ]:
                async with connect(url, origin=origin, proxy=None) as socket:
                    await socket.send(json.dumps({"role": role, "token": token}))
                    with pytest.raises(ConnectionClosed):
                        await socket.recv()
            async with connect(
                url, origin="chrome-extension://" + EXTENSION_ID, proxy=None
            ) as extension:
                await extension.send(json.dumps({"role": "extension", "token": "test-secret"}))
                assert json.loads(await extension.recv())["ready"]
                engine = RpcSocket()
                await engine.open(url, {"role": "engine", "token": "test-secret"})
                request = asyncio.create_task(engine.request({"action": "tabs"}))
                message = json.loads(await extension.recv())
                assert message["owner"] and message["action"] == "tabs"
                await extension.send(json.dumps({"id": message["id"], "result": [{"id": "42"}]}))
                assert await request == [{"id": "42"}]
                await engine.close()

    asyncio.run(run())


def test_chord_releases_all_modifiers_and_arrows_have_virtual_codes():
    events = key_events("Control+Shift+A")
    assert [e["key"] for e in events if e["type"] == "keyDown"] == ["Control", "Shift", "A"]
    assert [e["key"] for e in events if e["type"] == "keyUp"] == ["A", "Shift", "Control"]
    assert key_events("ArrowLeft")[0]["windowsVirtualKeyCode"] == 37
    with pytest.raises(ValueError):
        key_events("ImaginaryKey")


def test_extension_install_registers_real_destination(tmp_path, monkeypatch):
    from spirit_computer_use import browser_bridge

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "user"))
    source = tmp_path / "source"
    source.mkdir()
    (source / "manifest.json").write_text('{"manifest_version":3}')
    target = tmp_path / "Desktop" / "SPIRIT Browser"
    assert browser_bridge.install_extension(source, target) == target
    assert not target.is_symlink()
    assert (target / "manifest.json").is_file()
    assert json.loads((target / "connection.json").read_text()) == browser_bridge.bridge_settings()
    registry = browser_bridge.settings_path().parent / "extensions.json"
    assert str(target) in json.loads(registry.read_text())


def test_clients_share_credentials_despite_appdata_virtualization(tmp_path, monkeypatch):
    from spirit_computer_use.browser_bridge import bridge_settings, settings_path

    profile = tmp_path / "user"
    monkeypatch.setenv("USERPROFILE", str(profile))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "codex-private-appdata"))
    codex_settings = bridge_settings()
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "ordinary-appdata"))
    assert bridge_settings() == codex_settings
    assert settings_path() == profile / ".spirit" / "browser" / "bridge.json"
