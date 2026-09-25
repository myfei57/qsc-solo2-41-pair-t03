"""Aggregated view of the audit trail."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from tankfarm.audit.record import AuditEntry


@dataclass(frozen=True)
class AuditSummary:
    total: int
    by_kind: dict[str, int]
    by_subject: dict[str, int]
    latest: AuditEntry | None = field(default=None)

    def as_payload(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "by_kind": dict(self.by_kind),
            "by_subject": dict(self.by_subject),
            "latest": None if self.latest is None else self.latest.as_payload(),
        }


def summarize(entries: Iterable[AuditEntry]) -> AuditSummary:
    by_kind: dict[str, int] = {}
    by_subject: dict[str, int] = {}
    total = 0
    latest: AuditEntry | None = None
    for entry in entries:
        total += 1
        by_kind[entry.kind] = by_kind.get(entry.kind, 0) + 1
        by_subject[entry.subject] = by_subject.get(entry.subject, 0) + 1
        if latest is None or entry.seq > latest.seq:
            latest = entry
    return AuditSummary(
        total=total, by_kind=by_kind, by_subject=by_subject, latest=latest
    )

