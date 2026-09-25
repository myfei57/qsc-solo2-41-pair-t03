"""Single-step-at-a-time transfer sequence machine."""

from __future__ import annotations

from tankfarm.clock import LogicalClock
from tankfarm.errors import (
    GateBlockedError,
    OutOfOrderError,
    StageAlreadyReachedError,
)
from tankfarm.event import Event, EventBus
from tankfarm.event import topics
from tankfarm.journal.writer import JournalWriter
from tankfarm.sequence.stages import (
    FACTS,
    STAGE_GATES,
    STAGE_IDLE,
    STAGE_ORDER,
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
        self._facts = {name: False for name in FACTS}
        self._history: list[str] = [STAGE_IDLE]

    def stage(self) -> str:
        return self._stage

    def history(self) -> tuple[str, ...]:
        return tuple(self._history)

    def facts(self) -> dict[str, bool]:
        return dict(self._facts)

    def set_fact(self, name: str, value: bool = True) -> None:
        self._facts[name] = bool(value)

    def check(self, target: str) -> None:
        """Validates a step without taking it."""

        if target not in STAGE_ORDER:
            raise OutOfOrderError(self._stage, target)
        current = STAGE_ORDER.index(self._stage)
        wanted = STAGE_ORDER.index(target)
        if wanted == current:
            raise StageAlreadyReachedError(target)
        if wanted < current:
            raise OutOfOrderError(self._stage, target)
        for gate in STAGE_GATES[target]:
            if not self._facts.get(gate, False):
                raise GateBlockedError(gate)

    def advance(self, target: str) -> str:
        self.check(target)
        self._stage = target
        self._history.append(target)
        payload = {"stage": target, "facts": self.facts()}
        self._journal.append(topics.SEQUENCE_STAGE, payload)
        self._bus.publish(Event(topics.SEQUENCE_STAGE, payload, self._clock.now()))
        return self._stage

    def backfill(self, target: str) -> tuple[str, ...]:
        """Walks forward through every stage up to and including the target."""

        current = STAGE_ORDER.index(self._stage)
        wanted = STAGE_ORDER.index(target)
        passed: list[str] = []
        for stage in STAGE_ORDER[current + 1 : wanted + 1]:
            for gate in STAGE_GATES.get(stage, ()):
                self._facts[gate] = True
            self.advance(stage)
            passed.append(stage)
        return tuple(passed)

    def reset(self) -> None:
        self._stage = STAGE_IDLE
        self._facts = {name: False for name in FACTS}
        self._history = [STAGE_IDLE]
