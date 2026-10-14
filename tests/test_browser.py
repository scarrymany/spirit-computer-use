import asyncio
import ctypes
import json
import os
import secrets
import shutil
import subprocess
import threading
import time
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image
from playwright.async_api import async_playwright
from websockets.asyncio.server import serve

from spirit_computer_use import browser_transport
from spirit_computer_use.browser import Browser
from spirit_computer_use.browser_bridge import Broker, RpcSocket

ROOT = Path(__file__).resolve().parents[1]


def cursor_position():
    class Point(ctypes.Structure):
        _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

    point = Point()
    assert ctypes.windll.user32.GetCursorPos(ctypes.byref(point))
    return point.x, point.y


class Site(SimpleHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def do_GET(self):
        if self.path == "/download":
            self.send_response(200)
            self.send_header("Content-Disposition", 'attachment; filename="spirit-test.txt"')
            self.end_headers()
            self.wfile.write(b"SPIRIT download verified")
            return
        if self.path == "/ping":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")
            return
        super().do_GET()


@pytest.fixture
def site():
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0), partial(Site, directory=ROOT / "tests/browser_site")
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    server.server_close()
    thread.join()


def ref(state, name, role=None):
    return next(
        n["ref"]
        for frame in state["frames"]
        for n in frame["nodes"]
        if n["name"] == name and (role is None or n["role"] == role)
    )


