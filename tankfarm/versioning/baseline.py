"""Versioned level baselines."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from tankfarm.errors import (
    BaselineNotFoundError,
    ExpiredBaselineError,
)
from tankfarm.versioning.expiry import ExpiryPolicy
from tankfarm.versioning.generation import (
    CONFIG_KEY,
    SCOPE_BASELINE,
    SCOPE_CONFIG,
    GenerationRegistry,
)


@dataclass
class Baseline:
    """Reference level captured for one tank at a known generation."""

    tank_id: str
    value: float
    generation: int
    config_generation: int
    issued_at: int
    policy: ExpiryPolicy

    def as_payload(self) -> dict[str, Any]:
        return {
            "tank_id": self.tank_id,
            "value": self.value,
            "generation": self.generation,
            "config_generation": self.config_generation,
            "issued_at": self.issued_at,
        }


class BaselineBook:
    """Keeps the newest baseline per tank and validates it on read."""

    def __init__(self) -> None:
        self._baselines: dict[str, Baseline] = {}

    def record(
        self,
        tank_id: str,
        value: float,
        generation: int,
        config_generation: int,
        now: int,
        policy: ExpiryPolicy,
    ) -> Baseline:
        baseline = Baseline(
            tank_id=tank_id,
            value=float(value),
            generation=int(generation),
            config_generation=int(config_generation),
            issued_at=int(now),
            policy=policy,
        )
        self._baselines[tank_id] = baseline
        return baseline

    def get(self, tank_id: str) -> Baseline:
        baseline = self._baselines.get(tank_id)
        if baseline is None:
            raise BaselineNotFoundError(tank_id)
        return baseline

    def validate(
        self, tank_id: str, now: int, registry: GenerationRegistry
    ) -> Baseline:
        baseline = self.get(tank_id)
        registry.require(SCOPE_CONFIG, CONFIG_KEY, baseline.config_generation)
        registry.require(SCOPE_BASELINE, tank_id, baseline.generation)
        if baseline.policy.expired(baseline.issued_at, now):
            raise ExpiredBaselineError(
                tank_id,
                baseline.policy.age(baseline.issued_at, now),
                baseline.policy.max_age,
            )
        return baseline

    def values(self) -> dict[str, float]:
        return {tank_id: item.value for tank_id, item in self._baselines.items()}
