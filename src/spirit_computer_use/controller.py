from __future__ import annotations

import multiprocessing as mp
import os
import sys
import threading
from pathlib import Path

WORKER_TIMEOUT = 25.0


def desktop_worker(connection, overlay, stop, held) -> None:
    prepare_worker_streams()
    try:
        from . import native

        native.initialize()
        native.held_inputs = held
        from .desktop import worker

        worker(connection, overlay, stop)
    except Exception as error:
        try:
            connection.send(
                {"ok": False, "error": f"Worker startup: {error}", "outcome": "not_applied"}
            )
        except (OSError, EOFError):
            pass
    finally:
        connection.close()


def overlay_worker(commands, stop, shutdown, ready, visible) -> None:
    prepare_worker_streams()
    from .overlay import run_overlay

    run_overlay(commands, stop, shutdown, ready, visible)


def prepare_worker_streams() -> None:
    # pythonw has no console streams; native libraries still expect valid descriptors.
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")
    import pywin32_bootstrap  # noqa: F401


class DesktopError(RuntimeError):
    pass


class Controller:
    def __init__(self, *, overlay: bool = True, timeout: float = WORKER_TIMEOUT) -> None:
        if sys.platform != "win32":
            raise RuntimeError("SPIRIT Computer Use runs on Windows 11 only")
        # Bypass the venv redirector: duplicated multiprocessing handles belong
        # to the spawned process, not to an intermediate launcher process.
        pythonw = Path(sys._base_executable).with_name("pythonw.exe")
        if not pythonw.is_file():
            raise RuntimeError(
                "A standard Windows Python installation with pythonw.exe is required"
            )
        mp.set_executable(str(pythonw))
        self.context = mp.get_context("spawn")
        self.stop = self.context.Event()
        self.shutdown = self.context.Event()
        self.overlay_ready = self.context.Event()
        self.overlay_queue = self.context.Queue()
        self.held = self.context.Array("i", 258, lock=False)
        self.overlay_enabled = overlay
        self.timeout = timeout
        self.lock = threading.RLock()
        self.closed = False
        self.process = None
        self.overlay_process = None
        self.connection = None

    def _start(self) -> None:
        if self.overlay_process is None or not self.overlay_process.is_alive():
            self.shutdown.clear()
            self.overlay_ready.clear()
            self.overlay_process = self.context.Process(
                target=overlay_worker,
                args=(
                    self.overlay_queue,
                    self.stop,
                    self.shutdown,
                    self.overlay_ready,
                    self.overlay_enabled,
                ),
                daemon=True,
            )
            self.overlay_process.start()
            if not self.overlay_ready.wait(10):
                self.close()
                raise DesktopError("Overlay/emergency-stop monitor failed to start")
        if self.process is None or not self.process.is_alive():
            if self.connection:
                self.connection.close()
            self.connection, child = self.context.Pipe()
            self.process = self.context.Process(
                target=desktop_worker,
                args=(child, self.overlay_queue, self.stop, self.held),
                daemon=True,
            )
            self.process.start()
            child.close()

    def call(self, operation: str, **arguments):
        with self.lock:
            if self.closed:
                raise DesktopError("Controller is closed")
            self._start()
            try:
                self.connection.send((operation, arguments))
                if not self.connection.poll(self.timeout):
                    raise TimeoutError("Desktop operation timed out")
                response = self.connection.recv()
            except (TimeoutError, EOFError, BrokenPipeError, OSError) as error:
                self.stop.set()
                self._stop_worker()
                raise DesktopError(
                    f"{type(error).__name__}: {error}. Outcome is unknown; no automatic retry. "
                    "Input is stopped. Observe and ask the user before resuming."
                ) from error
            if not response["ok"]:
                raise DesktopError(f"{response['error']} (outcome: {response['outcome']})")
            return response["result"]

    def _stop_worker(self) -> None:
        if self.connection:
            self.connection.close()
            self.connection = None
        if self.process:
            self.process.join(0.5)
            if self.process.is_alive():
                self.process.terminate()
                self.process.join(2)
            self.process.close()
            self.process = None
        if any(self.held):
            from .native import release_inputs

            release_inputs(self.held)

    def close(self) -> None:
        self.stop.set()
        with self.lock:
            if self.closed:
                return
            try:
                self._stop_worker()
            finally:
                self.shutdown.set()
                if self.overlay_process:
                    self.overlay_process.join(2)
                    if self.overlay_process.is_alive():
                        self.overlay_process.terminate()
                        self.overlay_process.join(2)
                    self.overlay_process.close()
                    self.overlay_process = None
                self.overlay_queue.close()
                self.overlay_queue.join_thread()
                self.closed = True

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
