from __future__ import annotations

import ctypes
import sys
import threading


class EmergencyStop:
    def __init__(self) -> None:
        self.event = threading.Event()
        self.shutdown = threading.Event()
        self.thread = threading.Thread(target=self._monitor, name="spirit-stop", daemon=True)

    def start(self) -> None:
        self.thread.start()

    def _monitor(self) -> None:
        if sys.platform != "win32":
            return
        get_key = ctypes.windll.user32.GetAsyncKeyState
        get_key.argtypes = [ctypes.c_int]
        get_key.restype = ctypes.c_short
        while not self.shutdown.wait(0.02):
            if get_key(0x13) & 0x8000 or all(get_key(k) & 0x8000 for k in (0x11, 0x12, 0x1B)):
                self.event.set()

    def close(self) -> None:
        self.shutdown.set()
        if self.thread.is_alive():
            self.thread.join(1)
