import asyncio
import base64
import io
import json
import os
import subprocess
import sys
import time
import uuid
from datetime import timedelta
from pathlib import Path

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from PIL import Image

from spirit_computer_use.controller import Controller, DesktopError

pytestmark = [
    pytest.mark.desktop,
    pytest.mark.skipif(
        os.environ.get("SPIRIT_DESKTOP_TEST") != "1",
        reason="Set SPIRIT_DESKTOP_TEST=1 on an unlocked Windows desktop",
    ),
]
ROOT = Path(__file__).resolve().parents[1]


def wait_for(read, predicate, timeout=8):
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        try:
            last = read()
            if predicate(last):
                return last
        except (FileNotFoundError, json.JSONDecodeError, PermissionError):
            pass
        time.sleep(0.05)
    raise AssertionError(f"Expected state was not reached: {last}")


@pytest.fixture
def fixture_window(tmp_path):
    exe = ROOT / "tests/fixture/bin/Release/net9.0-windows/Spirit.TestWindow.exe"
    assert exe.is_file(), "Build tests/fixture/Spirit.TestWindow.csproj first"
    state_path = tmp_path / "state.json"
    title = "SPIRIT Test " + uuid.uuid4().hex[:8]
    process = subprocess.Popen([str(exe), title, str(state_path)])

    def read():
        return json.loads(state_path.read_text(encoding="utf-8"))

    try:
        state = wait_for(read, lambda value: value.get("hwnd"))
        yield state["hwnd"], read
    finally:
        process.terminate()
        process.wait(timeout=5)


def test_desktop_input_capture_accessibility_and_stop(fixture_window):
    hwnd, read = fixture_window
    with Controller() as controller:
        window = controller.call("get_window", id=hwnd)
        assert any(item["id"] == hwnd for item in controller.call("list_windows"))
        controller.call("activate_window", window=window)

        def observe():
            return controller.call(
                "get_window_state", window=window, include_screenshot=True, include_text=True
            )

        state = observe()
        assert "SPIRIT editor" in state["accessibility"]["tree"]
        image = Image.open(io.BytesIO(state["png"]))
        assert image.size == (state["width"], state["height"])
        assert image.width > 700 and len(image.getcolors(image.width * image.height)) > 10
        artifacts = ROOT / "artifacts"
        artifacts.mkdir(exist_ok=True)
        (artifacts / "test-window.png").write_bytes(state["png"])

        def index(state, name):
            for line in state["accessibility"]["tree"].splitlines():
                if name in line:
                    return int(line.strip().split("]", 1)[0][1:])
            raise AssertionError(f"Missing UIA element {name}: {state['accessibility']}")

        controller.call(
            "click",
            window=window,
            snapshot_id=state["snapshot_id"],
            element_index=index(state, "SPIRIT editor"),
        )
        state = observe()
        controller.call("press_key", window=window, snapshot_id=state["snapshot_id"], key="Ctrl+A")
        state = observe()
        assert state["accessibility"]["selected_text"] == "Ready"
        text = "SPIRIT Unicode: Привет 世界 🚀"
        controller.call("type_text", window=window, snapshot_id=state["snapshot_id"], text=text)
        try:
            wait_for(read, lambda value: value["text"] == text)
        except AssertionError:
            failed = observe()
            (artifacts / "failed-input.png").write_bytes(failed["png"])
            print(failed["accessibility"], flush=True)
            raise
        with pytest.raises(DesktopError, match="missing"):
            controller.call(
                "type_text", window=window, snapshot_id=state["snapshot_id"], text="bad"
            )

        state = observe()
        controller.call(
            "set_value",
            window=window,
            snapshot_id=state["snapshot_id"],
            element_index=index(state, "SPIRIT editor"),
            value="UIA value verified",
        )
        wait_for(read, lambda value: value["text"] == "UIA value verified")
        state = observe()
        controller.call(
            "click",
            window=window,
            snapshot_id=state["snapshot_id"],
            element_index=index(state, "SPIRIT button"),
        )
        wait_for(read, lambda value: value["clicks"] == 1)
        state = observe()
        controller.call(
            "perform_secondary_action",
            window=window,
            snapshot_id=state["snapshot_id"],
            element_index=index(state, "SPIRIT toggle"),
            action="toggle",
        )
        wait_for(read, lambda value: value["toggled"])

        # Read the actual UIA rectangle, including DPI scaling and non-client offsets.
        state = observe()
        line = next(
            line
            for line in state["accessibility"]["tree"].splitlines()
            if "SPIRIT drag pad" in line
        )
        rectangle = line.rsplit("(", 1)[1].split(")", 1)[0]
        left, top, right, bottom = map(int, rectangle.split(","))
        controller.call(
            "drag",
            window=window,
            snapshot_id=state["snapshot_id"],
            from_x=left + 30,
            from_y=top + 50,
            to_x=right - 30,
            to_y=bottom - 30,
            duration=0.3,
        )
        wait_for(read, lambda value: value["dragMoves"] > 3 and not value["dragging"])
        state = observe()
        controller.call(
            "scroll",
            window=window,
            snapshot_id=state["snapshot_id"],
            x=left + 50,
            y=top + 50,
            scroll_y=120,
        )
        wait_for(read, lambda value: value["wheel"] == -120)
        controller.stop.set()
        state = observe()
        with pytest.raises(DesktopError, match="Emergency"):
            controller.call(
                "click",
                window=window,
                snapshot_id=state["snapshot_id"],
                element_index=index(state, "SPIRIT button"),
            )
        assert read()["clicks"] == 1
        controller.call("resume")
        assert not controller.call("status")["emergency_stopped"]


def test_mcp_delivers_actual_window_image(fixture_window):
    hwnd, _ = fixture_window

    async def run():
        parameters = StdioServerParameters(
            command=sys.executable, args=["-m", "spirit_computer_use", "serve"]
        )
        async with stdio_client(parameters) as (reader, writer):
            async with ClientSession(
                reader, writer, read_timeout_seconds=timedelta(seconds=40)
            ) as session:
                await session.initialize()
                found = await session.call_tool("get_window", {"id": hwnd})
                assert not found.isError
                window = json.loads(found.content[0].text)
                state = await session.call_tool(
                    "get_window_state", {"window": window, "include_text": True}
                )
                assert not state.isError
                metadata = json.loads(state.content[0].text)
                assert metadata["snapshot_id"]
                assert "SPIRIT editor" in metadata["accessibility"]["tree"]
                assert state.content[1].type == "image"
                assert state.content[1].mimeType == "image/png"
                image = Image.open(io.BytesIO(base64.b64decode(state.content[1].data)))
                assert image.size == (metadata["width"], metadata["height"])

    asyncio.run(run())
