from __future__ import annotations

import io
import threading

from PIL import Image
from windows_capture import WindowsCapture

CAPTURE_TIMEOUT = 8.0
MAX_CAPTURE_PIXELS = 40_000_000


def capture_window(hwnd: int) -> tuple[bytes, int, int]:
    finished = threading.Event()
    frames = []
    errors = []
    capture = WindowsCapture(window_hwnd=hwnd, cursor_capture=False, draw_border=False)

    @capture.event
    def on_frame_arrived(frame, control):
        try:
            if frame.width * frame.height > MAX_CAPTURE_PIXELS:
                raise ValueError("Window exceeds the capture pixel limit")
            frames.append((frame.frame_buffer.copy(), frame.width, frame.height))
        except Exception as error:
            errors.append(error)
        finally:
            control.stop()
            finished.set()

    @capture.event
    def on_closed():
        finished.set()

    control = capture.start_free_threaded()
    try:
        if not finished.wait(CAPTURE_TIMEOUT):
            raise TimeoutError("Window capture timed out; restore or refresh the selected window")
    finally:
        control.stop()
    if errors:
        raise errors[0]
    if not frames:
        raise RuntimeError("Window closed or Windows refused capture")
    pixels, width, height = frames[0]
    image = Image.frombytes("RGBA", (width, height), pixels.tobytes(), "raw", "BGRA")
    output = io.BytesIO()
    image.convert("RGB").save(output, format="PNG")
    return output.getvalue(), width, height
