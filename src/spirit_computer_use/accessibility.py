from __future__ import annotations

import time

from pywinauto import Desktop
from pywinauto.controls.uiawrapper import UIAWrapper
from pywinauto.uia_defines import IUIA, NoPatternInterfaceError
from pywinauto.uia_element_info import UIAElementInfo

from .state import Snapshot

MAX_ELEMENTS = 300
MAX_DEPTH = 16
MAX_TEXT = 12000
TREE_SECONDS = 6.0


def focused(hwnd: int):
    wrapper = UIAWrapper(UIAElementInfo(IUIA().get_focused_element()))
    root = Desktop(backend="uia").window(handle=hwnd).wrapper_object()
    element = wrapper
    for _ in range(40):
        if element == root:
            return wrapper
        element = element.parent()
        if element is None:
            break
    raise RuntimeError("Keyboard focus is outside the selected window")


def require_text_focus(hwnd: int) -> None:
    wrapper = focused(hwnd)
    if wrapper.element_info.element.CurrentIsPassword:
        raise RuntimeError("Password fields require manual input")
    if wrapper.element_info.control_type not in {"Edit", "Document", "ComboBox"}:
        raise RuntimeError("Focus is not an editable surface; click an editor and observe again")


def tree(snapshot: Snapshot) -> dict:
    root = Desktop(backend="uia").window(handle=snapshot.window.id).wrapper_object()
    stack = [(root, 0)]
    lines = []
    selected = []
    selected_text = []
    document = []
    focused_line = None
    deadline = time.monotonic() + TREE_SECONDS
    warnings = []
    while stack and len(snapshot.elements) < MAX_ELEMENTS and time.monotonic() < deadline:
        wrapper, depth = stack.pop()
        try:
            info = wrapper.element_info
            if not wrapper.is_visible():
                continue
            password = bool(info.element.CurrentIsPassword)
            name = "[password]" if password else info.name[:500]
            index = len(snapshot.elements)
            snapshot.elements[index] = wrapper
            rectangle = wrapper.rectangle()
            b = snapshot.bounds
            line = (
                f"{'  ' * depth}[{index}] {info.control_type} {name!r} "
                f"({rectangle.left - b.left},{rectangle.top - b.top},"
                f"{rectangle.right - b.left},{rectangle.bottom - b.top})"
            )
            is_focused = bool(info.element.CurrentHasKeyboardFocus)
            if is_focused:
                focused_line = line
                line += " [focused]"
            if not wrapper.is_enabled():
                line += " [disabled]"
            lines.append(line)
            if not password:
                try:
                    if wrapper.iface_selection_item.CurrentIsSelected:
                        selected.append(line)
                except (NoPatternInterfaceError, AttributeError):
                    pass
                if info.control_type in {"Edit", "Document"}:
                    try:
                        document.append(wrapper.iface_text.DocumentRange.GetText(MAX_TEXT))
                        if is_focused:
                            ranges = wrapper.iface_text.GetSelection()
                            for position in range(min(ranges.Length, 32)):
                                selected_text.append(ranges.GetElement(position).GetText(MAX_TEXT))
                    except (NoPatternInterfaceError, AttributeError):
                        try:
                            document.append(wrapper.iface_value.CurrentValue[:MAX_TEXT])
                        except (NoPatternInterfaceError, AttributeError):
                            pass
            if depth < MAX_DEPTH and not password:
                children = wrapper.children()
                stack.extend((child, depth + 1) for child in reversed(children[:MAX_ELEMENTS]))
        except Exception as error:
            warnings.append(type(error).__name__)
    return {
        "tree": "\n".join(lines),
        "focused_element": focused_line,
        "selected_elements": selected,
        "selected_text": "\n".join(selected_text)[:MAX_TEXT],
        "document_text": "\n".join(document)[:MAX_TEXT],
        "truncated": bool(stack),
        "warnings": sorted(set(warnings)),
    }


def element(snapshot: Snapshot, index: int):
    if index not in snapshot.elements:
        raise ValueError("Unknown element index; get a fresh accessibility snapshot")
    wrapper = snapshot.elements[index]
    if not wrapper.is_visible() or not wrapper.is_enabled():
        raise ValueError("Element is no longer visible and enabled")
    if wrapper.element_info.element.CurrentIsPassword:
        raise RuntimeError("Password fields require manual input")
    return wrapper
