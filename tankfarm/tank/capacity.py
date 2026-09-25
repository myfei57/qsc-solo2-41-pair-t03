"""Remaining volume estimation from calibrated readings."""

from __future__ import annotations

from tankfarm.level.service import LevelService
from tankfarm.tank.registry import TankRegistry


class CapacityEstimator:
    """Turns a raw reading into the headroom left in a tank."""

    def __init__(self, tanks: TankRegistry, levels: LevelService) -> None:
        self._tanks = tanks
        self._levels = levels

    def net_volume(self, tank_id: str) -> float:
        tank = self._tanks.get(tank_id)
        state = self._levels.state(tank_id)
        net = state.reading - state.offset
        if net < 0:
            return 0.0
        if net > tank.capacity_mm:
            return tank.capacity_mm
        return net

    def remaining(self, tank_id: str) -> float:
        tank = self._tanks.get(tank_id)
        remaining = tank.capacity_mm - self.net_volume(tank_id)
        if remaining < 0:
            return 0.0
        return remaining

