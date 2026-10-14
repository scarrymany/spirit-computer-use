from __future__ import annotations

import ctypes as ct
import multiprocessing as mp
import os
import queue
import time
import tkinter as tk
from ctypes import wintypes as wt

from . import native

FRAME_COLOR = "#A78BFA"
POINTER_COLOR = "#67E8F9"
TRANSPARENT_COLOR = "#010101"
FRAME_WIDTH = 3
HALO_RADIUS = 19
VISIBLE_SECONDS = 1.6
POLL_MS = 16
WS_EX_TRANSPARENT = 0x20
WS_EX_TOOLWINDOW = 0x80
WS_EX_LAYERED = 0x80000
WS_EX_NOACTIVATE = 0x8000000


def run_overlay(commands, stop, shutdown, ready, visible: bool) -> None:
    native.initialize()
    root = tk.Tk()
    root.withdraw()
    root.title("SPIRIT Overlay")
    root.overrideredirect(True)
    root.configure(bg=TRANSPARENT_COLOR)
    root.attributes("-transparentcolor", TRANSPARENT_COLOR)
    root.attributes("-topmost", True)
    canvas = tk.Canvas(root, bg=TRANSPARENT_COLOR, highlightthickness=0, borderwidth=0)
    canvas.pack(fill="both", expand=True)
    root.update_idletasks()
    hwnd = native.user32.GetAncestor(root.winfo_id(), native.GA_ROOT)
    style = native.user32.GetWindowLongPtrW(hwnd, -20)
    native.user32.SetWindowLongPtrW(
        hwnd, -20, style | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW | WS_EX_LAYERED | WS_EX_NOACTIVATE
    )
    if os.environ.get("SPIRIT_RECORD_OVERLAY") != "1":
        native.user32.SetWindowDisplayAffinity(hwnd, 0x11)
    deadline = 0.0
    active_bounds = None
    label = ""
    origin = (0, 0)

    def tick():
        nonlocal deadline, active_bounds, label, origin
        parent = mp.parent_process()
        if shutdown.is_set() or (parent is not None and not parent.is_alive()):
            root.destroy()
            return
        if native.emergency_pressed():
            stop.set()
        try:
            while True:
                event = commands.get_nowait()
                active_bounds = event["bounds"]
                label = event["label"]
                deadline = time.monotonic() + event.get("seconds", VISIBLE_SECONDS)
        except queue.Empty:
            pass

        if visible and active_bounds and time.monotonic() < deadline:
            left = native.user32.GetSystemMetrics(76)
            top = native.user32.GetSystemMetrics(77)
            width = native.user32.GetSystemMetrics(78)
            height = native.user32.GetSystemMetrics(79)
            origin = (left, top)
            # SetWindowPos preserves physical negative coordinates on secondary monitors.
            native.user32.SetWindowPos(hwnd, -1, left, top, width, height, 0x0010 | 0x0040)
            canvas.configure(width=width, height=height)
            canvas.delete("all")
            x1, y1, x2, y2 = active_bounds
            x1, x2 = x1 - origin[0], x2 - origin[0]
            y1, y2 = y1 - origin[1], y2 - origin[1]
            color = "#FB7185" if stop.is_set() else FRAME_COLOR
            canvas.create_rectangle(
                x1 + 2, y1 + 2, x2 - 2, y2 - 2, outline=color, width=FRAME_WIDTH
            )
            caption = "SPIRIT  |  STOPPED" if stop.is_set() else f"SPIRIT  |  {label}"
            label_x, label_y = max(5, x1 + 10), max(5, y1 + 10)
            text_id = canvas.create_text(
                label_x + 10,
                label_y + 8,
                anchor="nw",
                text=caption,
                fill="#F5F3FF",
                font=("Segoe UI", 10, "bold"),
            )
            box = canvas.bbox(text_id)
            if box:
                background = canvas.create_rectangle(
                    box[0] - 8, box[1] - 5, box[2] + 8, box[3] + 5, fill="#181325", outline=color
                )
                canvas.tag_lower(background, text_id)
            point = wt.POINT()
            if native.user32.GetCursorPos(ct.byref(point)):
                x, y = point.x - left, point.y - top
                r = HALO_RADIUS
                canvas.create_oval(x - r, y - r, x + r, y + r, outline=POINTER_COLOR, width=3)
                canvas.create_oval(x - 4, y - 4, x + 4, y + 4, outline="#FFFFFF", width=1)
        else:
            native.user32.ShowWindow(hwnd, 0)
        root.after(POLL_MS, tick)

    ready.set()
    root.after(POLL_MS, tick)
    try:
        root.mainloop()
    finally:
        shutdown.set()
