"""Pump setpoint and ramp handling."""

from __future__ import annotations

from tankfarm.errors import NegativeSetpointError
from tankfarm.pump.arbiter import HeaderArbiter
from tankfarm.pump.model import Pump

RAMP_STEP = 5.0
RAMP_MAX_STEPS = 24


class SetpointController:
    """Applies setpoints directly or walks them up in fixed steps."""

    def __init__(self, arbiter: HeaderArbiter) -> None:
        self._arbiter = arbiter

    def apply(self, pump: Pump, value: float) -> float:
        if value < 0:
            raise NegativeSetpointError(value)
        pump.setpoint = float(value)
        return self._arbiter.write(pump.pump_id, value)

    def ramp(self, pump: Pump, target: float) -> tuple[float, ...]:
        if target < 0:
            raise NegativeSetpointError(target)
        if target == pump.setpoint:
            return ()
        direction = 1.0 if target > pump.setpoint else -1.0
        applied: list[float] = []
        for _ in range(RAMP_MAX_STEPS):
            if pump.setpoint == target:
                break
            step = pump.setpoint + direction * RAMP_STEP
            if direction > 0 and step > target:
                step = target
            elif direction < 0 and step < target:
                step = target
            applied.append(self.apply(pump, step))
        return tuple(applied)
