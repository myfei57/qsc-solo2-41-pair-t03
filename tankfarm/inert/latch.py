"""Vent valve latch held while a blanket alarm is active."""

from __future__ import annotations

from tankfarm.domain import VALVE_VENT
from tankfarm.valve.model import Valve
from tankfarm.valve.switch import ValveSwitcher


class VentLatch:
    """The vent stays open until the alarm clears and the latch is released."""

    def __init__(self, switcher: ValveSwitcher, valve_id: str = VALVE_VENT) -> None:
        self._switcher = switcher
        self._valve_id = valve_id

    @property
    def valve_id(self) -> str:
        return self._valve_id

    def open(self) -> Valve:
        return self._switcher.open(self._valve_id)

    def close(self) -> Valve:
        return self._switcher.close(self._valve_id)

    def is_open(self) -> bool:
        return self._switcher.position_of(self._valve_id) == "open"

    def release(self, alarm_active: bool) -> bool:
        if alarm_active or not self.is_open():
            return False
        self.close()
        return True

