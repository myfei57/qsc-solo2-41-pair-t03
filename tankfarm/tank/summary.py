"""Per tank console summary."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from tankfarm.level.service import LevelService
from tankfarm.tank.capacity import CapacityEstimator
from tankfarm.tank.model import Tank


@dataclass(frozen=True)
class TankSummary:
    tank_id: str
    name: str
    capacity_mm: float
    reading: float
    remaining_mm: float
    gauge_id: str
    confirmed: bool

    def as_payload(self) -> dict[str, Any]:
        return {
            "tank_id": self.tank_id,
            "name": self.name,
            "capacity_mm": self.capacity_mm,
            "reading": self.reading,
            "remaining_mm": self.remaining_mm,
            "gauge_id": self.gauge_id,
            "confirmed": self.confirmed,
        }


def build_summary(
    tank: Tank, levels: LevelService, estimator: CapacityEstimator
) -> TankSummary:
    state = levels.state(tank.tank_id)
    return TankSummary(
        tank_id=tank.tank_id,
        name=tank.name,
        capacity_mm=tank.capacity_mm,
        reading=state.reading,
        remaining_mm=estimator.remaining(tank.tank_id),
        gauge_id=state.gauge_id,
        confirmed=state.confirmed,
    )

