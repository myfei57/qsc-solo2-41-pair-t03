"""Inlet valve state."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class InletState:
    tank_id: str
    valve_id: str
    open: bool = False

    def as_payload(self) -> dict[str, Any]:
        return {"tank_id": self.tank_id, "valve_id": self.valve_id, "open": self.open}

