"""Tank inventory record."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Tank:
    tank_id: str
    name: str
    capacity_mm: float

    @property
    def valve_id(self) -> str:
        return f"valve-{self.tank_id}"

    def as_payload(self) -> dict[str, Any]:
        return {
            "tank_id": self.tank_id,
            "name": self.name,
            "capacity_mm": self.capacity_mm,
        }

