"""Shared equipment identifiers, limits and seeds."""

from __future__ import annotations

POSITION_OPEN = "open"
POSITION_CLOSED = "closed"

HIGH_LIMIT_MM = 9200.0
INERT_LOW_KPA = 80.0
INERT_HIGH_KPA = 120.0
INERT_SEED_KPA = 110.0

TANK_MAIN = "tank-main"
TANK_NEW = "tank-new"
TANK_OLD = "tank-old"
TANKS = (TANK_MAIN, TANK_NEW, TANK_OLD)

PUMP_A = "pump-a"
PUMP_B = "pump-b"
PUMPS = (PUMP_A, PUMP_B)

VALVE_INLET = "valve-inlet"
VALVE_OUTLET = "valve-outlet"
VALVE_ESD = "valve-esd"
VALVE_VENT = "valve-vent"
VALVE_TANK_NEW = "valve-tank-new"
VALVE_TANK_OLD = "valve-tank-old"
VALVES = (
    VALVE_INLET,
    VALVE_OUTLET,
    VALVE_ESD,
    VALVE_VENT,
    VALVE_TANK_NEW,
    VALVE_TANK_OLD,
)

TANK_GAUGE = {
    TANK_MAIN: "gauge-a",
    TANK_NEW: "gauge-b",
    TANK_OLD: "gauge-c",
}

TANK_CAPACITY_MM = {
    TANK_MAIN: 12000.0,
    TANK_NEW: 12000.0,
    TANK_OLD: 9000.0,
}

TANK_LEVEL_SEED = {
    TANK_MAIN: 5200.0,
    TANK_NEW: 3200.0,
    TANK_OLD: 1800.0,
}

TANK_OFFSET_SEED = 100.0
TANK_BASELINE_SEED = {
    tank_id: TANK_LEVEL_SEED[tank_id] - TANK_OFFSET_SEED for tank_id in TANKS
}

PUMP_VALVE = {
    PUMP_A: VALVE_OUTLET,
    PUMP_B: VALVE_TANK_OLD,
}

HEADER_ID = "header-main"

SOURCE_TANK = TANK_NEW
DESTINATION_TANK = TANK_OLD
PROCESS_TANK = TANK_NEW
