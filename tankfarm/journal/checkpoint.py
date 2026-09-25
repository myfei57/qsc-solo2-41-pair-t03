"""Durable restart marker."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class JournalCheckpoint:
    """Watermark plus the projected state a restart resumes from."""

    watermark: int
    head: int
    ts: int
    state: Mapping[str, Any] = field(default_factory=dict)

    def as_payload(self) -> dict[str, Any]:
        return {
            "watermark": self.watermark,
            "head": self.head,
            "ts": self.ts,
            "state": dict(self.state),
        }

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "JournalCheckpoint":
        return cls(
            watermark=int(payload["watermark"]),
            head=int(payload["head"]),
            ts=int(payload["ts"]),
            state=dict(payload.get("state", {})),
        )
