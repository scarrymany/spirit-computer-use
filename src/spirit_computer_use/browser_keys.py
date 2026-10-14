from __future__ import annotations

SPECIAL_KEYS = {
    "Enter": ("Enter", 13),
    "Tab": ("Tab", 9),
    "Escape": ("Escape", 27),
    "Backspace": ("Backspace", 8),
    "Delete": ("Delete", 46),
    "Space": (" ", 32),
    "ArrowLeft": ("ArrowLeft", 37),
    "ArrowUp": ("ArrowUp", 38),
    "ArrowRight": ("ArrowRight", 39),
    "ArrowDown": ("ArrowDown", 40),
    "Home": ("Home", 36),
    "End": ("End", 35),
    "PageUp": ("PageUp", 33),
    "PageDown": ("PageDown", 34),
}
MODIFIERS = {"Alt": (1, 18), "Control": (2, 17), "Meta": (4, 91), "Shift": (8, 16)}
ALIASES = {
    "Ctrl": "Control",
    "Return": "Enter",
    "Esc": "Escape",
    "Left": "ArrowLeft",
    "Right": "ArrowRight",
    "Up": "ArrowUp",
    "Down": "ArrowDown",
}


def key_events(chord: str) -> list[dict]:
    parts = [ALIASES.get(part, part) for part in chord.split("+")]
    key = parts[-1]
    modifiers = parts[:-1]
    if len(set(modifiers)) != len(modifiers) or any(m not in MODIFIERS for m in modifiers):
        raise ValueError("Use chords such as Control+A, Shift+Tab or ArrowDown")
    mask = sum(MODIFIERS[m][0] for m in modifiers)
    if key in SPECIAL_KEYS:
        value, code = SPECIAL_KEYS[key]
        physical = "Space" if key == "Space" else value
    elif len(key) == 1 and key.isascii() and key.isalnum():
        value, code = key, ord(key.upper())
        physical = ("Key" if key.isalpha() else "Digit") + key.upper()
    elif key.startswith("F") and key[1:].isdigit() and 1 <= int(key[1:]) <= 12:
        value, code, physical = key, 111 + int(key[1:]), key
    else:
        raise ValueError("Unsupported key. Use type_text for literal Unicode or punctuation")
    events = [
        {
            "type": "keyDown",
            "key": m,
            "code": m + "Left",
            "windowsVirtualKeyCode": MODIFIERS[m][1],
            "modifiers": mask,
        }
        for m in modifiers
    ]
    event = {"key": value, "code": physical, "windowsVirtualKeyCode": code, "modifiers": mask}
    text = "\r" if value == "Enter" else value if len(value) == 1 else ""
    if text and not mask & 7:
        event["text"] = text
        event["unmodifiedText"] = text
    events += [
        {"type": "keyDown", **event},
        {
            "type": "keyUp",
            **{k: v for k, v in event.items() if k not in {"text", "unmodifiedText"}},
        },
    ]
    events += [
        {
            "type": "keyUp",
            "key": m,
            "code": m + "Left",
            "windowsVirtualKeyCode": MODIFIERS[m][1],
            "modifiers": 0,
        }
        for m in reversed(modifiers)
    ]
    return events
