from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import asdict, astuple
from pathlib import Path

from . import accessibility, native
from .capture import capture_window
from .state import Snapshot, Snapshots, Window

MUTATIONS = {
    "activate_window",
    "click",
    "move_pointer",
    "press_key",
    "type_text",
    "scroll",
    "drag",
    "set_value",
    "perform_secondary_action",
    "launch_app",
}
OPERATIONS = MUTATIONS | {
    "list_windows",
    "get_window",
    "list_apps",
    "get_window_state",
    "resume",
    "status",
}


class Desktop:
    def __init__(self, overlay, stop) -> None:
        native.initialize()
        self.snapshots = Snapshots()
        self.overlay = overlay
        self.stop = stop
        self.installed: dict[str, dict] = {}

    def highlight(self, hwnd: int, label: str, seconds: float = 1.6) -> None:
        self.overlay.put(
            {"bounds": astuple(native.bounds(hwnd)), "label": label, "seconds": seconds}
        )

    def dispatch(self, operation: str, args: dict):
        if operation not in OPERATIONS:
            raise ValueError("Unknown desktop operation")
        if operation == "status":
            return {
                "emergency_stopped": self.stop.is_set(),
                "platform": "Windows 11",
                "capture": "Windows.Graphics.Capture",
                "coordinate_space": "physical pixels",
            }
        if operation == "resume":
            if native.emergency_pressed():
                raise RuntimeError("Release the emergency shortcut before resuming")
            self.stop.clear()
            return {"emergency_stopped": False}
        with native.desktop_lock():
            if operation in MUTATIONS:
                native.check_stop(self.stop)
            if operation == "list_windows":
                return native.list_windows()
            if operation == "get_window":
                return native.describe(args["id"]).model_dump()
            if operation == "list_apps":
                return self.list_apps()
            if operation == "launch_app":
                return self.launch_app(**args)
            window = Window.model_validate(args.pop("window"))
            native.validate(window)
            if operation == "get_window_state":
                return self.get_window_state(window, **args)
            if operation == "activate_window":
                self.snapshots.invalidate(window.id)
                native.activate(window)
                self.highlight(window.id, "Active window")
                return {"ok": True, "observe_again": True}
            snapshot_id = args.pop("snapshot_id")
            snapshot = self.snapshots.require(snapshot_id, window, native.bounds(window.id))
            try:
                native.activate(window)
                # Restoring/focusing can change geometry even when the preflight matched.
                self.snapshots.require(snapshot_id, window, native.bounds(window.id))
                self.highlight(
                    window.id,
                    operation.replace("_", " "),
                    max(1.6, float(args.get("duration", 0)) + 0.4),
                )
                getattr(self, operation)(window, snapshot, **args)
                return {"ok": True, "observe_again": True}
            finally:
                self.snapshots.invalidate(window.id)

    def get_window_state(self, window: Window, include_screenshot=True, include_text=False):
        self.snapshots.invalidate(window.id)
        if native.user32.IsIconic(window.id):
            raise ValueError("Window is minimized; activate_window before capturing")
        if not include_screenshot and not include_text:
            raise ValueError("Request a screenshot, accessibility, or both")
        snapshot = Snapshot(window, native.bounds(window.id))
        result = {
            "window": native.describe(window.id).model_dump(),
            "bounds": asdict(snapshot.bounds),
            "coordinate_space": "physical pixels relative to window bounds",
            "accessibility": None,
        }
        if include_text:
            result["accessibility"] = accessibility.tree(snapshot)
        if include_screenshot:
            png, width, height = capture_window(window.id)
            if (width, height) != (snapshot.bounds.width, snapshot.bounds.height):
                raise RuntimeError(
                    "Capture size disagrees with window geometry; refresh after resize"
                )
            result.update(png=png, width=width, height=height)
        native.validate(window)
        if native.bounds(window.id) != snapshot.bounds:
            raise ValueError("Window moved during observation; capture again")
        result["snapshot_id"] = self.snapshots.add(snapshot)
        self.highlight(window.id, "Observed")
        return result

    def click(
        self, window, snapshot, x=None, y=None, element_index=None, button="left", click_count=1
    ):
        if button not in native.MOUSE_DOWN or click_count not in (1, 2):
            raise ValueError("Choose left/right/middle and one or two clicks")
        if element_index is not None:
            if x is not None or y is not None:
                raise ValueError("Choose element_index or x/y, not both")
            rectangle = accessibility.element(snapshot, element_index).rectangle()
            x = (rectangle.left + rectangle.right) // 2 - snapshot.bounds.left
            y = (rectangle.top + rectangle.bottom) // 2 - snapshot.bounds.top
        px, py = snapshot.bounds.point(x, y)
        for _ in range(click_count):
            native.move(window.id, px, py, self.stop)
            native.mouse(native.MOUSE_DOWN[button])
            try:
                time.sleep(0.025)
            finally:
                native.mouse(native.MOUSE_UP[button])
            time.sleep(0.04)

    def move_pointer(self, window, snapshot, x, y):
        native.move(window.id, *snapshot.bounds.point(x, y), self.stop)

    def press_key(self, window, snapshot, key):
        native.press_chord(window.id, key, self.stop)

    def type_text(self, window, snapshot, text):
        accessibility.require_text_focus(window.id)
        native.type_text(window.id, text, self.stop)

    def scroll(self, window, snapshot, x, y, scroll_y=0, scroll_x=0):
        if abs(scroll_y) > 12000 or abs(scroll_x) > 12000:
            raise ValueError("Scroll delta exceeds 12000 wheel units")
        native.move(window.id, *snapshot.bounds.point(x, y), self.stop)
        if scroll_y:
            native.mouse(native.MOUSE_WHEEL, -scroll_y)
        if scroll_x:
            native.check_stop(self.stop)
            native.check_foreground(window.id)
            native.mouse(native.MOUSE_HWHEEL, scroll_x)

    def drag(self, window, snapshot, from_x, from_y, to_x, to_y, duration=0.6):
        if not 0.1 <= duration <= 5:
            raise ValueError("Drag duration must be 0.1..5 seconds")
        start = snapshot.bounds.point(from_x, from_y)
        end = snapshot.bounds.point(to_x, to_y)
        native.move(window.id, *start, self.stop)
        native.mouse(native.MOUSE_DOWN["left"])
        steps = max(2, round(duration * 60))
        try:
            for step in range(1, steps + 1):
                native.check_stop(self.stop)
                native.check_foreground(window.id)
                x = round(start[0] + (end[0] - start[0]) * step / steps)
                y = round(start[1] + (end[1] - start[1]) * step / steps)
                native.move(window.id, x, y, self.stop)
                time.sleep(duration / steps)
        finally:
            native.mouse(native.MOUSE_UP["left"])

    def set_value(self, window, snapshot, element_index, value):
        if len(value) > native.MAX_TEXT_LENGTH or "\x00" in value:
            raise ValueError("Value exceeds text limits")
        wrapper = accessibility.element(snapshot, element_index)
        native.check_stop(self.stop)
        native.check_foreground(window.id)
        if wrapper.iface_value.CurrentIsReadOnly:
            raise ValueError("Element is read-only")
        wrapper.iface_value.SetValue(value)

    def perform_secondary_action(self, window, snapshot, element_index, action):
        wrapper = accessibility.element(snapshot, element_index)
        native.check_stop(self.stop)
        native.check_foreground(window.id)
        if action == "invoke":
            wrapper.iface_invoke.Invoke()
        elif action == "toggle":
            wrapper.iface_toggle.Toggle()
        elif action == "expand":
            wrapper.iface_expand_collapse.Expand()
        elif action == "collapse":
            wrapper.iface_expand_collapse.Collapse()
        elif action == "select":
            wrapper.iface_selection_item.Select()
        else:
            raise ValueError("Supported actions: invoke, toggle, expand, collapse, select")

    def list_apps(self):
        windows = native.list_windows()
        grouped = {}
        for window in windows:
            path = window["app"]
            grouped.setdefault(path, {"id": path, "display_name": Path(path).stem, "windows": []})[
                "windows"
            ].append(window)
        script = (
            "[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new(); "
            "@(Get-StartApps | Select-Object Name,AppID) | ConvertTo-Json -Compress"
        )
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True,
            encoding="utf-8",
            timeout=12,
            creationflags=subprocess.CREATE_NO_WINDOW,
            check=True,
        )
        apps = json.loads(result.stdout or "[]")
        if isinstance(apps, dict):
            apps = [apps]
        self.installed = {"aumid:" + app["AppID"]: app for app in apps}
        for identifier, app in self.installed.items():
            grouped[identifier] = {"id": identifier, "display_name": app["Name"], "windows": []}
        return list(grouped.values())

    def launch_app(self, app: str, arguments: list[str] | None = None):
        if app.startswith("aumid:"):
            if app not in self.installed:
                self.list_apps()
            if app not in self.installed or arguments:
                raise ValueError("Use an installed app id from list_apps without arguments")
            os.startfile("shell:AppsFolder\\" + self.installed[app]["AppID"])
            return {"launched": app, "observe_again": True}
        path = Path(app)
        if not path.is_absolute() or path.suffix.casefold() != ".exe" or not path.is_file():
            raise ValueError("Use an absolute existing .exe path or an app id from list_apps")
        process = subprocess.Popen(
            [str(path), *(arguments or [])],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
        )
        return {"pid": process.pid, "observe_again": True}


def worker(connection, overlay, stop) -> None:
    # Native capture libraries may print diagnostics. MCP stdout belongs only to JSON-RPC.
    os.dup2(sys_stderr_fd(), 1)
    desktop = Desktop(overlay, stop)
    try:
        while True:
            operation, arguments = connection.recv()
            try:
                result = desktop.dispatch(operation, arguments)
                connection.send({"ok": True, "result": result})
            except Exception as error:
                connection.send(
                    {
                        "ok": False,
                        "error": f"{type(error).__name__}: {error}",
                        "outcome": "unknown" if operation in MUTATIONS else "not_applied",
                    }
                )
    except (EOFError, BrokenPipeError):
        pass
    finally:
        connection.close()


def sys_stderr_fd() -> int:
    import sys

    return sys.stderr.fileno()
