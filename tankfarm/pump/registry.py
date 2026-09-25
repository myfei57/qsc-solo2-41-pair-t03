"""Pump lookup table."""

from __future__ import annotations

from tankfarm.domain import PUMP_A, PUMP_B, PUMP_VALVE, PUMPS
from tankfarm.errors import UnknownPumpError
from tankfarm.pump.model import Pump

PUMP_NAMES = {
    PUMP_A: "transfer pump A",
    PUMP_B: "transfer pump B",
}


class PumpRegistry:
    """Holds the transfer pumps of the header."""

    def __init__(self) -> None:
        self._pumps: dict[str, Pump] = {}

    @classmethod
    def seeded(cls) -> "PumpRegistry":
        registry = cls()
        for pump_id in PUMPS:
            registry.register(
                Pump(
                    pump_id=pump_id,
                    name=PUMP_NAMES[pump_id],
                    valve_id=PUMP_VALVE[pump_id],
                )
            )
        return registry

    def register(self, pump: Pump) -> None:
        self._pumps[pump.pump_id] = pump

    def get(self, pump_id: str) -> Pump:
        pump = self._pumps.get(pump_id)
        if pump is None:
            raise UnknownPumpError(pump_id)
        return pump

    def all(self) -> tuple[Pump, ...]:
        return tuple(self._pumps.values())

    def running_ids(self) -> tuple[str, ...]:
        return tuple(pump.pump_id for pump in self._pumps.values() if pump.running)

    def reset_to_seed(self) -> None:
        for pump in self._pumps.values():
            pump.running = False
            pump.setpoint = 0.0

    def apply_running(self, running: dict[str, bool]) -> None:
        for pump_id, is_running in running.items():
            pump = self._pumps.get(pump_id)
            if pump is not None:
                pump.running = bool(is_running)
