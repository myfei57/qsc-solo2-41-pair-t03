"""Comparison primitives used by every threshold decision."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Threshold:
    """A single limit with the two comparisons the control logic needs."""

    limit: float

    def at_or_above(self, value: float) -> bool:
        return value >= self.limit

    def below(self, value: float) -> bool:
        return value < self.limit


@dataclass(frozen=True)
class Window:
    """An inclusive band with a three way classification."""

    low: float
    high: float

    def contains(self, value: float) -> bool:
        return self.low <= value <= self.high

    def classify(self, value: float) -> str:
        if value < self.low:
            return "low"
        if value > self.high:
            return "high"
        return "ok"
