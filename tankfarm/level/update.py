"""Bounded history of level movements."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class UpdateRecord:
    tank_id: str
    kind: str
    reading: float
    seq: int

    def as_payload(self) -> dict[str, Any]:
        return {
            "tank_id": self.tank_id,
            "kind": self.kind,
            "reading": self.reading,
            "seq": self.seq,
        }


class UpdateLog:
    """Keeps the last few level movements for the console and the tests."""

    def __init__(self, capacity: int) -> None:
        self._capacity = int(capacity)
        self._entries: list[UpdateRecord] = []
        self._counter = 0

    def record(self, tank_id: str, kind: str, reading: float) -> UpdateRecord:
        self._counter += 1
        entry = UpdateRecord(
            tank_id=tank_id, kind=kind, reading=float(reading), seq=self._counter
        )
        self._entries.append(entry)
        if len(self._entries) > self._capacity:
            del self._entries[0 : len(self._entries) - self._capacity]
        return entry

    def recent(self, limit: int) -> tuple[UpdateRecord, ...]:
        if limit <= 0 or limit > len(self._entries):
            return tuple(self._entries)
        return tuple(self._entries[-limit:])

    def clear(self) -> None:
        self._entries.clear()

