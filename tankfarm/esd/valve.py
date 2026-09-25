"""Emergency shutdown valve device."""

from __future__ import annotations

from tankfarm.domain import VALVE_ESD
from tankfarm.valve.model import Valve
from tankfarm.valve.switch import ValveSwitcher


class EsdValve:
    """Closed means isolated; the trip path only ever closes it."""

    def __init__(self, switcher: ValveSwitcher, valve_id: str = VALVE_ESD) -> None:
        self._switcher = switcher
        self._valve_id = valve_id

    @property
    def valve_id(self) -> str:
        return self._valve_id

    def close(self) -> Valve:
        return self._switcher.close(self._valve_id)

    def open(self) -> Valve:
        return self._switcher.open(self._valve_id)

    def is_closed(self) -> bool:
        return self._switcher.position_of(self._valve_id) != "open"

    def is_open(self) -> bool:
        return self._switcher.position_of(self._valve_id) == "open"

