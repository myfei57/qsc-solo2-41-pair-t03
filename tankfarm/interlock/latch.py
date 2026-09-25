"""Latch state value object."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class LatchState:
    name: str
    active: bool = False
    reason: str = ""
    changed_at: int = 0

    def as_payload(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "active": self.active,
            "reason": self.reason,
            "changed_at": self.changed_at,
        }

