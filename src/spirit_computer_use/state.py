from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

SNAPSHOT_TTL = 120.0
MAX_SNAPSHOTS = 16


class Window(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    id: int = Field(gt=0)
    pid: int = Field(gt=0)
    created: float
    app: str
    title: str


@dataclass(frozen=True)
class Bounds:
    left: int
    top: int
    right: int
    bottom: int

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top

    def point(self, x: int, y: int) -> tuple[int, int]:
        if (
            isinstance(x, bool)
            or isinstance(y, bool)
            or not isinstance(x, int)
            or not isinstance(y, int)
        ):
            raise ValueError("Coordinates must be integer physical pixels")
        if not (0 <= x < self.width and 0 <= y < self.height):
            raise ValueError("Coordinates are outside the selected window")
        return self.left + x, self.top + y


@dataclass
class Snapshot:
    window: Window
    bounds: Bounds
    elements: dict[int, Any] = field(default_factory=dict)
    created: float = field(default_factory=time.monotonic)
    id: str = field(default_factory=lambda: uuid.uuid4().hex)


class Snapshots:
    def __init__(self) -> None:
        self._items: dict[str, Snapshot] = {}

    def add(self, snapshot: Snapshot) -> str:
        self.invalidate(snapshot.window.id)
        if len(self._items) >= MAX_SNAPSHOTS:
            self._items.pop(next(iter(self._items)))
        self._items[snapshot.id] = snapshot
        return snapshot.id

    def require(self, snapshot_id: str, window: Window, bounds: Bounds) -> Snapshot:
        state = self._items.get(snapshot_id)
        if state is None or time.monotonic() - state.created > SNAPSHOT_TTL:
            raise ValueError("Snapshot is missing or expired; call get_window_state again")
        if (state.window.id, state.window.pid, state.window.created) != (
            window.id,
            window.pid,
            window.created,
        ):
            raise ValueError("Snapshot belongs to a different window")
        if state.bounds != bounds:
            raise ValueError("Window moved or resized; call get_window_state again")
        return state

    def invalidate(self, window_id: int) -> None:
        self._items = {
            key: item for key, item in self._items.items() if item.window.id != window_id
        }
