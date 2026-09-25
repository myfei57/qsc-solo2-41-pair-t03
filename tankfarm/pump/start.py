"""Energising a transfer pump."""

from __future__ import annotations

from tankfarm.clock import LogicalClock
from tankfarm.errors import AlreadyRunningError
from tankfarm.event import Event, EventBus
from tankfarm.event import topics
from tankfarm.journal.writer import JournalWriter
from tankfarm.pump.model import Pump


def start_pump(
    pump: Pump, journal: JournalWriter, bus: EventBus, clock: LogicalClock
) -> Pump:
    """Runs only after the caller cleared the start gate."""

    if pump.running:
        raise AlreadyRunningError(pump.pump_id)
    pump.running = True
    payload = {"pump_id": pump.pump_id, "valve_id": pump.valve_id}
    journal.append(topics.PUMP_STARTED, payload)
    bus.publish(Event(topics.PUMP_STARTED, payload, clock.now()))
    return pump

