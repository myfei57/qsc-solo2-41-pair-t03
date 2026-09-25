"""Generation numbering and expiry for confirmations, baselines and snapshots."""

from __future__ import annotations

from tankfarm.versioning.baseline import Baseline, BaselineBook
from tankfarm.versioning.expiry import ExpiryPolicy
from tankfarm.versioning.generation import Generation, GenerationRegistry
from tankfarm.versioning.sheet import (
    STATE_CONSUMED,
    STATE_EXPIRED,
    STATE_OPEN,
    ConfirmationSheet,
    SheetBook,
)
from tankfarm.versioning.snapshot import SnapshotBook, VersionedSnapshot

__all__ = [
    "Baseline",
    "BaselineBook",
    "ConfirmationSheet",
    "ExpiryPolicy",
    "Generation",
    "GenerationRegistry",
    "STATE_CONSUMED",
    "STATE_EXPIRED",
    "STATE_OPEN",
    "SheetBook",
    "SnapshotBook",
    "VersionedSnapshot",
]
