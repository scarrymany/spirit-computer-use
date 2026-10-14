import ctypes
import threading

import pytest

from spirit_computer_use import native


def test_input_structure_matches_windows_x64_abi():
    assert ctypes.sizeof(native.Input) == 40


def test_chord_releases_pressed_keys_when_interrupted(monkeypatch):
    events = []
    stop = threading.Event()

    def record(vk, **kwargs):
        events.append((vk, kwargs.get("up", False)))
        if not kwargs.get("up"):
            stop.set()

    monkeypatch.setattr(native, "key", record)
    monkeypatch.setattr(native, "check_foreground", lambda _: None)
    monkeypatch.setattr(native, "emergency_pressed", lambda: False)
    with pytest.raises(RuntimeError, match="Emergency"):
        native.press_chord(1, "Ctrl+A", stop)
    assert events == [(0x11, False), (0x11, True)]


@pytest.mark.parametrize("value", ["Ctrl+", "Ctrl+Ctrl", "FakeKey", "Win+R"])
def test_unsupported_chords_fail_before_input(value):
    with pytest.raises(ValueError):
        native.parse_chord(value)


def test_numpad_enter_is_extended():
    assert native.parse_chord("KP_Enter") == [(0x0D, True)]


def test_unicode_surrogate_pairs_are_preserved(monkeypatch):
    events = []
    monkeypatch.setattr(native, "key", lambda vk, **kwargs: events.append(kwargs))
    monkeypatch.setattr(native, "check_foreground", lambda _: None)
    monkeypatch.setattr(native, "emergency_pressed", lambda: False)
    native.type_text(1, "A\U0001f680", threading.Event())
    assert [event["scan"] for event in events[::2]] == [65, 0xD83D, 0xDE80]
    assert all(event["up"] for event in events[1::2])


def test_crash_cleanup_releases_only_recorded_inputs(monkeypatch):
    keys = []
    buttons = []
    monkeypatch.setattr(native, "key", lambda vk, **kwargs: keys.append((vk, kwargs)))
    monkeypatch.setattr(native, "mouse", lambda flags: buttons.append(flags))
    ledger = [0] * 258
    ledger[0xA3] = 2
    ledger[native.MOUSE_SLOT] = native.MOUSE_DOWN["left"]
    native.release_inputs(ledger)
    assert keys == [(0xA3, {"up": True, "extended": True})]
    assert buttons == [native.MOUSE_UP["left"]]
    assert not any(ledger)
