"""Logical clock used instead of wall-clock time."""

from __future__ import annotations


class LogicalClock:
    """Monotonic tick source; every service shares one instance."""

    def __init__(self, start: int = 1_700_000_000) -> None:
        self._value = int(start)

    def now(self) -> int:
        return self._value

    def tick(self, step: int = 1) -> int:
        if step <= 0:
            raise ValueError("tick step must be positive")
        self._value += step
        return self._value

    def age(self, since: int) -> int:
        return self._value - since

