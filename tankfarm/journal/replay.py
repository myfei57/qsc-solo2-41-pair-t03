"""Restart replay driven by the commit watermark."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from tankfarm.journal.commit import CommitController
from tankfarm.journal.record import Record
from tankfarm.journal.stream import RecordStream
from tankfarm.journal.tombstone import TombstoneIndex

Applier = Callable[[Record], None]


@dataclass(frozen=True)
class ReplayResult:
    """Outcome of one replay pass, split by why a record was skipped."""

    from_watermark: int
    to_watermark: int
    applied: tuple[Record, ...]
    skipped_uncommitted: tuple[Record, ...]
    skipped_tombstoned: tuple[Record, ...]

    def applied_count(self) -> int:
        return len(self.applied)

    def skipped_count(self) -> int:
        return len(self.skipped_uncommitted) + len(self.skipped_tombstoned)


def replay(
    stream: RecordStream,
    commits: CommitController,
    index: TombstoneIndex,
    since: int,
    apply: Applier,
) -> ReplayResult:
    """Re-apply committed, not-rolled-back records appended after ``since``."""

    applied: list[Record] = []
    uncommitted: list[Record] = []
    tombstoned: list[Record] = []
    watermark = commits.watermark()
    for record in stream.records():
        if record.seq <= since:
            continue
        if record.seq > watermark:
            uncommitted.append(record)
            continue
        if index.is_tombstoned(record.seq):
            tombstoned.append(record)
            continue
        apply(record)
        applied.append(record)
    return ReplayResult(
        from_watermark=int(since),
        to_watermark=watermark,
        applied=tuple(applied),
        skipped_uncommitted=tuple(uncommitted),
        skipped_tombstoned=tuple(tombstoned),
    )

