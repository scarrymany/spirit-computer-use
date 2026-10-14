import queue
import threading
from contextlib import nullcontext

import pytest

from spirit_computer_use import desktop, native
from spirit_computer_use.state import Bounds, Snapshot, Window


@pytest.fixture
def observed(monkeypatch):
    window = Window(id=10, pid=20, created=1.0, app="test.exe", title="Test")
    bounds = Bounds(0, 0, 100, 100)
    engine = desktop.Desktop(queue.SimpleQueue(), threading.Event())
    token = engine.snapshots.add(Snapshot(window, bounds))
    monkeypatch.setattr(native, "desktop_lock", nullcontext)
    monkeypatch.setattr(native, "validate", lambda _: window)
    monkeypatch.setattr(native, "describe", lambda _: window)
    monkeypatch.setattr(native, "bounds", lambda _: bounds)
    monkeypatch.setattr(native, "check_stop", lambda _: None)
    return engine, window, bounds, token


def test_failed_activation_consumes_input_snapshot(observed, monkeypatch):
    engine, window, bounds, token = observed

    def refuse(_):
        raise RuntimeError("Focus refused")

    monkeypatch.setattr(native, "activate", refuse)
    with pytest.raises(RuntimeError, match="Focus refused"):
        engine.dispatch(
            "click", {"window": window.model_dump(), "snapshot_id": token, "x": 1, "y": 1}
        )
    with pytest.raises(ValueError, match="missing"):
        engine.snapshots.require(token, window, bounds)


def test_failed_capture_invalidates_old_observation(observed, monkeypatch):
    engine, window, bounds, token = observed

    def refuse(_):
        raise RuntimeError("Capture refused")

    monkeypatch.setattr(desktop, "capture_window", refuse)
    with pytest.raises(RuntimeError, match="Capture refused"):
        engine.get_window_state(window)
    with pytest.raises(ValueError, match="missing"):
        engine.snapshots.require(token, window, bounds)
