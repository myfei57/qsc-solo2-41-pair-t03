"""Overfill trip path: close the emergency valve before stopping the pumps."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from tankfarm.clock import LogicalClock
from tankfarm.event import Event, EventBus
from tankfarm.event import topics
from tankfarm.esd.valve import EsdValve
from tankfarm.interlock.engine import InterlockEngine
from tankfarm.interlock.rules import OVERFILL_LATCH
from tankfarm.journal.writer import JournalWriter
from tankfarm.level.service import LevelService

StopHook = Callable[[], tuple[str, ...]]


@dataclass(frozen=True)
class TripResult:
    tank_id: str
    reading: float
    tripped: bool
    latched: bool

    def as_payload(self) -> dict[str, Any]:
        return {
            "tank_id": self.tank_id,
            "reading": self.reading,
            "tripped": self.tripped,
            "latched": self.latched,
        }


class TripController:
    """Decides and performs the overfill trip for one tank."""

    def __init__(
        self,
        tank_id: str,
        level: LevelService,
        engine: InterlockEngine,
        valve: EsdValve,
        journal: JournalWriter,
        bus: EventBus,
        clock: LogicalClock,
        running_hook: Callable[[], tuple[str, ...]],
        stop_hook: StopHook,
    ) -> None:
        self._tank_id = tank_id
        self._level = level
        self._engine = engine
        self._valve = valve
        self._journal = journal
        self._bus = bus
        self._clock = clock
        self._running_hook = running_hook
        self._stop_hook = stop_hook

    def trip(self) -> TripResult:
        reading = self._level.read_confirmed(self._tank_id)
        if not self._level.at_high(self._tank_id):
            return TripResult(
                self._tank_id, reading, False, self._engine.is_active(OVERFILL_LATCH)
            )
        self._act("high level")
        return TripResult(
            self._tank_id, reading, True, self._engine.is_active(OVERFILL_LATCH)
        )

    def retrip(self) -> TripResult:
        reading = self._level.read_confirmed(self._tank_id)
        if not self._level.at_high(self._tank_id):
            return TripResult(
                self._tank_id, reading, False, self._engine.is_active(OVERFILL_LATCH)
            )
        if (
            self._engine.is_active(OVERFILL_LATCH)
            and self._valve.is_closed()
            and not self._running_hook()
        ):
            return TripResult(self._tank_id, reading, False, True)
        self._act("high level retrip")
        return TripResult(
            self._tank_id, reading, True, self._engine.is_active(OVERFILL_LATCH)
        )

    def _act(self, reason: str) -> None:
        self._engine.set(OVERFILL_LATCH, reason)
        self._valve.close()
        stopped = self._stop_hook()
        payload = {
            "tank_id": self._tank_id,
            "reason": reason,
            "stopped": list(stopped),
        }
        self._journal.append(topics.ESD_TRIP, payload)
        self._bus.publish(Event(topics.ESD_TRIP, payload, self._clock.now()))
