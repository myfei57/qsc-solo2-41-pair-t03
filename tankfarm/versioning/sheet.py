"""Single-use confirmation sheets bound to a generation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from tankfarm.errors import DuplicateSheetError, ExpiredSheetError, SheetNotFoundError
from tankfarm.ids import IdFactory
from tankfarm.versioning.expiry import ExpiryPolicy
from tankfarm.versioning.generation import CONFIG_KEY, SCOPE_CONFIG, GenerationRegistry

STATE_OPEN = "open"
STATE_CONSUMED = "consumed"
STATE_EXPIRED = "expired"


@dataclass
class ConfirmationSheet:
    """Evidence that one pre-condition was confirmed at a known generation."""

    sheet_id: str
    scope: str
    key: str
    generation: int
    config_generation: int
    issued_at: int
    policy: ExpiryPolicy
    state: str = STATE_OPEN
    consumed_at: int | None = field(default=None)

    def as_payload(self) -> dict[str, Any]:
        return {
            "sheet_id": self.sheet_id,
            "scope": self.scope,
            "key": self.key,
            "generation": self.generation,
            "config_generation": self.config_generation,
            "issued_at": self.issued_at,
            "state": self.state,
            "consumed_at": self.consumed_at,
        }


class SheetBook:
    """Issues and consumes sheets; every sheet may be used at most once."""

    def __init__(self, ids: IdFactory) -> None:
        self._ids = ids
        self._sheets: dict[str, ConfirmationSheet] = {}

    def issue(
        self,
        scope: str,
        key: str,
        generation: int,
        config_generation: int,
        now: int,
        policy: ExpiryPolicy,
    ) -> ConfirmationSheet:
        sheet = ConfirmationSheet(
            sheet_id=self._ids.new("sheet"),
            scope=scope,
            key=key,
            generation=int(generation),
            config_generation=int(config_generation),
            issued_at=int(now),
            policy=policy,
        )
        self._sheets[sheet.sheet_id] = sheet
        return sheet

    def get(self, sheet_id: str) -> ConfirmationSheet:
        sheet = self._sheets.get(sheet_id)
        if sheet is None:
            raise SheetNotFoundError(sheet_id)
        return sheet

    def consume(
        self, sheet_id: str, now: int, registry: GenerationRegistry
    ) -> ConfirmationSheet:
        sheet = self.get(sheet_id)
        if sheet.state != STATE_OPEN:
            raise DuplicateSheetError(sheet_id)
        registry.require(SCOPE_CONFIG, CONFIG_KEY, sheet.config_generation)
        registry.require(sheet.scope, sheet.key, sheet.generation)
        if sheet.policy.expired(sheet.issued_at, now):
            sheet.state = STATE_EXPIRED
            raise ExpiredSheetError(
                sheet_id,
                sheet.policy.age(sheet.issued_at, now),
                sheet.policy.max_age,
            )
        sheet.state = STATE_CONSUMED
        sheet.consumed_at = int(now)
        return sheet

    def open_sheets(self) -> tuple[ConfirmationSheet, ...]:
        return tuple(
            sheet for sheet in self._sheets.values() if sheet.state == STATE_OPEN
        )
