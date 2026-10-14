import time

import psutil
import pytest

from spirit_computer_use import controller as module


def stalled_worker(connection, overlay, stop, held):
    connection.recv()
    time.sleep(10)


def test_native_timeout_stops_input_and_terminates_worker(monkeypatch):
    monkeypatch.setattr(module, "desktop_worker", stalled_worker)
    with module.Controller(overlay=False, timeout=0.15) as controller:
        start = time.monotonic()
        with pytest.raises(module.DesktopError, match="Outcome is unknown"):
            controller.call("status")
        assert time.monotonic() - start < 5
        assert controller.stop.is_set()
        assert controller.process is None


def test_shutdown_reaps_both_children():
    controller = module.Controller(overlay=False)
    controller.call("status")
    pids = [controller.process.pid, controller.overlay_process.pid]
    controller.close()
    assert all(not psutil.pid_exists(pid) for pid in pids)
    controller.close()
