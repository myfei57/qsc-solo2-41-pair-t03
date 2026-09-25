"""Rollback expressed as an appended tombstone record."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tankfarm.errors import (
    DuplicateTombstoneError,
    RollbackTargetError,
    UncommittedRecordError,
)
from tankfarm.journal.commit import CommitController
from tankfarm.journal.record import Record

if TYPE_CHECKING:  # pragma: no cover - import cycle guard
    from tankfarm.journal.writer import JournalWriter

TOMBSTONE_KIND = "journal.tombstone"


class TombstoneIndex:
    """Remembers which record sequences were rolled back."""

    def __init__(self) -> None:
        self._targets: set[int] = set()

    def mark(self, seq: int) -> bool:
        if seq in self._targets:
            return False
        self._targets.add(seq)
        return True

    def is_tombstoned(self, seq: int) -> bool:
        return seq in self._targets

    def targets(self) -> tuple[int, ...]:
        return tuple(sorted(self._targets))


class RollbackService:
    """Rolls a committed record back without rewriting history."""

    def __init__(
        self, journal: "JournalWriter", commits: CommitController, index: TombstoneIndex
    ) -> None:
        self._journal = journal
        self._commits = commits
        self._index = index

    def rollback(self, seq: int, reason: str) -> Record:
        target = self._journal.stream.get(seq)
        if target.kind == TOMBSTONE_KIND:
            raise RollbackTargetError(seq)
        if not self._commits.is_committed(seq):
            raise UncommittedRecordError(seq)
        if not self._index.mark(seq):
            raise DuplicateTombstoneError(seq)
        tombstone = self._journal.append(
            TOMBSTONE_KIND,
            {"target_seq": seq, "target_kind": target.kind, "reason": reason},
        )
        self._commits.commit(tombstone.seq)
        return tombstone