@pytest.mark.browser
def test_extension_end_to_end(tmp_path, monkeypatch, site):
    async def run():
        token = secrets.token_urlsafe(32)
        broker = Broker(token)
        async with serve(broker.handle, "127.0.0.1", 0, max_size=32 * 1024 * 1024) as bridge:
            port = bridge.sockets[0].getsockname()[1]
            url = f"ws://127.0.0.1:{port}"
            extension = tmp_path / "extension"
            shutil.copytree(ROOT / "extension", extension)
            (extension / "connection.json").write_text(json.dumps({"url": url, "token": token}))

            async def connect_test_bridge():
                rpc = RpcSocket()
                await rpc.open(url, {"role": "engine", "token": token})
                return rpc

            monkeypatch.setattr(browser_transport, "connect_bridge", connect_test_bridge)
            profile = tmp_path / "profile" / "Default"
            profile.mkdir(parents=True)
            (tmp_path / "downloads").mkdir()
            (profile / "Preferences").write_text(
                json.dumps(
                    {
                        "download": {
                            "default_directory": str(tmp_path / "downloads"),
                            "prompt_for_download": False,
                        }
                    }
                )
            )
            async with async_playwright() as pw:
                context = await pw.chromium.launch_persistent_context(
                    tmp_path / "profile",
                    channel="chromium",
                    headless=os.environ.get("SPIRIT_HEADED_TEST") != "1",
                    executable_path=os.environ.get("SPIRIT_TEST_CHROME"),
                    args=[
                        f"--disable-extensions-except={extension}",
                        f"--load-extension={extension}",
                        "--site-per-process",
                    ],
                    viewport={"width": 1100, "height": 800},
                    device_scale_factor=2,
                )
                engine = None
                try:
                    browser_session = await context.browser.new_browser_cdp_session()
                    await browser_session.send(
                        "Browser.setDownloadBehavior", {"behavior": "default"}
                    )
                    page = await context.new_page()
                    await page.goto(site)
                    await page.wait_for_selector("#cross")
                    other = await context.new_page()
                    await other.goto(site + "/next.html")
                    await other.bring_to_front()
                    for _ in range(100):
                        if broker.extension:
                            break
                        await asyncio.sleep(0.05)
                    assert broker.extension, "MV3 extension did not connect"
                    engine = Browser(threading.Event())
                    await engine.connect("extension")
                    tabs = await engine.list_tabs()
                    tab = next(t["id"] for t in tabs if t["url"].rstrip("/") == site)
                    assert not next(t["active"] for t in tabs if t["id"] == tab)
                    before = await context.service_workers[0].evaluate(
                        "chrome.tabs.query({active:true}).then(t=>t.map(x=>x.id))"
                    )
                    state = await engine.read_page(tab)
                    assert await page.evaluate(
                        "document.getElementById('__spirit_overlay__').shadowRoot ==="
                        " null && !document.getElementById('__spirit_overlay__').spir"
                        "itMove"
                    )
                    assert len(state["frames"]) >= 3
                    grouped = await engine.list_tabs()
                    assert next(t for t in grouped if t["id"] == tab)["group_id"] >= 0
                    assert all(t["group_id"] == -1 for t in grouped if t["id"] != tab)
                    assert ref(state, "Shadow play", "button")
                    assert "hidden-secret" not in json.dumps(state, default=lambda _: "")
                    with Image.open(BytesIO(state["png"])) as image:
                        assert image.size == (1100, 800)
                    pointer_before = cursor_position()
                    foreground_before = ctypes.windll.user32.GetForegroundWindow()
                    started = time.monotonic()
                    await engine.click(tab, state["snapshot_id"], ref=ref(state, "Play", "button"))
                    latency = time.monotonic() - started
                    cursor_unchanged = cursor_position() == pointer_before
                    foreground_unchanged = (
                        ctypes.windll.user32.GetForegroundWindow() == foreground_before
                    )
                    if os.environ.get("SPIRIT_CURSOR_TEST") == "1":
                        assert cursor_unchanged
                        assert foreground_unchanged
                    assert await page.locator("#result").inner_text() == "Played"
                    after = await context.service_workers[0].evaluate(
                        "chrome.tabs.query({active:true}).then(t=>t.map(x=>x.id))"
                    )
                    assert before == after, "Browser input stole the active tab"
                    with pytest.raises(ValueError, match="consumed"):
                        await engine.click(tab, state["snapshot_id"], x=20, y=20)
                    state = await engine.read_page(tab, screenshot=False)
                    await engine.type_text(
                        tab,
                        state["snapshot_id"],
                        "Привет 🌍",
                        ref=ref(state, "Display name", "textbox"),
                    )
                    assert await page.locator("#name").input_value() == "Привет 🌍"
                    state = await engine.read_page(tab, screenshot=False)
                    with pytest.raises(ValueError, match="Password"):
                        await engine.type_text(
                            tab,
                            state["snapshot_id"],
                            "not-entered",
                            ref=ref(state, "Secret", "textbox"),
                        )
                    assert await page.locator("[type=password]").input_value() == "hidden-secret"
                    cross = next(f for f in page.frames if "?cross" in f.url)
                    await cross.locator("[type=password]").focus()
                    state = await engine.read_page(tab, screenshot=False)
                    with pytest.raises(ValueError, match="editable"):
                        await engine.type_text(tab, state["snapshot_id"], "blocked")
                    assert await cross.locator("[type=password]").input_value() == "frame-secret"
                    state = await engine.read_page(tab, screenshot=False)
                    frame_inputs = [
                        n["ref"]
                        for f in state["frames"]
                        for n in f["nodes"]
                        if n["name"] == "Frame input" and n["role"] == "textbox"
                    ]
                    await engine.type_text(
                        tab, state["snapshot_id"], "Frame Unicode test", ref=frame_inputs[-1]
                    )
                    assert "Frame Unicode test" in [
                        await f.locator("input:not([type=password])").input_value()
                        for f in page.frames[1:]
                    ]

                    state = await engine.read_page(tab, screenshot=False)
                    await engine.click(
                        tab, state["snapshot_id"], ref=ref(state, "Shadow play", "button")
                    )
                    assert await page.locator("#result").inner_text() == "Shadow clicked"
                    state = await engine.read_page(tab, screenshot=False)
                    frame_refs = [
                        n["ref"]
                        for f in state["frames"]
                        for n in f["nodes"]
                        if n["name"] == "Frame play" and n["role"] == "button"
                    ]
                    assert len(frame_refs) == 2
                    await engine.click(tab, state["snapshot_id"], ref=frame_refs[-1])
                    assert "Frame clicked" in [
                        await f.locator("button").inner_text() for f in page.frames[1:]
                    ]
                    state = await engine.read_page(tab, screenshot=False)
                    old_ref = ref(state, "Play", "button")
                    await page.locator("#replace").click()
                    await engine.click(tab, state["snapshot_id"], ref=old_ref)
                    assert await page.locator("#result").inner_text() == "Played"
                    state = await engine.read_page(tab, screenshot=False)
                    await page.locator("#cover").evaluate("e=>e.style.display='block'")
                    with pytest.raises(ValueError, match="occluded"):
                        await engine.click(
                            tab, state["snapshot_id"], ref=ref(state, "Play", "button")
                        )
                    await page.locator("#cover").evaluate("e=>e.style.display='none'")
                    await page.mouse.move(1000, 700)
                    await page.locator("#play").evaluate(
                        "e=>e.onpointerenter=()=>e.style.transform='translateX(300px)'"
                    )
                    state = await engine.read_page(tab, screenshot=False)
                    with pytest.raises(ValueError, match="occluded"):
                        await engine.click(
                            tab, state["snapshot_id"], ref=ref(state, "Play", "button")
                        )
                    await page.locator("#play").evaluate(
                        "e=>{e.onpointerenter=null;e.style.transform='none'}"
                    )

                    state = await engine.read_page(tab, screenshot=False)
                    await engine.keys(tab, state["snapshot_id"], ["ArrowLeft", "ArrowDown"])
                    assert await page.locator("#score").inner_text() == "Score: 20"
                    state = await engine.read_page(tab, screenshot=False)
                    await engine.form_input(
                        tab, state["snapshot_id"], ref(state, "Color", "combobox"), "cyan"
                    )
                    assert await page.locator("select").input_value() == "cyan"
                    state = await engine.read_page(tab, screenshot=False)
                    await engine.form_input(
                        tab, state["snapshot_id"], ref(state, "Enabled", "checkbox"), True
                    )
                    assert await page.locator("#check").is_checked()
                    for name, button, count, expected in [
                        ("Double target", "left", 2, "Double clicked"),
                        ("Right target", "right", 1, "Right clicked"),
                    ]:
                        state = await engine.read_page(tab, screenshot=False)
                        await engine.click(
                            tab,
                            state["snapshot_id"],
                            ref=ref(state, name, "button"),
                            button=button,
                            count=count,
                        )
                        assert await page.locator("#result").inner_text() == expected
                    await page.locator("#drag").scroll_into_view_if_needed()
                    state = await engine.read_page(tab, screenshot=False)
                    box = await page.locator("#drag").bounding_box()
                    await engine.drag(
                        tab,
                        state["snapshot_id"],
                        box["x"] + 15,
                        box["y"] + 15,
                        box["x"] + 110,
                        box["y"] + 15,
                    )
                    assert await page.locator("#result").inner_text() == "Dragged"
                    state = await engine.read_page(tab, screenshot=False)
                    await engine.click(
                        tab, state["snapshot_id"], ref=ref(state, "Bottom target", "button")
                    )
                    assert await page.locator("#result").inner_text() == "Bottom clicked"
                    state = await engine.read_page(tab, screenshot=False)
                    prior_scroll = await page.evaluate("scrollY")
                    await engine.scroll(tab, state["snapshot_id"], 500, 400, delta_y=-300)
                    await page.wait_for_function("y=>scrollY<y", arg=prior_scroll)
                    state = await engine.read_page(tab, screenshot=False)
                    await engine.hold_key(tab, state["snapshot_id"], "ArrowUp", 100)
                    assert not engine.tabs[tab].held
                    state = await engine.read_page(tab, screenshot=False)
                    payload = tmp_path / "upload.txt"
                    payload.write_text("Upload verification")
                    upload = asyncio.create_task(
                        engine.upload(
                            tab, state["snapshot_id"], ref(state, "Upload document"), [str(payload)]
                        )
                    )
                    approval = await context.wait_for_event("page")
                    await approval.wait_for_load_state()
                    assert "Provide these files" in await approval.locator("#message").inner_text()
                    await approval.locator("#allow").click()
                    await upload
                    assert (
                        await page.locator("#upload").evaluate("e=>e.files[0].name") == "upload.txt"
                    )
                    exports = await engine.export_tabs(str(tmp_path))
                    assert tab in [(await engine._tab(path)).id for path in exports["files"]]
                    state = await engine.read_page(tab, screenshot=False)
                    engine.stop.set()
                    with pytest.raises(RuntimeError, match="Input stopped"):
                        await engine.click(tab, state["snapshot_id"], x=1, y=1)
                    engine.stop.clear()
                    await engine.save(tab, str(tmp_path / "page.png"))
                    await engine.save(tab, str(tmp_path / "page.pdf"), "pdf")
                    assert (tmp_path / "page.pdf").read_bytes().startswith(b"%PDF")
                    await engine.downloads(tab, str(tmp_path))
                    state = await engine.read_page(tab, screenshot=False)
                    await engine.click(
                        tab, state["snapshot_id"], ref=ref(state, "Download file", "link")
                    )
                    for _ in range(50):
                        await engine.downloads(tab)
                        if (tmp_path / "spirit-test.txt").exists():
                            break
                        await asyncio.sleep(0.1)
                    assert (tmp_path / "spirit-test.txt").read_text() == "SPIRIT download verified"
                    assert any("play event" in entry["text"] for entry in engine.tabs[tab].console)
                    assert any(
                        "/ping" in entry.get("url", "") for entry in engine.tabs[tab].network
                    )
                    await engine.navigate(tab, site + "/next.html")
                    await engine.wait_for(tab, text="Navigation worked")
                    assert await page.locator("#__spirit_overlay__").count() == 1
                    await engine.close()
                    assert not page.is_closed()
                    assert await page.locator("#__spirit_overlay__").count() == 0
                    (tmp_path / "metrics.json").write_text(
                        json.dumps(
                            {
                                "click_seconds": latency,
                                "cursor_unchanged": cursor_unchanged,
                                "foreground_unchanged": foreground_unchanged,
                            }
                        )
                    )
                except BaseException:
                    import traceback

                    traceback.print_exc()
                    raise
                finally:
                    if engine:
                        await engine.close()
                    await context.close()

    asyncio.run(asyncio.wait_for(run(), 90))


