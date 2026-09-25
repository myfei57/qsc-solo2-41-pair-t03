"""Filling and drawing through the inlet and outlet valves."""

from __future__ import annotations

from tankfarm.inlet.controller import InletController
from tankfarm.level.model import LevelState
from tankfarm.level.service import LevelService


class FillingController:
    """Combines the inlet gate with the level movement."""

    def __init__(self, inlet: InletController, level: LevelService) -> None:
        self._inlet = inlet
        self._level = level

    def fill(self, amount: float) -> LevelState:
        state = self._inlet.open()
        return self._level.fill(state.tank_id, amount)
