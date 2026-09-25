"""Audit entries and the log that subscribes to the event bus."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from tankfarm.clock import LogicalClock
from tankfarm.event import Event, EventBus
from tankfarm.event.topics import AUDITED_TOPICS
from tankfarm.ids import IdFactory
from tankfarm.store.repository import Repository

_SUBJECT_KEYS = ("tank_id", "valve_id", "pump_id", "batch_id", "latch", "subject")


@dataclass(frozen=True)
class AuditEntry:
    entry_id: str
    seq: int
    kind: str
    subject: str
    message: str
    ts: int

    @property
    def payload(self) -> dict[str, Any]:
        return self.as_payload()

    def as_payload(self) -> dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "seq": self.seq,
            "kind": self.kind,
            "subject": self.subject,
            "tank_id": self.subject,
            "message": self.message,
            "ts": self.ts,
        }

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "AuditEntry":
        return cls(
            entry_id=str(payload["entry_id"]),
            seq=int(payload["seq"]),
            kind=str(payload["kind"]),
            subject=str(payload.get("subject", "")),
            message=str(payload.get("message", "")),
            ts=int(payload.get("ts", 0)),
        )


class AuditLog:
    """Turns every published event into one durable audit entry."""

    def __init__(
        self,
        repository: Repository,
        bus: EventBus,
        ids: IdFactory,
        clock: LogicalClock,
    ) -> None:
        self._repository = repository
        self._bus = bus
        self._ids = ids
        self._clock = clock
        self._entries: list[AuditEntry] = []

    def subscribe(self) -> None:
        for topic in AUDITED_TOPICS:
            self._bus.subscribe(topic, self._on_event)

    def entries(self) -> tuple[AuditEntry, ...]:
        return tuple(self._entries)

    def record(self, kind: str, subject: str, message: str) -> AuditEntry:
        entry = AuditEntry(
            entry_id=self._ids.new("audit"),
            seq=len(self._entries) + 1,
            kind=kind,
            subject=subject,
            message=message,
            ts=self._clock.now(),
        )
        self._entries.append(entry)
        self._repository.append_audit(entry.as_payload())
        return entry

    def restore(self) -> None:
        self._entries = [
            AuditEntry.from_payload(item) for item in self._repository.load_audit()
        ]

    def _on_event(self, event: Event) -> None:
        payload = event.value if isinstance(event.value, Mapping) else {}
        subject = ""
        for key in _SUBJECT_KEYS:
            value = payload.get(key)
            if isinstance(value, str) and value:
                subject = value
                break
        self.record(event.topic, subject, _describe(event.topic, payload))


def _describe(topic: str, payload: Mapping[str, Any]) -> str:
    parts = [f"{key}={payload[key]}" for key in sorted(payload) if _is_scalar(payload[key])]
    return f"{topic} " + " ".join(parts) if parts else topic


def _is_scalar(value: Any) -> bool:
    return isinstance(value, (str, int, float, bool))

