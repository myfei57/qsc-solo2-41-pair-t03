"""Append-only sequence of records."""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from tankfarm.errors import RecordNotFoundError
from tankfarm.ids import IdFactory
from tankfarm.journal.record import Record


class RecordStream:
    """Records are only ever appended; nothing is rewritten in place."""

    def __init__(self, ids: IdFactory) -> None:
        self._ids = ids
        self._records: list[Record] = []

    def append(self, kind: str, payload: Mapping[str, Any], ts: int) -> Record:
        seq = len(self._records) + 1
        record = Record(
            seq=seq,
            record_id=self._ids.new("rec"),
            kind=kind,
            payload=dict(payload),
            ts=int(ts),
        )
        self._records.append(record)
        return record

    def load(self, records: Iterable[Record]) -> None:
        self._records = sorted(records, key=lambda item: item.seq)

    def get(self, seq: int) -> Record:
        if seq < 1 or seq > len(self._records):
            raise RecordNotFoundError(seq)
        return self._records[seq - 1]

    def head(self) -> int:
        return len(self._records)

    def records(self) -> tuple[Record, ...]:
        return tuple(self._records)

