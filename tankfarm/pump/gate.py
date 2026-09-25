"""Start gate: every pre-condition a transfer pump must satisfy."""

from __future__ import annotations

from tankfarm.clock import LogicalClock
from tankfarm.errors import LatchActiveError, NotPersistedError
from tankfarm.interlock.engine import InterlockEngine
from tankfarm.tank.interlock import InterlockReport, TransferInterlock
from tankfarm.valve.persist import ValvePersister
from tankfarm.versioning.generation import SCOPE_VALVE_PERSIST, GenerationRegistry
from tankfarm.versioning.sheet import ConfirmationSheet, SheetBook


class PumpStartGate:
    """Checks durable valve state, latches and the transfer interlock."""

    def __init__(
        self,
        sheets: SheetBook,
        generations: GenerationRegistry,
        persister: ValvePersister,
        engine: InterlockEngine,
        interlock: TransferInterlock,
        clock: LogicalClock,
    ) -> None:
        self._sheets = sheets
        self._generations = generations
        self._persister = persister
        self._engine = engine
        self._interlock = interlock
        self._clock = clock

    def verify(self, sheet_id: str, tank_id: str) -> tuple[ConfirmationSheet, InterlockReport]:
        sheet = self._sheets.get(sheet_id)
        if sheet.scope != SCOPE_VALVE_PERSIST:
            raise NotPersistedError("valve positions")
        if not self._persister.all_persisted():
            missing = self._persister.unpersisted()
            raise NotPersistedError(missing[0].valve_id)
        active = self._engine.active_latches()
        if active:
            raise LatchActiveError(active[0])
        report = self._interlock.require_ready(tank_id)
        consumed = self._sheets.consume(sheet_id, self._clock.now(), self._generations)
        return consumed, report

