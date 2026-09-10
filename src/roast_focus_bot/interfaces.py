from __future__ import annotations

from collections.abc import Callable
from typing import Protocol


class Clock(Protocol):
    def monotonic(self) -> float: ...


class ActiveWindowProvider(Protocol):
    def title(self) -> str: ...


class ActivityTracker(Protocol):
    @property
    def last_activity(self) -> float: ...

    def start(self) -> None: ...

    def stop(self) -> None: ...


class Enforcer(Protocol):
    def enforce(self, category: str, message: str) -> None: ...


class StopSignal(Protocol):
    def is_set(self) -> bool: ...


Notify = Callable[[str], None]
