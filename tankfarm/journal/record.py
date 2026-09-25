"""Record value object carried by the append-only stream."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class Record:
    """One immutable entry of the operation stream."""

    seq: int
    record_id: str
    kind: str
    payload: Mapping[str, Any]
    ts: int

    def as_payload(self) -> dict[str, Any]:
        return {
            "seq": self.seq,
            "record_id": self.record_id,
            "kind": self.kind,
            "payload": dict(self.payload),
            "ts": self.ts,
        }

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "Record":
        return cls(
            seq=int(payload["seq"]),
            record_id=str(payload["record_id"]),
            kind=str(payload["kind"]),
            payload=dict(payload["payload"]),
            ts=int(payload["ts"]),
        )

