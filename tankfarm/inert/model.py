"""Blanket gas state of one tank."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class InertState:
    tank_id: str
    pressure: float
    alarm: bool = False
    confirmed: bool = True
    band: str = "ok"

    def as_payload(self) -> dict[str, Any]:
        return {
            "tank_id": self.tank_id,
            "pressure": self.pressure,
            "alarm": self.alarm,
            "confirmed": self.confirmed,
            "band": self.band,
        }

