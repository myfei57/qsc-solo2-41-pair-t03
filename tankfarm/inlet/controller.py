"""Inlet valve gated on blanketed tank condition."""

from __future__ import annotations

from tankfarm.clock import LogicalClock
from tankfarm.errors import InertNotConfirmedError
from tankfarm.event import Event, EventBus
from tankfarm.event import topics
from tankfarm.inert.service import InertService
from tankfarm.inlet.model import InletState
from tankfarm.interlock.engine import InterlockEngine
from tankfarm.journal.writer import JournalWriter
from tankfarm.valve.switch import ValveSwitcher

BLANKET_LATCH = "blanket"


class InletController:
    """Opening the inlet requires a confirmed blanket pressure."""

    def __init__(
        self,
        tank_id: str,
        valve_id: str,
        inert: InertService,
        engine: InterlockEngine,
        switcher: ValveSwitcher,
        journal: JournalWriter,
        bus: EventBus,
        clock: LogicalClock,
    ) -> None:
        self._state = InletState(tank_id=tank_id, valve_id=valve_id)
        self._inert = inert
        self._engine = engine
        self._switcher = switcher
        self._journal = journal
        self._bus = bus
        self._clock = clock

    def state(self) -> InletState:
        return self._state

    def open(self) -> InletState:
        if self._engine.is_active(BLANKET_LATCH):
            raise InertNotConfirmedError(self._state.tank_id)
        if not self._inert.check(self._state.tank_id):
            raise InertNotConfirmedError(self._state.tank_id)
        self._switcher.open(self._state.valve_id)
        self._state.open = True
        self._emit(topics.INLET_OPENED)
        return self._state

    def release(self) -> InletState:
        if self._engine.is_active(BLANKET_LATCH):
            self._engine.clear(BLANKET_LATCH, "operator release")
        self._state.open = True
        self._emit(topics.INLET_RELEASED)
        return self._state

    def apply_open(self, open_state: bool) -> None:
        self._state.open = bool(open_state)

    def _emit(self, topic: str) -> None:
        payload = {
            "tank_id": self._state.tank_id,
            "valve_id": self._state.valve_id,
            "open": self._state.open,
        }
        self._journal.append(topic, payload)
        self._bus.publish(Event(topic, payload, self._clock.now()))

