"""Calibration baselines bound to generations and expiry."""

from __future__ import annotations

from tankfarm.clock import LogicalClock
from tankfarm.errors import (
    BaselineNotFoundError,
)
from tankfarm.versioning.baseline import Baseline, BaselineBook
from tankfarm.versioning.expiry import ExpiryPolicy
from tankfarm.versioning.generation import (
    CONFIG_KEY,
    SCOPE_BASELINE,
    SCOPE_CONFIG,
    GenerationRegistry,
)


class BaselineRecorder:
    """Writes baselines and re-validates them before they are trusted."""

    def __init__(
        self,
        baselines: BaselineBook,
        generations: GenerationRegistry,
        clock: LogicalClock,
        policy: ExpiryPolicy,
    ) -> None:
        self._baselines = baselines
        self._generations = generations
        self._clock = clock
        self._policy = policy

    def seed(self, tank_id: str, baseline: float) -> None:
        self._baselines.record(
            tank_id=tank_id,
            value=baseline,
            generation=0,
            config_generation=self._generations.current(SCOPE_CONFIG, CONFIG_KEY),
            now=self._clock.now(),
            policy=self._policy,
        )

    def record(self, tank_id: str, baseline: float, offset: float) -> Baseline:
        now = self._clock.now()
        generation = self._generations.bump(SCOPE_BASELINE, tank_id, now)
        return self._baselines.record(
            tank_id=tank_id,
            value=baseline,
            generation=generation.number,
            config_generation=self._generations.current(SCOPE_CONFIG, CONFIG_KEY),
            now=now,
            policy=self._policy,
        )

    def validate(self, tank_id: str) -> Baseline:
        try:
            return self._baselines.validate(
                tank_id, self._clock.now(), self._generations
            )
        except BaselineNotFoundError:
            raise

