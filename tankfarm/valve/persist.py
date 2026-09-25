"""Durable valve position writes that gate dependent actions."""

from __future__ import annotations

from tankfarm.clock import LogicalClock
from tankfarm.event import Event, EventBus
from tankfarm.event import topics
from tankfarm.journal.writer import JournalWriter
from tankfarm.valve.model import Valve
from tankfarm.valve.registry import ValveRegistry
from tankfarm.versioning.expiry import ExpiryPolicy
from tankfarm.versioning.generation import (
    CONFIG_KEY,
    SCOPE_CONFIG,
    SCOPE_VALVE_PERSIST,
    GenerationRegistry,
)
from tankfarm.versioning.sheet import ConfirmationSheet, SheetBook

PERSIST_KEY = "all-valves"


class ValvePersister:
    """Writes every valve position before an action depends on it."""

    def __init__(
        self,
        registry: ValveRegistry,
        journal: JournalWriter,
        bus: EventBus,
        clock: LogicalClock,
        generations: GenerationRegistry,
        sheets: SheetBook,
        policy: ExpiryPolicy,
    ) -> None:
        self._registry = registry
        self._journal = journal
        self._bus = bus
        self._clock = clock
        self._generations = generations
        self._sheets = sheets
        self._policy = policy

    def persist(self) -> ConfirmationSheet:
        now = self._clock.now()
        for valve in self._registry.all():
            valve.mark_persisted(self._clock.tick())
            self._journal.append(
                topics.VALVE_POSITION,
                {"valve_id": valve.valve_id, "position": valve.position},
            )
        generation = self._generations.bump(SCOPE_VALVE_PERSIST, PERSIST_KEY, now)
        config_generation = self._generations.current(SCOPE_CONFIG, CONFIG_KEY)
        sheet = self._sheets.issue(
            SCOPE_VALVE_PERSIST,
            PERSIST_KEY,
            generation.number,
            config_generation,
            now,
            self._policy,
        )
        self._journal.append(
            topics.VALVE_PERSISTED,
            {"generation": generation.number, "sheet_id": sheet.sheet_id},
        )
        self._bus.publish(
            Event(
                topic=topics.VALVE_PERSISTED,
                value={"generation": generation.number, "sheet_id": sheet.sheet_id},
                ts=now,
            )
        )
        return sheet

    def all_persisted(self) -> bool:
        valves = self._registry.all()
        return bool(valves) and all(valve.persisted for valve in valves)

    def unpersisted(self) -> tuple[Valve, ...]:
        return tuple(valve for valve in self._registry.all() if not valve.persisted)

