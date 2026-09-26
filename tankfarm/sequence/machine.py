"""Single-step-at-a-time transfer sequence machine.

A stage is never marked reached on its own: advancing to a stage is only
allowed when every gate fact is backed by a durable record that was appended
*before* the stage record. The machine therefore has no ``set_fact`` hook and
no "catch up" helper -- facts arrive as evidence records, one step at a time,
and jumps or post-hoc backfill are refused.
"""

from __future__ import annotations

from typing import Iterable

from tankfarm.clock import LogicalClock
from tankfarm.domain import (
    POSITION_CLOSED,
    POSITION_OPEN,
    VALVE_TANK_NEW,
    VALVE_TANK_OLD,
)
from tankfarm.errors import (
    GateBlockedError,
    OutOfOrderError,
    StageAlreadyReachedError,
)
from tankfarm.event import Event, EventBus
from tankfarm.event import topics
from tankfarm.journal.record import Record
from tankfarm.journal.writer import JournalWriter
from tankfarm.sequence.stages import (
    FACT_NEW_TANK_OPEN,
    FACT_OLD_TANK_CLOSED,
    FACT_VALVE_PERSISTED,
    STAGE_GATES,
    STAGE_IDLE,
    STAGE_ORDER,
)

# Valve whose durable position record proves each handover fact.
_POSITION_FACTS = (
    (FACT_NEW_TANK_OPEN, VALVE_TANK_NEW, POSITION_OPEN),
    (FACT_OLD_TANK_CLOSED, VALVE_TANK_OLD, POSITION_CLOSED),
)


class SequenceMachine:
    """Refuses jumps, repeats and stages whose gate evidence is missing."""

    def __init__(
        self, journal: JournalWriter, bus: EventBus, clock: LogicalClock
    ) -> None:
        self._journal = journal
        self._bus = bus
        self._clock = clock
        self._stage = STAGE_IDLE
        self._history: list[str] = [STAGE_IDLE]
        self._positions: dict[str, str] = {}
        self._position_evidence: dict[str, Record] = {}
        self._persisted_evidence: Record | None = None

    def stage(self) -> str:
        return self._stage

    def history(self) -> tuple[str, ...]:
        return tuple(self._history)

    def facts(self) -> dict[str, bool]:
        return {name: self.evidence_for(name) is not None for name in self._fact_names()}

    def evidence(self) -> dict[str, dict[str, object]]:
        """Record proving each established fact -- the per-step credentials."""

        return {
            name: record.as_payload()
            for name in self._fact_names()
            if (record := self.evidence_for(name)) is not None
        }

    def evidence_for(self, fact: str) -> Record | None:
        if fact == FACT_VALVE_PERSISTED:
            return self._persisted_evidence
        for name, valve_id, position in _POSITION_FACTS:
            if fact == name and self._positions.get(valve_id) == position:
                return self._position_evidence.get(valve_id)
        return None

    def observe(self, record: Record) -> None:
        """Feeds one durable record; facts are derived, never assigned."""

        if record.kind == topics.VALVE_PERSISTED:
            self._persisted_evidence = record
        elif record.kind == topics.VALVE_POSITION:
            valve_id = str(record.payload["valve_id"])
            if valve_id in (VALVE_TANK_NEW, VALVE_TANK_OLD):
                self._positions[valve_id] = str(record.payload["position"])
                self._position_evidence[valve_id] = record

    def replay(self, records: Iterable[Record]) -> tuple[str, ...]:
        """Rebuilds the machine from committed records, stopping at the first
        stage that cannot show the evidence its gates demand."""

        self.reset()
        accepted: list[str] = []
        for record in records:
            if record.kind == topics.SEQUENCE_STAGE:
                target = str(record.payload.get("stage", ""))
                if target == self._stage:
                    # Idempotent re-assertion of the stage already reached.
                    pass
                elif not self._can_take(target):
                    # A logged step without the prior step's credentials is
                    # not a step: the run resumes just before it.
                    break
                else:
                    self._stage = target
                    self._history.append(target)
                    accepted.append(target)
            self.observe(record)
        return tuple(accepted)

    def check(self, target: str) -> None:
        """Validates the next step without taking it."""

        if not self._can_take(target):
            if target not in STAGE_ORDER:
                raise OutOfOrderError(self._stage, target)
            current = STAGE_ORDER.index(self._stage)
            wanted = STAGE_ORDER.index(target)
            if wanted == current:
                raise StageAlreadyReachedError(target)
            if wanted < current or wanted != current + 1:
                raise OutOfOrderError(self._stage, target)
        for gate in STAGE_GATES[target]:
            if self.evidence_for(gate) is None:
                raise GateBlockedError(gate)

    def advance(self, target: str) -> str:
        self.check(target)
        evidence = {
            gate: self.evidence_for(gate).record_id  # type: ignore[union-attr]
            for gate in STAGE_GATES[target]
        }
        self._stage = target
        self._history.append(target)
        payload = {"stage": target, "facts": self.facts(), "evidence": evidence}
        self._journal.append(topics.SEQUENCE_STAGE, payload)
        self._bus.publish(Event(topics.SEQUENCE_STAGE, payload, self._clock.now()))
        return self._stage

    def reset(self) -> None:
        self._stage = STAGE_IDLE
        self._history = [STAGE_IDLE]
        self._positions = {}
        self._position_evidence = {}
        self._persisted_evidence = None

    def _can_take(self, target: str) -> bool:
        if target not in STAGE_ORDER:
            return False
        current = STAGE_ORDER.index(self._stage)
        wanted = STAGE_ORDER.index(target)
        return wanted == current + 1

    @staticmethod
    def _fact_names() -> tuple[str, ...]:
        return (FACT_VALVE_PERSISTED, FACT_NEW_TANK_OPEN, FACT_OLD_TANK_CLOSED)
