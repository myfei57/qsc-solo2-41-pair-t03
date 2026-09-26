"""Single-step-at-a-time transfer sequence machine."""

from __future__ import annotations

from collections.abc import Callable

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
    STAGE_GATES,
    STAGE_IDLE,
    STAGE_ORDER,
)

Evidence = Callable[[], dict[str, bool]]


class SequenceMachine:
    """Refuses jumps, repeats and stages whose gate evidence is missing.

    A stage may only be reached from the immediately preceding stage, and
    only while every gate fact of the target is backed by a record of the
    physical action that produced it. Facts are read through the evidence
    probe on every check; callers can never mark a gate satisfied by hand,
    and there is no API that walks several stages at once.
    """

    def __init__(
        self,
        journal: JournalWriter,
        bus: EventBus,
        clock: LogicalClock,
        evidence: Evidence,
    ) -> None:
        self._journal = journal
        self._bus = bus
        self._clock = clock
        self._evidence = evidence
        self._stage = STAGE_IDLE
        self._history: list[str] = [STAGE_IDLE]

    def stage(self) -> str:
        return self._stage

    def history(self) -> tuple[str, ...]:
        return tuple(self._history)

    def facts(self) -> dict[str, bool]:
        return dict(self._evidence())

    def require_fact(self, name: str) -> None:
        """Guards an action that is only legal with evidence in hand."""

        if not self._evidence().get(name, False):
            raise GateBlockedError(name)

    def check(self, target: str) -> None:
        """Validates the next single step without taking it."""

        if target not in STAGE_ORDER:
            raise OutOfOrderError(self._stage, target)
        current = STAGE_ORDER.index(self._stage)
        wanted = STAGE_ORDER.index(target)
        if wanted == current:
            raise StageAlreadyReachedError(target)
        if wanted != current + 1:
            raise OutOfOrderError(self._stage, target)
        for gate in STAGE_GATES[target]:
            if not self._evidence().get(gate, False):
                raise GateBlockedError(gate)

    def advance(self, target: str) -> str:
        self.check(target)
        self._stage = target
        self._history.append(target)
        # The carried facts are a snapshot of the evidence that unlocked
        # the gate; the evidence itself stays in the record stream.
        payload = {"stage": target, "facts": self.facts()}
        self._journal.append(topics.SEQUENCE_STAGE, payload)
        self._bus.publish(Event(topics.SEQUENCE_STAGE, payload, self._clock.now()))
        return self._stage

    def restore(self, stage: str, history: tuple[str, ...] | list[str]) -> None:
        """Re-enters a stage replayed from the durable record stream.

        Only a stage whose position in the order matches the replayed stage
        history is accepted, and every gate along that history must still
        be backed by replayed physical evidence; there is no shortcut.
        """

        if stage not in STAGE_ORDER:
            raise OutOfOrderError(self._stage, stage)
        trail = tuple(history)
        if not trail or trail[0] != STAGE_IDLE:
            raise OutOfOrderError(self._stage, stage)
        expected = STAGE_ORDER[: STAGE_ORDER.index(stage) + 1]
        if trail != expected:
            raise OutOfOrderError(self._stage, stage)
        for reached in trail[1:]:
            for gate in STAGE_GATES[reached]:
                if not self._evidence().get(gate, False):
                    raise GateBlockedError(gate)
        self._stage = stage
        self._history = list(trail)

    def reset(self) -> None:
        self._stage = STAGE_IDLE
        self._history = [STAGE_IDLE]
