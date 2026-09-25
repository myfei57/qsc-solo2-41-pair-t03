"""Threshold and window policies for the process values."""

from __future__ import annotations

from typing import Any

from tankfarm.measure import Threshold, Window


class LevelLimits:
    """Overfill decision policy for tank levels."""

    def __init__(self, high_limit_mm: float) -> None:
        self._high_limit_mm = float(high_limit_mm)

    def high_limit(self) -> float:
        return self._high_limit_mm

    def at_high(self, reading: float) -> bool:
        return Threshold(self._high_limit_mm).at_or_above(reading)

    def below(self, reading: float) -> bool:
        return Threshold(self._high_limit_mm).below(reading)

    def update(self, high_limit_mm: float) -> None:
        self._high_limit_mm = float(high_limit_mm)

    def as_payload(self) -> dict[str, Any]:
        return {"high_limit_mm": self._high_limit_mm}


class BlanketLimits:
    """Blanket gas pressure window for the inerting system."""

    def __init__(self, low_kpa: float, high_kpa: float) -> None:
        self._low_kpa = float(low_kpa)
        self._high_kpa = float(high_kpa)

    def window(self) -> Window:
        return Window(self._low_kpa, self._high_kpa)

    def confirmed(self, pressure: float) -> bool:
        return self.window().contains(pressure)

    def classify(self, pressure: float) -> str:
        return self.window().classify(pressure)

    def update(self, low_kpa: float, high_kpa: float) -> None:
        self._low_kpa = float(low_kpa)
        self._high_kpa = float(high_kpa)

    def as_payload(self) -> dict[str, Any]:
        payload = {"low_kpa": self._low_kpa, "high_kpa": self._high_kpa}
        return payload

