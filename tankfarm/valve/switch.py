"""Valve movement, always mirrored into the record stream."""

from __future__ import annotations

from tankfarm.clock import LogicalClock
from tankfarm.domain import POSITION_CLOSED, POSITION_OPEN
from tankfarm.event import Event, EventBus
from tankfarm.event import topics
from tankfarm.journal.writer import JournalWriter
from tankfarm.valve.model import Valve
from tankfarm.valve.registry import ValveRegistry


class ValveSwitcher:
    """Moves valves and publishes each movement."""

    def __init__(
        self,
        registry: ValveRegistry,
        journal: JournalWriter,
        bus: EventBus,
        clock: LogicalClock,
    ) -> None:
        self._registry = registry
        self._journal = journal
        self._bus = bus
        self._clock = clock

    def open(self, valve_id: str) -> Valve:
        return self._move(valve_id, POSITION_OPEN)

    def close(self, valve_id: str) -> Valve:
        return self._move(valve_id, POSITION_CLOSED)

    def position_of(self, valve_id: str) -> str:
        return self._registry.position(valve_id)

    def _move(self, valve_id: str, position: str) -> Valve:
        valve = self._registry.get(valve_id)
        valve.move_to(position, self._clock.tick())
        self._journal.append(
            topics.VALVE_POSITION,
            {"valve_id": valve.valve_id, "position": valve.position},
        )
        self._bus.publish(
            Event(
                topic=topics.VALVE_POSITION,
                value={"valve_id": valve.valve_id, "position": valve.position},
                ts=self._clock.now(),
            )
        )
        return valve

