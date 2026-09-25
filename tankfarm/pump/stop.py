"""Stopping pumps, closing the emergency valve first."""

from __future__ import annotations

from tankfarm.clock import LogicalClock
from tankfarm.errors import NotRunningError
from tankfarm.esd.valve import EsdValve
from tankfarm.event import Event, EventBus
from tankfarm.event import topics
from tankfarm.journal.writer import JournalWriter
from tankfarm.pump.model import Pump
from tankfarm.pump.registry import PumpRegistry


def stop_pump(
    pump: Pump,
    esd_valve: EsdValve,
    journal: JournalWriter,
    bus: EventBus,
    clock: LogicalClock,
) -> Pump:
    """The emergency valve is closed before the pump is de-energised."""

    if not pump.running:
        raise NotRunningError(pump.pump_id)
    if not esd_valve.is_closed():
        esd_valve.close()
    pump.running = False
    payload = {"pump_id": pump.pump_id, "esd_closed": esd_valve.is_closed()}
    journal.append(topics.PUMP_STOPPED, payload)
    bus.publish(Event(topics.PUMP_STOPPED, payload, clock.now()))
    return pump


def stop_all_pumps(
    registry: PumpRegistry,
    esd_valve: EsdValve,
    journal: JournalWriter,
    bus: EventBus,
    clock: LogicalClock,
) -> tuple[str, ...]:
    stopped: list[str] = []
    for pump in registry.all():
        if pump.running:
            stop_pump(pump, esd_valve, journal, bus, clock)
            stopped.append(pump.pump_id)
    return tuple(stopped)

