from __future__ import annotations

import ctypes as ct
import os
import sys
import time
from contextlib import contextmanager
from ctypes import wintypes as wt

import psutil

from .state import Bounds, Window

if sys.platform != "win32":
    raise RuntimeError("SPIRIT Computer Use requires Windows 11")

user32 = ct.WinDLL("user32", use_last_error=True)
kernel32 = ct.WinDLL("kernel32", use_last_error=True)
dwmapi = ct.WinDLL("dwmapi", use_last_error=True)
ULONG_PTR = ct.c_size_t
WNDENUMPROC = ct.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)


def bind(dll, name, result, *args):
    function = getattr(dll, name)
    function.restype = result
    function.argtypes = args
    return function


bind(user32, "EnumWindows", wt.BOOL, WNDENUMPROC, wt.LPARAM)
bind(user32, "IsWindow", wt.BOOL, wt.HWND)
bind(user32, "IsWindowVisible", wt.BOOL, wt.HWND)
bind(user32, "IsIconic", wt.BOOL, wt.HWND)
bind(user32, "GetWindowTextLengthW", ct.c_int, wt.HWND)
bind(user32, "GetWindowTextW", ct.c_int, wt.HWND, wt.LPWSTR, ct.c_int)
bind(user32, "GetWindowThreadProcessId", wt.DWORD, wt.HWND, ct.POINTER(wt.DWORD))
bind(user32, "GetWindowRect", wt.BOOL, wt.HWND, ct.POINTER(wt.RECT))
bind(user32, "SetForegroundWindow", wt.BOOL, wt.HWND)
bind(user32, "AttachThreadInput", wt.BOOL, wt.DWORD, wt.DWORD, wt.BOOL)
bind(user32, "PeekMessageW", wt.BOOL, ct.POINTER(wt.MSG), wt.HWND, wt.UINT, wt.UINT, wt.UINT)
bind(user32, "BringWindowToTop", wt.BOOL, wt.HWND)
bind(kernel32, "GetCurrentThreadId", wt.DWORD)
bind(user32, "GetForegroundWindow", wt.HWND)
bind(user32, "GetAncestor", wt.HWND, wt.HWND, wt.UINT)
bind(user32, "ShowWindow", wt.BOOL, wt.HWND, ct.c_int)
bind(user32, "WindowFromPoint", wt.HWND, wt.POINT)
bind(user32, "SetCursorPos", wt.BOOL, ct.c_int, ct.c_int)
bind(user32, "GetCursorPos", wt.BOOL, ct.POINTER(wt.POINT))
bind(user32, "GetAsyncKeyState", wt.SHORT, ct.c_int)
bind(user32, "SetProcessDpiAwarenessContext", wt.BOOL, ct.c_void_p)
bind(user32, "GetSystemMetrics", ct.c_int, ct.c_int)
bind(user32, "GetWindowLongPtrW", ct.c_ssize_t, wt.HWND, ct.c_int)
bind(user32, "SetWindowLongPtrW", ct.c_ssize_t, wt.HWND, ct.c_int, ct.c_ssize_t)
bind(
    user32,
    "SetWindowPos",
    wt.BOOL,
    wt.HWND,
    wt.HWND,
    ct.c_int,
    ct.c_int,
    ct.c_int,
    ct.c_int,
    wt.UINT,
)
bind(user32, "SetWindowDisplayAffinity", wt.BOOL, wt.HWND, wt.DWORD)
bind(user32, "OpenInputDesktop", wt.HANDLE, wt.DWORD, wt.BOOL, wt.DWORD)
bind(user32, "CloseDesktop", wt.BOOL, wt.HANDLE)
bind(
    user32,
    "GetUserObjectInformationW",
    wt.BOOL,
    wt.HANDLE,
    ct.c_int,
    ct.c_void_p,
    wt.DWORD,
    ct.POINTER(wt.DWORD),
)
bind(kernel32, "CreateMutexW", wt.HANDLE, ct.c_void_p, wt.BOOL, wt.LPCWSTR)
bind(kernel32, "WaitForSingleObject", wt.DWORD, wt.HANDLE, wt.DWORD)
bind(kernel32, "ReleaseMutex", wt.BOOL, wt.HANDLE)
bind(kernel32, "CloseHandle", wt.BOOL, wt.HANDLE)
bind(dwmapi, "DwmGetWindowAttribute", ct.c_long, wt.HWND, wt.DWORD, ct.c_void_p, wt.DWORD)

