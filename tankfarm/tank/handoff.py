"""Two stage tank handover: open the new tank before closing the old one."""

from __future__ import annotations

from tankfarm.clock import LogicalClock
from tankfarm.domain import POSITION_CLOSED, POSITION_OPEN
from tankfarm.event import Event, EventBus
from tankfarm.event import topics
from tankfarm.journal.writer import JournalWriter
from tankfarm.valve.switch import ValveSwitcher


class Handoff:
    """Runs handover steps separately so each one can be gated."""

    def __init__(
        self,
        switcher: ValveSwitcher,
        journal: JournalWriter,
        bus: EventBus,
        clock: LogicalClock,
    ) -> None:
        self._switcher = switcher
        self._journal = journal
        self._bus = bus
        self._clock = clock

    def open_new(self, new_tank_id: str) -> None:
        valve_id = f"valve-{new_tank_id}"
        self._switcher.open(valve_id)
        self._emit("new-open", new_tank_id, "")

    def close_old(self, new_tank_id: str, old_tank_id: str) -> None:
        valve_id = f"valve-{old_tank_id}"
        self._switcher.close(valve_id)
        self._emit("old-close", new_tank_id, old_tank_id)

    def retry(self, new_tank_id: str, old_tank_id: str) -> tuple[str, ...]:
        steps: list[str] = []
        new_valve = f"valve-{new_tank_id}"
        old_valve = f"valve-{old_tank_id}"
        if self._switcher.position_of(new_valve) != POSITION_OPEN:
            self.open_new(new_tank_id)
            steps.append("new-open")
        if self._switcher.position_of(old_valve) != POSITION_CLOSED:
            self.close_old(new_tank_id, old_tank_id)
            steps.append("old-close")
        return tuple(steps)

    def _emit(self, phase: str, new_tank_id: str, old_tank_id: str) -> None:
        payload = {
            "phase": phase,
            "new_tank_id": new_tank_id,
            "old_tank_id": old_tank_id,
        }
        self._journal.append(topics.TANK_SWITCHED, payload)
        self._bus.publish(Event(topics.TANK_SWITCHED, payload, self._clock.now()))

