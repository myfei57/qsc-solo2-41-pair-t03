"""Discharge header setpoint device."""

from __future__ import annotations

from tankfarm.clock import LogicalClock
from tankfarm.errors import NegativeSetpointError
from tankfarm.event import Event, EventBus
from tankfarm.event import topics
from tankfarm.journal.writer import JournalWriter

HEADER_HISTORY_LIMIT = 8


class Header:
    """Single setpoint shared by every transfer pump."""

    def __init__(
        self,
        header_id: str,
        journal: JournalWriter,
        bus: EventBus,
        clock: LogicalClock,
    ) -> None:
        self._header_id = header_id
        self._journal = journal
        self._bus = bus
        self._clock = clock
        self._setpoint = 0.0
        self._history: list[tuple[int, float]] = []

    @property
    def header_id(self) -> str:
        return self._header_id

    def setpoint(self) -> float:
        return self._setpoint

    def history(self) -> tuple[tuple[int, float], ...]:
        return tuple(self._history)

    def write(self, value: float) -> float:
        if value < 0:
            raise NegativeSetpointError(value)
        self._setpoint = float(value)
        now = self._clock.tick()
        self._history.append((now, self._setpoint))
        if len(self._history) > HEADER_HISTORY_LIMIT:
            del self._history[0 : len(self._history) - HEADER_HISTORY_LIMIT]
        self._journal.append(topics.HEADER_SETPOINT, {"setpoint": self._setpoint})
        self._bus.publish(
            Event(
                topic=topics.HEADER_SETPOINT,
                value={"setpoint": self._setpoint},
                ts=now,
            )
        )
        return self._setpoint

    def restore(self, value: float) -> None:
        self._setpoint = float(value)

