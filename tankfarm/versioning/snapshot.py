"""Versioned journal snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from tankfarm.errors import ExpiredSnapshotError, SnapshotNotFoundError
from tankfarm.ids import IdFactory
from tankfarm.versioning.expiry import ExpiryPolicy
from tankfarm.versioning.generation import CONFIG_KEY, SCOPE_CONFIG, GenerationRegistry


@dataclass
class VersionedSnapshot:
    """A projection of the record stream pinned to a watermark and generation."""

    snapshot_id: str
    watermark: int
    generation: int
    config_generation: int
    scope: str
    key: str
    issued_at: int
    policy: ExpiryPolicy
    state: Mapping[str, Any]

    def as_payload(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "watermark": self.watermark,
            "generation": self.generation,
            "config_generation": self.config_generation,
            "issued_at": self.issued_at,
            "state": dict(self.state),
        }


class SnapshotBook:
    """Stores versioned snapshots and refuses stale or expired ones."""

    def __init__(self, ids: IdFactory) -> None:
        self._ids = ids
        self._snapshots: dict[str, VersionedSnapshot] = {}
        self._order: list[str] = []

    def capture(
        self,
        state: Mapping[str, Any],
        watermark: int,
        scope: str,
        key: str,
        generation: int,
        config_generation: int,
        now: int,
        policy: ExpiryPolicy,
    ) -> VersionedSnapshot:
        snapshot = VersionedSnapshot(
            snapshot_id=self._ids.new("snap"),
            watermark=int(watermark),
            generation=int(generation),
            config_generation=int(config_generation),
            scope=scope,
            key=key,
            issued_at=int(now),
            policy=policy,
            state=dict(state),
        )
        self._snapshots[snapshot.snapshot_id] = snapshot
        self._order.append(snapshot.snapshot_id)
        return snapshot

    def get(self, snapshot_id: str) -> VersionedSnapshot:
        snapshot = self._snapshots.get(snapshot_id)
        if snapshot is None:
            raise SnapshotNotFoundError(snapshot_id)
        return snapshot

    def validate(
        self, snapshot_id: str, now: int, registry: GenerationRegistry
    ) -> VersionedSnapshot:
        snapshot = self.get(snapshot_id)
        registry.require(SCOPE_CONFIG, CONFIG_KEY, snapshot.config_generation)
        registry.require(snapshot.scope, snapshot.key, snapshot.generation)
        if snapshot.policy.expired(snapshot.issued_at, now):
            raise ExpiredSnapshotError(
                snapshot_id,
                snapshot.policy.age(snapshot.issued_at, now),
                snapshot.policy.max_age,
            )
        return snapshot

    def latest(self) -> VersionedSnapshot | None:
        if not self._order:
            return None
        return self._snapshots[self._order[-1]]
