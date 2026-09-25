"""Filtered reads over the audit trail."""

from __future__ import annotations

from tankfarm.audit.record import AuditEntry, AuditLog
from tankfarm.judgement.filters import RecordFilter


class AuditQuery:
    """Applies the shared record filter to audit entries."""

    def __init__(self, log: AuditLog) -> None:
        self._log = log

    def select(self, record_filter: RecordFilter) -> tuple[AuditEntry, ...]:
        return record_filter.apply(self._log.entries())

    def kinds(self) -> tuple[str, ...]:
        return tuple(sorted({entry.kind for entry in self._log.entries()}))

    def subjects(self) -> tuple[str, ...]:
        return tuple(sorted({entry.subject for entry in self._log.entries()}))

