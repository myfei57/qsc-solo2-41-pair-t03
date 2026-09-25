"""Current live state and its comparison against a historical projection."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class CurrentView:
    """The live plant state as the console sees it right now."""

    valve_positions: Mapping[str, str] = field(default_factory=dict)
    header_setpoint: float = 0.0
    pumps: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    levels: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    latches: Mapping[str, bool] = field(default_factory=dict)
    stage: str = ""
    watermark: int = 0
    head: int = 0

    def as_payload(self) -> dict[str, Any]:
        return {
            "valves": dict(self.valve_positions),
            "header_setpoint": self.header_setpoint,
            "pumps": {key: dict(value) for key, value in self.pumps.items()},
            "levels": {key: dict(value) for key, value in self.levels.items()},
            "latches": dict(self.latches),
            "stage": self.stage,
            "watermark": self.watermark,
            "head": self.head,
        }

    def differences(self, history: Mapping[str, Any]) -> dict[str, Any]:
        pairs = (
            ("valves", dict(self.valve_positions)),
            ("header_setpoint", self.header_setpoint),
            ("stage", self.stage),
            ("latches", dict(self.latches)),
        )
        report: dict[str, Any] = {}
        for name, current in pairs:
            historical = history.get(name)
            report[name] = {
                "current": current,
                "historical": historical,
                "same": current == historical,
            }
        report["identical"] = all(item["same"] for item in report.values() if isinstance(item, dict))
        return report

