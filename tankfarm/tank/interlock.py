"""Pre-gate bundle evaluated before a transfer may start."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from tankfarm.clock import LogicalClock
from tankfarm.errors import LevelTooHighError
from tankfarm.judgement.limits import LevelLimits
from tankfarm.level.service import LevelService
from tankfarm.versioning.baseline import BaselineBook
from tankfarm.versioning.generation import GenerationRegistry


@dataclass(frozen=True)
class InterlockReport:
    tank_id: str
    gauge_id: str
    reading: float
    raw_reading: float
    limit: float
    overfilled: bool
    safe: bool

    def as_payload(self) -> dict[str, Any]:
        return {
            "tank_id": self.tank_id,
            "gauge_id": self.gauge_id,
            "reading": self.reading,
            "raw_reading": self.raw_reading,
            "limit": self.limit,
            "overfilled": self.overfilled,
            "safe": self.safe,
        }


class TransferInterlock:
    """Requires a confirmed gauge, a safe level and a live baseline."""

    def __init__(
        self,
        levels: LevelService,
        limits: LevelLimits,
        baselines: BaselineBook,
        generations: GenerationRegistry,
        clock: LogicalClock,
    ) -> None:
        self._levels = levels
        self._limits = limits
        self._baselines = baselines
        self._generations = generations
        self._clock = clock

    def report(self, tank_id: str) -> InterlockReport:
        reading = self._levels.read_confirmed(tank_id)
        return InterlockReport(
            tank_id=tank_id,
            gauge_id=self._levels.gauge_of(tank_id),
            reading=reading,
            raw_reading=self._levels.read_raw(tank_id),
            limit=self._limits.high_limit(),
            overfilled=self._limits.at_high(reading),
            safe=self._limits.below(reading),
        )

    def require_ready(self, tank_id: str) -> InterlockReport:
        report = self.report(tank_id)
        if report.overfilled:
            raise LevelTooHighError(tank_id, report.reading, report.limit)
        self._baselines.validate(tank_id, self._clock.now(), self._generations)
        return report
