"""Tank lookup table."""

from __future__ import annotations

from tankfarm.domain import TANK_CAPACITY_MM, TANKS
from tankfarm.errors import UnknownTankError
from tankfarm.tank.model import Tank

TANK_NAMES = {
    "tank-main": "main storage",
    "tank-new": "transfer source",
    "tank-old": "transfer destination",
}


class TankRegistry:
    """Holds the tanks of the farm."""

    def __init__(self) -> None:
        self._tanks: dict[str, Tank] = {}

    @classmethod
    def seeded(cls) -> "TankRegistry":
        registry = cls()
        for tank_id in TANKS:
            registry.register(
                Tank(
                    tank_id=tank_id,
                    name=TANK_NAMES[tank_id],
                    capacity_mm=TANK_CAPACITY_MM[tank_id],
                )
            )
        return registry

    def register(self, tank: Tank) -> None:
        self._tanks[tank.tank_id] = tank

    def get(self, tank_id: str) -> Tank:
        tank = self._tanks.get(tank_id)
        if tank is None:
            raise UnknownTankError(tank_id)
        return tank

    def all(self) -> tuple[Tank, ...]:
        return tuple(self._tanks.values())
