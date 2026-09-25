"""Set and clear conditions of every latch."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

OVERFILL_LATCH = "overfill"
BLANKET_LATCH = "blanket"


@dataclass(frozen=True)
class ControlContext:
    """Everything the latch rules are allowed to look at."""

    level_overfilled: bool
    gauge_confirmed: bool
    blanket_alarm: bool
    blanket_confirmed: bool
    pumps_running: bool
    esd_closed: bool


@dataclass(frozen=True)
class LatchRule:
    name: str
    description: str
    set_when: Callable[[ControlContext], bool]
    clear_when: Callable[[ControlContext], bool]


def _overfill_set(ctx: ControlContext) -> bool:
    return ctx.level_overfilled and ctx.gauge_confirmed


def _overfill_clear(ctx: ControlContext) -> bool:
    return (
        not ctx.level_overfilled
        and ctx.gauge_confirmed
        and not ctx.pumps_running
        and ctx.esd_closed
    )


def _blanket_set(ctx: ControlContext) -> bool:
    return ctx.blanket_alarm


def _blanket_clear(ctx: ControlContext) -> bool:
    return not ctx.blanket_alarm and ctx.blanket_confirmed


OVERFILL_RULE = LatchRule(
    name=OVERFILL_LATCH,
    description="level reached the high limit while the gauge was confirmed",
    set_when=_overfill_set,
    clear_when=_overfill_clear,
)

BLANKET_RULE = LatchRule(
    name=BLANKET_LATCH,
    description="blanket gas pressure left its window",
    set_when=_blanket_set,
    clear_when=_blanket_clear,
)


def default_rules() -> tuple[LatchRule, ...]:
    return (OVERFILL_RULE, BLANKET_RULE)

