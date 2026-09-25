"""Query filters shared by the audit trail and the record stream."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class RecordFilter:
    """Narrows a record set by kind, subject, sequence window and limit."""

    kinds: tuple[str, ...] = ()
    subject: str | None = None
    min_seq: int = 0
    max_seq: int = 0
    limit: int = 0

    def matches(self, record: Any) -> bool:
        if self.kinds and record.kind not in self.kinds:
            return False
        if self.min_seq and record.seq < self.min_seq:
            return False
        if self.max_seq and record.seq > self.max_seq:
            return False
        if self.subject is not None:
            payload: Mapping[str, Any] = record.payload
            if not self._subject_matches(payload):
                return False
        return True

    def _subject_matches(self, payload: Mapping[str, Any]) -> bool:
        subject = self.subject
        if subject is None:
            return True
        for key in ("tank_id", "valve_id", "pump_id", "batch_id"):
            if payload.get(key) == subject:
                return True
        return payload.get("subject") == subject

    def apply(self, records: Sequence[Any]) -> tuple[Any, ...]:
        selected = [record for record in records if self.matches(record)]
        if self.limit > 0:
            selected = selected[-self.limit :]
        return tuple(selected)

    def as_payload(self) -> dict[str, Any]:
        return {
            "kinds": list(self.kinds),
            "subject": self.subject,
            "min_seq": self.min_seq,
            "max_seq": self.max_seq,
            "limit": self.limit,
        }
