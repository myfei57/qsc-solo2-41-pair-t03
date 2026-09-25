"""Control settings and the revision that carries a generation number."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from tankfarm.domain import HIGH_LIMIT_MM, INERT_HIGH_KPA, INERT_LOW_KPA


@dataclass(frozen=True)
class ControlSettings:
    """Everything the control plane reads at start-up."""

    addr: str = "127.0.0.1:8080"
    data_dir: str = "var"
    high_limit_mm: float = HIGH_LIMIT_MM
    inert_low_kpa: float = INERT_LOW_KPA
    inert_high_kpa: float = INERT_HIGH_KPA
    sheet_max_age: int = 40
    baseline_max_age: int = 400
    snapshot_max_age: int = 60

    def with_addr(self, addr: str) -> "ControlSettings":
        return replace(self, addr=addr)

    def with_data_dir(self, data_dir: str) -> "ControlSettings":
        return replace(self, data_dir=data_dir)

    def as_payload(self) -> dict[str, Any]:
        return {
            "addr": self.addr,
            "data_dir": self.data_dir,
            "high_limit_mm": self.high_limit_mm,
            "inert_low_kpa": self.inert_low_kpa,
            "inert_high_kpa": self.inert_high_kpa,
            "sheet_max_age": self.sheet_max_age,
            "baseline_max_age": self.baseline_max_age,
            "snapshot_max_age": self.snapshot_max_age,
        }


DEFAULT_SETTINGS = ControlSettings()


@dataclass(frozen=True)
class ConfigRevision:
    """One activated settings revision."""

    generation: int
    settings: ControlSettings
    issued_at: int

    def as_payload(self) -> dict[str, Any]:
        return {
            "generation": self.generation,
            "issued_at": self.issued_at,
            "settings": self.settings.as_payload(),
        }
