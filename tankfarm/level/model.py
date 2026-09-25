"""Level state of one tank."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class LevelState:
    """Reading, calibration and gauge confirmation for one tank."""

    tank_id: str
    gauge_id: str
    reading: float
    baseline: float
    offset: float
    confirmed: bool
    generation: int = 0
    pending_sheet: str | None = None

    def as_payload(self) -> dict[str, Any]:
        return {
            "tank_id": self.tank_id,
            "gauge_id": self.gauge_id,
            "reading": self.reading,
            "baseline": self.baseline,
            "offset": self.offset,
            "confirmed": self.confirmed,
            "generation": self.generation,
            "pending_sheet": self.pending_sheet,
        }

