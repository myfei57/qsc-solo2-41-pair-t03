"""Historical state rebuilt by replaying the visible record stream."""

from __future__ import annotations

from typing import Any

from tankfarm.event import topics
from tankfarm.journal import TOMBSTONE_KIND
from tankfarm.journal.record import Record
from tankfarm.sequence.stages import (
    FACT_NEW_TANK_OPEN,
    FACT_OLD_TANK_CLOSED,
    FACT_VALVE_PERSISTED,
)
from tankfarm.versioning.generation import (
    CONFIG_KEY,
    SCOPE_BASELINE,
    SCOPE_CONFIG,
    SCOPE_GAUGE_CONFIRM,
    SCOPE_VALVE_PERSIST,
)
from tankfarm.valve.persist import PERSIST_KEY


class StateProjection:
    """Folds records into the state a tank farm had at a given watermark."""

    def __init__(self) -> None:
        self.valve_positions: dict[str, str] = {}
        self.valve_ts: dict[str, int] = {}
        self.header_setpoint = 0.0
        self.pump_running: dict[str, bool] = {}
        self.gauges: dict[str, str] = {}
        self.gauge_confirmed: dict[str, bool] = {}
        self.gauge_generation: dict[str, int] = {}
        self.readings: dict[str, float] = {}
        self.offsets: dict[str, float] = {}
        self.baselines: dict[str, float] = {}
        self.baseline_generation: dict[str, int] = {}
        self.latches: dict[str, bool] = {}
        self.latch_reason: dict[str, str] = {}
        self.inert_alarm: dict[str, bool] = {}
        self.pressures: dict[str, float] = {}
        self.batches: dict[str, tuple[str, int]] = {}
        self.handoff_phase = ""
        self.trips = 0
        self.tests = 0
        self.tombstones: list[int] = []
        self.generations: dict[tuple[str, str], tuple[int, int]] = {}
        self.settings: dict[str, Any] = {}
        self.config_generation = 0
        self.applied = 0

    def apply(self, record: Record) -> None:
        kind = record.kind
        payload = record.payload
        if kind == topics.VALVE_POSITION:
            valve_id = str(payload["valve_id"])
            self.valve_positions[valve_id] = str(payload["position"])
            self.valve_ts[valve_id] = record.ts
        elif kind == topics.VALVE_PERSISTED:
            self._note_generation(SCOPE_VALVE_PERSIST, PERSIST_KEY, payload, record.ts)
        elif kind == topics.PUMP_STARTED:
            self.pump_running[str(payload["pump_id"])] = True
        elif kind == topics.PUMP_STOPPED:
            self.pump_running[str(payload["pump_id"])] = False
        elif kind == topics.HEADER_SETPOINT:
            self.header_setpoint = float(payload["setpoint"])
        elif kind == topics.TANK_SWITCHED:
            self.handoff_phase = str(payload["phase"])
        elif kind in (topics.INLET_OPENED, topics.INLET_RELEASED):
            self.handoff_phase = "inlet"
        elif kind == topics.LEVEL_READING:
            self.readings[str(payload["tank_id"])] = float(payload["reading"])
        elif kind == topics.LEVEL_GAUGE:
            tank_id = str(payload["tank_id"])
            self.gauges[tank_id] = str(payload["gauge_id"])
            self.gauge_confirmed[tank_id] = bool(payload["confirmed"])
            self._note_generation(SCOPE_GAUGE_CONFIRM, tank_id, payload, record.ts)
        elif kind == topics.LEVEL_BASELINE:
            tank_id = str(payload["tank_id"])
            self.baselines[tank_id] = float(payload["value"])
            self.offsets[tank_id] = float(payload["offset"])
            self._note_generation(SCOPE_BASELINE, tank_id, payload, record.ts)
        elif kind == topics.LEVEL_RECALIBRATED:
            self.offsets[str(payload["tank_id"])] = float(payload["offset"])
        elif kind == topics.ESD_LATCH:
            name = str(payload["latch"])
            if bool(payload["active"]):
                self.latches[name] = True
                self.latch_reason[name] = str(payload["reason"])
            else:
                self.latches.pop(name, None)
                self.latch_reason.pop(name, None)
        elif kind == topics.ESD_TRIP:
            self.trips += 1
        elif kind == topics.ESD_TEST:
            self.tests += 1
        elif kind == topics.INERT_ALARM:
            self.inert_alarm[str(payload["tank_id"])] = bool(payload["alarm"])
        elif kind == topics.INERT_PRESSURE:
            self.pressures[str(payload["tank_id"])] = float(payload["pressure"])
        elif kind == topics.BATCH_REGISTERED:
            self.batches[str(payload["batch_id"])] = (
                str(payload["tank_id"]),
                int(payload["generation"]),
            )
        elif kind == topics.CONFIG_REVISED:
            self.settings = dict(payload["settings"])
            self.config_generation = int(payload["generation"])
            self._note_generation(SCOPE_CONFIG, CONFIG_KEY, payload, record.ts)
        elif kind == TOMBSTONE_KIND:
            self.tombstones.append(int(payload["target_seq"]))
        self.applied += 1

    def facts(self) -> dict[str, bool]:
        return {
            FACT_VALVE_PERSISTED: bool(
                self.generations.get((SCOPE_VALVE_PERSIST, PERSIST_KEY))
            ),
            FACT_NEW_TANK_OPEN: self.valve_positions.get("valve-tank-new") == "open",
            FACT_OLD_TANK_CLOSED: self.valve_positions.get("valve-tank-old") != "open",
        }

    def snapshot(self) -> dict[str, Any]:
        return {
            "valves": dict(self.valve_positions),
            "header_setpoint": self.header_setpoint,
            "pumps": dict(self.pump_running),
            "gauges": dict(self.gauges),
            "gauge_confirmed": dict(self.gauge_confirmed),
            "gauge_generation": dict(self.gauge_generation),
            "readings": dict(self.readings),
            "offsets": dict(self.offsets),
            "baselines": dict(self.baselines),
            "baseline_generation": dict(self.baseline_generation),
            "latches": dict(self.latches),
            "latch_reason": dict(self.latch_reason),
            "inert_alarm": dict(self.inert_alarm),
            "pressures": dict(self.pressures),
            "batches": {key: list(value) for key, value in self.batches.items()},
            "handoff_phase": self.handoff_phase,
            "trips": self.trips,
            "tests": self.tests,
            "tombstones": list(self.tombstones),
            "generations": [
                [scope, key, number, ts]
                for (scope, key), (number, ts) in self.generations.items()
            ],
            "settings": dict(self.settings),
            "config_generation": self.config_generation,
            "applied_records": self.applied,
        }

    @classmethod
    def from_snapshot(cls, payload: Mapping[str, Any]) -> "StateProjection":
        projection = cls()
        projection.valve_positions = {
            str(key): str(value) for key, value in payload.get("valves", {}).items()
        }
        projection.header_setpoint = float(payload.get("header_setpoint", 0.0))
        projection.pump_running = {
            str(key): bool(value) for key, value in payload.get("pumps", {}).items()
        }
        projection.gauges = {
            str(key): str(value) for key, value in payload.get("gauges", {}).items()
        }
        projection.gauge_confirmed = {
            str(key): bool(value)
            for key, value in payload.get("gauge_confirmed", {}).items()
        }
        projection.gauge_generation = {
            str(key): int(value)
            for key, value in payload.get("gauge_generation", {}).items()
        }
        projection.readings = {
            str(key): float(value) for key, value in payload.get("readings", {}).items()
        }
        projection.offsets = {
            str(key): float(value) for key, value in payload.get("offsets", {}).items()
        }
        projection.baselines = {
            str(key): float(value) for key, value in payload.get("baselines", {}).items()
        }
        projection.baseline_generation = {
            str(key): int(value)
            for key, value in payload.get("baseline_generation", {}).items()
        }
        projection.latches = {
            str(key): bool(value) for key, value in payload.get("latches", {}).items()
        }
        projection.latch_reason = {
            str(key): str(value)
            for key, value in payload.get("latch_reason", {}).items()
        }
        projection.inert_alarm = {
            str(key): bool(value)
            for key, value in payload.get("inert_alarm", {}).items()
        }
        projection.pressures = {
            str(key): float(value) for key, value in payload.get("pressures", {}).items()
        }
        projection.batches = {
            str(key): (str(value[0]), int(value[1]))
            for key, value in payload.get("batches", {}).items()
        }
        projection.handoff_phase = str(payload.get("handoff_phase", ""))
        projection.trips = int(payload.get("trips", 0))
        projection.tests = int(payload.get("tests", 0))
        projection.tombstones = [int(item) for item in payload.get("tombstones", [])]
        projection.generations = {
            (str(scope), str(key)): (int(number), int(ts))
            for scope, key, number, ts in payload.get("generations", [])
        }
        projection.settings = dict(payload.get("settings", {}))
        projection.config_generation = int(payload.get("config_generation", 0))
        projection.applied = int(payload.get("applied_records", 0))
        return projection

    def _note_generation(
        self, scope: str, key: str, payload: dict[str, Any], ts: int
    ) -> None:
        number = payload.get("generation")
        if isinstance(number, int):
            self.generations[(scope, key)] = (number, ts)
