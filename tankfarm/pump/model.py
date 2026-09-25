"""Transfer pump device."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class Pump:
    pump_id: str
    name: str
    valve_id: str
    running: bool = False
    setpoint: float = 0.0

    def as_payload(self) -> dict[str, Any]:
        return {
            "pump_id": self.pump_id,
            "name": self.name,
            "valve_id": self.valve_id,
            "running": self.running,
            "setpoint": self.setpoint,
        }

