"""Ordered transfer sequence with named pre-gates."""

from __future__ import annotations

from tankfarm.sequence.machine import SequenceMachine
from tankfarm.sequence.stages import (
    FACT_NEW_TANK_OPEN,
    FACT_OLD_TANK_CLOSED,
    FACT_VALVE_PERSISTED,
    STAGE_GATES,
    STAGE_IDLE,
    STAGE_NEW_TANK_OPEN,
    STAGE_OLD_TANK_CLOSED,
    STAGE_ORDER,
    STAGE_PUMP_RUNNING,
    STAGE_VALVES_PERSISTED,
)

__all__ = [
    "FACT_NEW_TANK_OPEN",
    "FACT_OLD_TANK_CLOSED",
    "FACT_VALVE_PERSISTED",
    "STAGE_GATES",
    "STAGE_IDLE",
    "STAGE_NEW_TANK_OPEN",
    "STAGE_OLD_TANK_CLOSED",
    "STAGE_ORDER",
    "STAGE_PUMP_RUNNING",
    "STAGE_VALVES_PERSISTED",
    "SequenceMachine",
]

