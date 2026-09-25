"""Journal writer that mirrors every append into durable storage."""

from __future__ import annotations

from typing import Any, Callable, Mapping

from tankfarm.clock import LogicalClock
from tankfarm.journal.record import Record
from tankfarm.journal.stream import RecordStream


class JournalWriter:
    """Appends to the in-memory stream and to the append-only store file."""

    def __init__(self, stream: RecordStream, repository: Any, clock: LogicalClock) -> None:
        self._stream = stream
        self._repository = repository
        self._clock = clock
        self._observers: list[Callable[[Record], None]] = []

    @property
    def stream(self) -> RecordStream:
        return self._stream

    def add_observer(self, observer: Callable[[Record], None]) -> None:
        self._observers.append(observer)

    def append(self, kind: str, payload: Mapping[str, Any]) -> Record:
        record = self._stream.append(kind, payload, self._clock.tick())
        self._repository.append_record(record)
        for observer in tuple(self._observers):
            observer(record)
        return record
