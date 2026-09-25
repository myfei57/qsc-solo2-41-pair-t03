"""Topic names carried by the event bus and the record stream."""

from __future__ import annotations

VALVE_POSITION = "valve.position"
VALVE_PERSISTED = "valve.persisted"
PUMP_STARTED = "pump.started"
PUMP_STOPPED = "pump.stopped"
HEADER_SETPOINT = "header.setpoint"
TANK_SWITCHED = "tank.switched"
INLET_OPENED = "inlet.opened"
INLET_RELEASED = "inlet.released"
LEVEL_READING = "level.reading"
LEVEL_GAUGE = "level.gauge"
LEVEL_BASELINE = "level.baseline"
LEVEL_RECALIBRATED = "level.recalibrated"
ESD_LATCH = "esd.latch"
ESD_TRIP = "esd.trip"
ESD_TEST = "esd.test"
INERT_ALARM = "inert.alarm"
INERT_PRESSURE = "inert.pressure"
SEQUENCE_STAGE = "sequence.stage"
BATCH_REGISTERED = "batch.registered"
CONFIG_REVISED = "config.revised"

AUDITED_TOPICS = (
    VALVE_POSITION,
    VALVE_PERSISTED,
    PUMP_STARTED,
    PUMP_STOPPED,
    HEADER_SETPOINT,
    TANK_SWITCHED,
    INLET_OPENED,
    INLET_RELEASED,
    LEVEL_READING,
    LEVEL_GAUGE,
    LEVEL_BASELINE,
    LEVEL_RECALIBRATED,
    ESD_LATCH,
    ESD_TRIP,
    ESD_TEST,
    INERT_ALARM,
    INERT_PRESSURE,
    SEQUENCE_STAGE,
    BATCH_REGISTERED,
    CONFIG_REVISED,
)
