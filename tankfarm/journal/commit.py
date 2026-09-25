"""Commit watermark controller over a record stream."""

from __future__ import annotations

from tankfarm.errors import RecordNotFoundError
from tankfarm.journal.record import Record
from tankfarm.journal.stream import RecordStream
from tankfarm.journal.watermark import Watermark


class CommitController:
    """Separates appended records from records that readers may observe."""

    def __init__(self, stream: RecordStream, watermark: Watermark) -> None:
        self._stream = stream
        self._watermark = watermark

    def commit(self, seq: int | None = None) -> int:
        target = self._stream.head() if seq is None else int(seq)
        if target > self._stream.head():
            raise RecordNotFoundError(target)
        return self._watermark.advance_to(target)

    def watermark(self) -> int:
        return self._watermark.value()

    def is_committed(self, seq: int) -> bool:
        return 1 <= seq <= self._watermark.value()

    def committed(self) -> tuple[Record, ...]:
        return tuple(
            record for record in self._stream.records() if record.seq <= self._watermark.value()
        )

    def pending(self) -> tuple[Record, ...]:
        return tuple(
            record for record in self._stream.records() if record.seq > self._watermark.value()
        )

