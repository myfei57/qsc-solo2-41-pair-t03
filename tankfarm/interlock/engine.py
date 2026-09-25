"""Latch engine driven by the rule set."""

from __future__ import annotations

from typing import Any

from tankfarm.clock import LogicalClock
from tankfarm.event import Event, EventBus
from tankfarm.event import topics
from tankfarm.interlock.latch import LatchState
from tankfarm.interlock.rules import ControlContext, LatchRule, default_rules
from tankfarm.journal.writer import JournalWriter


class InterlockEngine:
    """Applies latch rules and records every change of state."""

    def __init__(
        self, journal: JournalWriter, bus: EventBus, clock: LogicalClock
    ) -> None:
        self._journal = journal
        self._bus = bus
        self._clock = clock
        self._rules: dict[str, LatchRule] = {}
        self._latches: dict[str, LatchState] = {}
        for rule in default_rules():
            self.register(rule)

    def register(self, rule: LatchRule) -> None:
        self._rules[rule.name] = rule
        self._latches.setdefault(rule.name, LatchState(name=rule.name))

    def is_active(self, name: str) -> bool:
        latch = self._latches.get(name)
        return bool(latch is not None and latch.active)

    def active_latches(self) -> tuple[str, ...]:
        return tuple(
            name for name, latch in self._latches.items() if latch.active
        )

    def all(self) -> tuple[LatchState, ...]:
        return tuple(self._latches.values())

    def set(self, name: str, reason: str) -> LatchState:
        return self._apply(name, True, reason)

    def clear(self, name: str, reason: str) -> LatchState:
        return self._apply(name, False, reason)

    def restore(self, name: str, active: bool, reason: str) -> None:
        latch = self._latches.setdefault(name, LatchState(name=name))
        latch.active = bool(active)
        latch.reason = reason

    def evaluate(self, ctx: ControlContext) -> tuple[LatchState, ...]:
        changed: list[LatchState] = []
        for name, rule in self._rules.items():
            latch = self._latches[name]
            if not latch.active and rule.set_when(ctx):
                changed.append(self._apply(name, True, rule.description))
            elif latch.active and rule.clear_when(ctx):
                changed.append(self._apply(name, False, rule.description))
        return tuple(changed)

    def reset(self) -> None:
        for name, latch in self._latches.items():
            latch.active = False
            latch.reason = ""
            latch.changed_at = 0

    def as_payload(self) -> dict[str, Any]:
        return {name: latch.as_payload() for name, latch in self._latches.items()}

    def _apply(self, name: str, active: bool, reason: str) -> LatchState:
        latch = self._latches.setdefault(name, LatchState(name=name))
        latch.active = bool(active)
        latch.reason = reason
        latch.changed_at = self._clock.tick()
        payload = {"latch": name, "active": latch.active, "reason": reason}
        self._journal.append(topics.ESD_LATCH, payload)
        self._bus.publish(Event(topics.ESD_LATCH, payload, latch.changed_at))
        return latch