@pytest.mark.browser
def test_direct_cdp_existing_session(tmp_path, site):
    async def run():
        profile = tmp_path / "cdp-profile"
        chrome = os.environ["SPIRIT_TEST_CHROME"]
        process = subprocess.Popen(
            [
                chrome,
                "--headless=new",
                "--remote-debugging-port=0",
                "--user-data-dir=" + str(profile),
                "--no-first-run",
                "about:blank",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        engine = Browser(threading.Event())
        try:
            port_file = profile / "DevToolsActivePort"
            for _ in range(100):
                if port_file.exists():
                    break
                await asyncio.sleep(0.05)
            port, path = port_file.read_text().splitlines()[:2]
            await engine.connect("cdp", f"ws://127.0.0.1:{port}{path}")
            tab = (await engine.tab_action("new", url=site))["tab"]
            await engine.wait_for(tab, text="SPIRIT browser verification")
            state = await engine.read_page(tab)
            await engine.click(tab, state["snapshot_id"], ref=ref(state, "Play", "button"))
            assert "Played" in (await engine.get_page_text(tab))["text"]
            result = await engine.downloads(tab, str(tmp_path))
            assert result["method"] == "Browser.setDownloadBehavior"
            (tmp_path / "unrelated.txt").write_text("Do not report unrelated files")
            state = await engine.read_page(tab, screenshot=False)
            await engine.click(tab, state["snapshot_id"], ref=ref(state, "Download file", "link"))
            for _ in range(50):
                downloaded = await engine.downloads(tab)
                if downloaded["files"]:
                    break
                await asyncio.sleep(0.1)
            assert len(downloaded["files"]) == 1
            assert Path(downloaded["files"][0]["path"]).name != "unrelated.txt"

            await engine.close()
            assert process.poll() is None
        finally:
            await engine.close()
            process.terminate()
            process.wait(timeout=10)

    asyncio.run(asyncio.wait_for(run(), 60))
