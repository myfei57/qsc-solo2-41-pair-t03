"""Monotonic generation numbers per scope and key."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from tankfarm.errors import StaleGenerationError, UnknownGenerationError

SCOPE_CONFIG = "config"
SCOPE_VALVE_PERSIST = "valve.persist"
SCOPE_GAUGE_CONFIRM = "level.gauge"
SCOPE_BASELINE = "level.baseline"
SCOPE_SNAPSHOT = "journal.snapshot"
CONFIG_KEY = "control"
SNAPSHOT_KEY = "latest"


@dataclass(frozen=True)
class Generation:
    scope: str
    key: str
    number: int
    issued_at: int

    def as_payload(self) -> dict[str, Any]:
        return {
            "scope": self.scope,
            "key": self.key,
            "number": self.number,
            "issued_at": self.issued_at,
        }


class GenerationRegistry:
    """Every bump invalidates documents that carry the earlier number."""

    def __init__(self) -> None:
        self._numbers: dict[tuple[str, str], int] = {}
        self._issued: dict[tuple[str, str], int] = {}

    def bump(self, scope: str, key: str, ts: int) -> Generation:
        marker = (scope, key)
        number = self._numbers.get(marker, 0) + 1
        self._numbers[marker] = number
        self._issued[marker] = int(ts)
        return Generation(scope=scope, key=key, number=number, issued_at=int(ts))

    def current(self, scope: str, key: str) -> int:
        return self._numbers.get((scope, key), 0)

    def generation(self, scope: str, key: str) -> Generation:
        return Generation(
            scope=scope,
            key=key,
            number=self.current(scope, key),
            issued_at=self._issued.get((scope, key), 0),
        )

    def require(self, scope: str, key: str, number: int) -> Generation:
        current = self.current(scope, key)
        if number == current:
            return self.generation(scope, key)
        if number < current:
            raise StaleGenerationError(scope, key, current, number)
        raise UnknownGenerationError(scope, key, current, number)

    def restore(self, scope: str, key: str, number: int, ts: int) -> None:
        """Rebuilds a number while replaying the record stream."""

        marker = (scope, key)
        if number >= self._numbers.get(marker, 0):
            self._numbers[marker] = int(number)
            self._issued[marker] = int(ts)