GA_ROOT = 2
DWMWA_EXTENDED_FRAME_BOUNDS = 9
DWMWA_CLOAKED = 14
INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
KEYEVENTF_EXTENDEDKEY = 0x0001
MOUSE_DOWN = {"left": 0x0002, "right": 0x0008, "middle": 0x0020}
MOUSE_UP = {"left": 0x0004, "right": 0x0010, "middle": 0x0040}
MOUSE_WHEEL = 0x0800
MOUSE_HWHEEL = 0x1000
VK_PAUSE = 0x13
VK_ESCAPE = 0x1B
VK_CONTROL = 0x11
VK_MENU = 0x12
MAX_TEXT_LENGTH = 20000
UNICODE_SLOT = 256
MOUSE_SLOT = 257
held_inputs = None


class MouseInput(ct.Structure):
    _fields_ = [
        ("dx", wt.LONG),
        ("dy", wt.LONG),
        ("mouseData", wt.DWORD),
        ("dwFlags", wt.DWORD),
        ("time", wt.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class KeyboardInput(ct.Structure):
    _fields_ = [
        ("wVk", wt.WORD),
        ("wScan", wt.WORD),
        ("dwFlags", wt.DWORD),
        ("time", wt.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class HardwareInput(ct.Structure):
    _fields_ = [("uMsg", wt.DWORD), ("wParamL", wt.WORD), ("wParamH", wt.WORD)]


class InputUnion(ct.Union):
    _fields_ = [("mi", MouseInput), ("ki", KeyboardInput), ("hi", HardwareInput)]


class Input(ct.Structure):
    _anonymous_ = ("value",)
    _fields_ = [("type", wt.DWORD), ("value", InputUnion)]


bind(user32, "SendInput", wt.UINT, wt.UINT, ct.POINTER(Input), ct.c_int)


def initialize() -> None:
    if sys.getwindowsversion().build < 22000:
        raise RuntimeError("Windows 11 build 22000 or newer is required")
    user32.SetProcessDpiAwarenessContext(ct.c_void_p(-4))


def ensure_desktop() -> None:
    desktop = user32.OpenInputDesktop(0, False, 0x0001)
    if not desktop:
        raise RuntimeError("Desktop is locked or inaccessible; unlock Windows manually")
    try:
        name = ct.create_unicode_buffer(256)
        needed = wt.DWORD()
        if not user32.GetUserObjectInformationW(
            desktop, 2, name, ct.sizeof(name), ct.byref(needed)
        ):
            raise ct.WinError(ct.get_last_error())
        if name.value.casefold() != "default":
            raise RuntimeError("Secure desktop is active; return to the normal desktop manually")
    finally:
        user32.CloseDesktop(desktop)


def title(hwnd: int) -> str:
    buffer = ct.create_unicode_buffer(user32.GetWindowTextLengthW(hwnd) + 1)
    user32.GetWindowTextW(hwnd, buffer, len(buffer))
    return buffer.value


def describe(hwnd: int) -> Window:
    if not user32.IsWindow(hwnd):
        raise ValueError("Window no longer exists; list_windows again")
    pid = wt.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ct.byref(pid))
    process = psutil.Process(pid.value)
    return Window(
        id=hwnd, pid=pid.value, created=process.create_time(), app=process.exe(), title=title(hwnd)
    )


def validate(window: Window) -> Window:
    current = describe(window.id)
    if (current.pid, current.created, current.app.casefold()) != (
        window.pid,
        window.created,
        window.app.casefold(),
    ):
        raise ValueError("Window identity changed; list_windows again")
    return current


def bounds(hwnd: int) -> Bounds:
    rectangle = wt.RECT()
    result = dwmapi.DwmGetWindowAttribute(
        hwnd, DWMWA_EXTENDED_FRAME_BOUNDS, ct.byref(rectangle), ct.sizeof(rectangle)
    )
    if result != 0 and not user32.GetWindowRect(hwnd, ct.byref(rectangle)):
        raise ct.WinError(ct.get_last_error())
    return Bounds(rectangle.left, rectangle.top, rectangle.right, rectangle.bottom)


def list_windows() -> list[dict]:
    result = []

    @WNDENUMPROC
    def callback(hwnd, _):
        if not user32.IsWindowVisible(hwnd) or not title(hwnd):
            return True
        cloaked = wt.DWORD()
        dwmapi.DwmGetWindowAttribute(hwnd, DWMWA_CLOAKED, ct.byref(cloaked), ct.sizeof(cloaked))
        if cloaked.value:
            return True
        try:
            item = describe(hwnd)
            if item.pid != os.getpid() and not item.title.startswith("SPIRIT Overlay"):
                result.append(item.model_dump())
        except (psutil.Error, OSError, ValueError):
            pass
        return True

    if not user32.EnumWindows(callback, 0):
        raise ct.WinError(ct.get_last_error())
    return result


@contextmanager
def desktop_lock():
    handle = kernel32.CreateMutexW(None, False, "Local\\SPIRIT.ComputerUse.Input.v1")
    if not handle:
        raise ct.WinError(ct.get_last_error())
    acquired = False
    try:
        acquired = kernel32.WaitForSingleObject(handle, 5000) in (0, 0x80)
        if not acquired:
            raise RuntimeError("Another SPIRIT client is using the desktop; retry after observing")
        ensure_desktop()
        yield
    finally:
        if acquired:
            kernel32.ReleaseMutex(handle)
        kernel32.CloseHandle(handle)


def activate(window: Window) -> None:
    validate(window)
    if user32.IsIconic(window.id):
        user32.ShowWindow(window.id, 9)
    user32.SetForegroundWindow(window.id)
    if user32.GetForegroundWindow() != window.id:
        message = wt.MSG()
        user32.PeekMessageW(ct.byref(message), None, 0, 0, 0)
        foreground_thread = user32.GetWindowThreadProcessId(user32.GetForegroundWindow(), None)
        current_thread = kernel32.GetCurrentThreadId()
        target_thread = user32.GetWindowThreadProcessId(window.id, None)
        attached = []
        # Adapted from Windows-MCP's bring_window_to_top (MIT; see THIRD_PARTY_NOTICES).
        try:
            for thread in dict.fromkeys((foreground_thread, target_thread)):
                if thread and thread != current_thread:
                    if user32.AttachThreadInput(current_thread, thread, True):
                        attached.append(thread)
            user32.SetForegroundWindow(window.id)
            user32.BringWindowToTop(window.id)
        finally:
            for thread in reversed(attached):
                user32.AttachThreadInput(current_thread, thread, False)
    for _ in range(20):
        if user32.GetForegroundWindow() == window.id:
            return
        time.sleep(0.025)
    raise RuntimeError(
        f"Windows refused focus: target={window.id}, "
        f"foreground={user32.GetForegroundWindow()}; select the foreground window"
    )


def check_foreground(hwnd: int) -> None:
    if user32.GetForegroundWindow() != hwnd:
        raise RuntimeError(
            "Focus changed during input; outcome may be partial. Observe before retrying"
        )


def emergency_pressed() -> bool:
    def down(key):
        return bool(user32.GetAsyncKeyState(key) & 0x8000)

    return down(VK_PAUSE) or (down(VK_CONTROL) and down(VK_MENU) and down(VK_ESCAPE))


def check_stop(stop) -> None:
    if emergency_pressed():
        stop.set()
    if stop.is_set():
        raise RuntimeError("Emergency stop is latched; resume only at the user's request")


def move(hwnd: int, x: int, y: int, stop) -> None:
    check_stop(stop)
    check_foreground(hwnd)
    target = user32.WindowFromPoint(wt.POINT(x, y))
    if user32.GetAncestor(target, GA_ROOT) != hwnd:
        raise RuntimeError("Point is covered by another window; observe again")
    if not user32.SetCursorPos(x, y):
        raise ct.WinError(ct.get_last_error())


def send(item: Input) -> None:
    if user32.SendInput(1, ct.byref(item), ct.sizeof(Input)) != 1:
        raise RuntimeError("SendInput was rejected; target may have higher integrity")


def mouse(flags: int, data: int = 0) -> None:
    item = Input(type=INPUT_MOUSE)
    item.mi = MouseInput(0, 0, data & 0xFFFFFFFF, flags, 0, 0)
    if held_inputs is not None and flags in MOUSE_DOWN.values():
        held_inputs[MOUSE_SLOT] |= flags
    send(item)
    if held_inputs is not None:
        for button, up_flag in MOUSE_UP.items():
            if flags == up_flag:
                held_inputs[MOUSE_SLOT] &= ~MOUSE_DOWN[button]


def key(
    vk: int, *, up: bool = False, scan: int = 0, unicode: bool = False, extended: bool = False
) -> None:
    flags = KEYEVENTF_KEYUP if up else 0
    if unicode:
        flags |= KEYEVENTF_UNICODE
    if extended:
        flags |= KEYEVENTF_EXTENDEDKEY
    item = Input(type=INPUT_KEYBOARD)
    item.ki = KeyboardInput(vk, scan, flags, 0, 0)
    slot = UNICODE_SLOT if unicode else vk
    if held_inputs is not None and not up:
        held_inputs[slot] = (scan + 1) if unicode else (2 if extended else 1)
    send(item)
    if held_inputs is not None and up:
        held_inputs[slot] = 0


def release_inputs(ledger) -> None:
    for vk in range(256):
        if ledger[vk]:
            key(vk, up=True, extended=ledger[vk] == 2)
            ledger[vk] = 0
    if ledger[UNICODE_SLOT]:
        key(0, scan=ledger[UNICODE_SLOT] - 1, unicode=True, up=True)
        ledger[UNICODE_SLOT] = 0
    for button, flag in MOUSE_DOWN.items():
        if ledger[MOUSE_SLOT] & flag:
            mouse(MOUSE_UP[button])
            ledger[MOUSE_SLOT] &= ~flag


KEYS = {
    "ctrl": 0x11,
    "control": 0x11,
    "control_l": 0xA2,
    "control_r": 0xA3,
    "shift": 0x10,
    "shift_l": 0xA0,
    "shift_r": 0xA1,
    "alt": 0x12,
    "alt_l": 0xA4,
    "alt_r": 0xA5,
    "enter": 0x0D,
    "return": 0x0D,
    "tab": 0x09,
    "escape": 0x1B,
    "esc": 0x1B,
    "space": 0x20,
    "backspace": 0x08,
    "delete": 0x2E,
    "insert": 0x2D,
    "home": 0x24,
    "end": 0x23,
    "pageup": 0x21,
    "prior": 0x21,
    "pagedown": 0x22,
    "next": 0x22,
    "left": 0x25,
    "up": 0x26,
    "right": 0x27,
    "down": 0x28,
    "period": 0xBE,
    "comma": 0xBC,
    "slash": 0xBF,
    "semicolon": 0xBA,
    "apostrophe": 0xDE,
    "minus": 0xBD,
    "equal": 0xBB,
    "bracketleft": 0xDB,
    "bracketright": 0xDD,
    "backslash": 0xDC,
    "grave": 0xC0,
    "kp_add": 0x6B,
    "kp_subtract": 0x6D,
    "kp_multiply": 0x6A,
    "kp_divide": 0x6F,
    "kp_decimal": 0x6E,
    "kp_enter": 0x0D,
}
KEYS.update({f"f{i}": 0x6F + i for i in range(1, 25)})
KEYS.update({f"kp_{i}": 0x60 + i for i in range(10)})
EXTENDED_KEYS = {0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28, 0x2D, 0x2E, 0x6F, 0xA3, 0xA5}


def parse_chord(chord: str) -> list[tuple[int, bool]]:
    parts = [part.strip().casefold().replace("numpad_", "kp_") for part in chord.split("+")]
    if not 1 <= len(parts) <= 6 or any(not part for part in parts):
        raise ValueError("Use a key or a chord such as Ctrl+Shift+S")
    result = []
    for part in parts:
        vk = KEYS.get(part)
        if vk is None and len(part) == 1 and part.isascii() and part.isalnum():
            vk = ord(part.upper())
        if vk is None:
            raise ValueError(f"Unsupported key: {part}. Use type_text for literal text")
        result.append((vk, vk in EXTENDED_KEYS or part == "kp_enter"))
    if len(set(result)) != len(result):
        raise ValueError("A chord cannot contain duplicate keys")
    return result


def press_chord(hwnd: int, chord: str, stop) -> None:
    keys = parse_chord(chord)
    held = []
    try:
        for vk, extended in keys:
            check_stop(stop)
            check_foreground(hwnd)
            key(vk, extended=extended)
            held.append((vk, extended))
        time.sleep(0.03)
    finally:
        for vk, extended in reversed(held):
            key(vk, up=True, extended=extended)


def type_text(hwnd: int, text: str, stop) -> None:
    if not text or len(text) > MAX_TEXT_LENGTH or "\x00" in text:
        raise ValueError(f"Text must contain 1..{MAX_TEXT_LENGTH} characters without NUL")
    data = text.encode("utf-16-le")
    for index in range(0, len(data), 2):
        check_stop(stop)
        check_foreground(hwnd)
        code = int.from_bytes(data[index : index + 2], "little")
        key(0, scan=code, unicode=True)
        key(0, scan=code, unicode=True, up=True)
