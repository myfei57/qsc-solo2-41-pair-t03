"""Trip test and reset handling."""

from __future__ import annotations

from tankfarm.clock import LogicalClock
from tankfarm.errors import LevelTooHighError, LatchActiveError
from tankfarm.event import Event, EventBus
from tankfarm.event import topics
from tankfarm.esd.valve import EsdValve
from tankfarm.interlock.engine import InterlockEngine
from tankfarm.interlock.rules import OVERFILL_LATCH
from tankfarm.journal.writer import JournalWriter
from tankfarm.level.service import LevelService


class TestController:
    """Runs a trip test and only releases the latch when the process is safe."""

    def __init__(
        self,
        tank_id: str,
        level: LevelService,
        engine: InterlockEngine,
        valve: EsdValve,
        journal: JournalWriter,
        bus: EventBus,
        clock: LogicalClock,
    ) -> None:
        self._tank_id = tank_id
        self._level = level
        self._engine = engine
        self._valve = valve
        self._journal = journal
        self._bus = bus
        self._clock = clock

    def start(self) -> None:
        self._engine.set(OVERFILL_LATCH, "trip test")
        payload = {"tank_id": self._tank_id, "phase": "start"}
        self._journal.append(topics.ESD_TEST, payload)
        self._bus.publish(Event(topics.ESD_TEST, payload, self._clock.now()))

    def reset(self) -> None:
        if self._engine.is_active(OVERFILL_LATCH) and self._valve.is_open():
            raise LatchActiveError("esd-valve-open")
        reading = self._level.read_confirmed(self._tank_id)
        if self._level.at_high(self._tank_id):
            raise LevelTooHighError(self._tank_id, reading, self._level.high_limit())
        self._engine.clear(OVERFILL_LATCH, "operator reset")
        payload = {"tank_id": self._tank_id, "phase": "reset"}
        self._journal.append(topics.ESD_TEST, payload)
        self._bus.publish(Event(topics.ESD_TEST, payload, self._clock.now()))
