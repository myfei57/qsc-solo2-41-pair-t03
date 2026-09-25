"""Batch identity: a batch identifier may be registered exactly once."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from tankfarm.errors import BatchNotFoundError, DuplicateBatchError


@dataclass(frozen=True)
class BatchRegistration:
    batch_id: str
    tank_id: str
    generation: int
    ts: int

    def as_payload(self) -> dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "tank_id": self.tank_id,
            "generation": self.generation,
            "ts": self.ts,
        }


class BatchRegistry:
    """Guards transfer batches against double registration."""

    def __init__(self) -> None:
        self._batches: dict[str, BatchRegistration] = {}

    def register(
        self, batch_id: str, tank_id: str, generation: int, ts: int
    ) -> BatchRegistration:
        if batch_id in self._batches:
            raise DuplicateBatchError(batch_id, self._batches[batch_id].tank_id)
        registration = BatchRegistration(
            batch_id=batch_id, tank_id=tank_id, generation=int(generation), ts=int(ts)
        )
        self._batches[batch_id] = registration
        return registration

    def get(self, batch_id: str) -> BatchRegistration:
        registration = self._batches.get(batch_id)
        if registration is None:
            raise BatchNotFoundError(batch_id)
        return registration

    def for_tank(self, tank_id: str) -> tuple[BatchRegistration, ...]:
        return tuple(
            item for item in self._batches.values() if item.tank_id == tank_id
        )

    def count(self) -> int:
        return len(self._batches)

    def restore(self, registrations: dict[str, tuple[str, int]]) -> None:
        self._batches = {
            batch_id: BatchRegistration(
                batch_id=batch_id, tank_id=tank_id, generation=generation, ts=0
            )
            for batch_id, (tank_id, generation) in registrations.items()
        }

