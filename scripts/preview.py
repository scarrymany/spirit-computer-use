"""Capture the real SPIRIT overlay over the disposable integration-test window."""

import json
import os
import subprocess
import tempfile
import time
from pathlib import Path

from PIL import ImageGrab

from spirit_computer_use.controller import Controller


def main():
    root = Path(__file__).resolve().parents[1]
    fixture = root / "tests/fixture/bin/Release/net9.0-windows/Spirit.TestWindow.exe"
    os.environ["SPIRIT_RECORD_OVERLAY"] = "1"
    with tempfile.TemporaryDirectory(prefix="spirit-preview-") as directory:
        state_path = Path(directory) / "state.json"
        process = subprocess.Popen([str(fixture), "SPIRIT Computer Use", str(state_path)])
        try:
            deadline = time.monotonic() + 8
            while not state_path.exists():
                if time.monotonic() >= deadline:
                    raise TimeoutError("Test window did not start")
                time.sleep(0.05)
            hwnd = json.loads(state_path.read_text())["hwnd"]
            with Controller() as controller:
                window = controller.call("get_window", id=hwnd)
                controller.call("activate_window", window=window)
                state = controller.call("get_window_state", window=window, include_text=True)
                line = next(
                    line
                    for line in state["accessibility"]["tree"].splitlines()
                    if "SPIRIT editor" in line
                )
                index = int(line.strip().split("]", 1)[0][1:])
                controller.call(
                    "set_value",
                    window=window,
                    snapshot_id=state["snapshot_id"],
                    element_index=index,
                    value="SPIRIT Computer Use\r\nWindows 11. Your agent, your desktop.",
                )
                state = controller.call("get_window_state", window=window)
                controller.call(
                    "move_pointer", window=window, snapshot_id=state["snapshot_id"], x=420, y=350
                )
                time.sleep(0.35)
                bounds = state["bounds"]
                image = ImageGrab.grab(
                    bbox=(bounds["left"], bounds["top"], bounds["right"], bounds["bottom"]),
                    include_layered_windows=True,
                    all_screens=True,
                )
                output = root / "artifacts/overlay-preview.png"
                output.parent.mkdir(exist_ok=True)
                image.save(output)
                print(output)
        finally:
            process.terminate()
            process.wait(timeout=5)


if __name__ == "__main__":
    main()
