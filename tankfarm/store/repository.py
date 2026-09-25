"""Durable storage of the record stream, checkpoints and audit trail."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from tankfarm.journal.checkpoint import JournalCheckpoint
from tankfarm.journal.record import Record
from tankfarm.store.layout import StoreLayout
from tankfarm.store.reader import JsonReader
from tankfarm.store.writer import AtomicWriter


class Repository:
    """The only component that touches the data directory."""

    def __init__(self, root: str | Path) -> None:
        self._layout = StoreLayout(root)
        self._layout.ensure()
        self._writer = AtomicWriter()
        self._reader = JsonReader()

    @property
    def layout(self) -> StoreLayout:
        return self._layout

    def append_record(self, record: Record) -> None:
        self._writer.append_line(self._layout.journal_file(), record.as_payload())

    def load_records(self) -> tuple[Record, ...]:
        return tuple(
            Record.from_payload(item)
            for item in self._reader.read_lines(self._layout.journal_file())
        )

    def save_checkpoint(self, checkpoint: JournalCheckpoint) -> None:
        self._writer.write_json(self._layout.checkpoint_file(), checkpoint.as_payload())

    def load_checkpoint(self) -> JournalCheckpoint | None:
        payload = self._reader.read_json(self._layout.checkpoint_file())
        if payload is None:
            return None
        return JournalCheckpoint.from_payload(payload)

    def append_audit(self, payload: Mapping[str, Any]) -> None:
        self._writer.append_line(self._layout.audit_file(), payload)

    def load_audit(self) -> tuple[dict[str, Any], ...]:
        return self._reader.read_lines(self._layout.audit_file())

