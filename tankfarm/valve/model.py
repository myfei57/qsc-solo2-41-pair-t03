"""Valve device state."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from tankfarm.domain import POSITION_CLOSED, POSITION_OPEN


@dataclass
class Valve:
    """One movable valve with its last durable write marker."""

    valve_id: str
    name: str
    position: str = POSITION_CLOSED
    persisted: bool = False
    updated_at: int = 0

    def is_open(self) -> bool:
        return self.position == POSITION_OPEN

    def is_closed(self) -> bool:
        return self.position == POSITION_CLOSED

    def move_to(self, position: str, ts: int) -> None:
        self.position = position
        self.persisted = False
        self.updated_at = int(ts)

    def mark_persisted(self, ts: int) -> None:
        self.persisted = True
        self.updated_at = int(ts)

    def as_payload(self) -> dict[str, Any]:
        return {
            "valve_id": self.valve_id,
            "name": self.name,
            "position": self.position,
            "persisted": self.persisted,
        }
