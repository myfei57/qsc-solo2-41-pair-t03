"""Valve lookup table."""

from __future__ import annotations

from tankfarm.domain import POSITION_CLOSED, VALVES
from tankfarm.errors import UnknownValveError
from tankfarm.valve.model import Valve

VALVE_NAMES = {
    "valve-inlet": "inlet",
    "valve-outlet": "outlet",
    "valve-esd": "emergency shutoff",
    "valve-vent": "vent",
    "valve-tank-new": "new tank",
    "valve-tank-old": "old tank",
}


class ValveRegistry:
    """Holds every valve of the manifold."""

    def __init__(self) -> None:
        self._valves: dict[str, Valve] = {}

    @classmethod
    def seeded(cls) -> "ValveRegistry":
        registry = cls()
        for valve_id in VALVES:
            registry.register(Valve(valve_id=valve_id, name=VALVE_NAMES[valve_id]))
        return registry

    def register(self, valve: Valve) -> None:
        self._valves[valve.valve_id] = valve

    def get(self, valve_id: str) -> Valve:
        valve = self._valves.get(valve_id)
        if valve is None:
            raise UnknownValveError(valve_id)
        return valve

    def all(self) -> tuple[Valve, ...]:
        return tuple(self._valves.values())

    def position(self, valve_id: str) -> str:
        valve = self._valves.get(valve_id)
        if valve is None:
            return POSITION_CLOSED
        return valve.position

    def reset_to_seed(self) -> None:
        for valve in self._valves.values():
            valve.position = POSITION_CLOSED
            valve.persisted = False
            valve.updated_at = 0

    def apply_positions(self, positions: dict[str, str], persisted_at: dict[str, int]) -> None:
        for valve_id, position in positions.items():
            valve = self._valves.get(valve_id)
            if valve is None:
                continue
            valve.position = position
            valve.updated_at = persisted_at.get(valve_id, valve.updated_at)
