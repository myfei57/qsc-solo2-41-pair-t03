"""Durable storage and restart replay."""

from __future__ import annotations

from tankfarm.domain import (
    POSITION_CLOSED,
    POSITION_OPEN,
    PROCESS_TANK,
    VALVE_TANK_NEW,
    VALVE_VENT,
)
from tankfarm.event import topics
from tankfarm.judgement.filters import RecordFilter
from tankfarm.sequence.stages import STAGE_IDLE, STAGE_PUMP_RUNNING


def test_restart_without_records_keeps_seed_state(services, restart):
    fresh = restart()
    assert fresh.machine.stage() == STAGE_IDLE
    assert fresh.commits.watermark() == 0


def test_journal_file_keeps_one_line_per_record(services):
    services.persist_valves()
    lines = (
        services.repository.layout.journal_file()
        .read_text(encoding="utf-8")
        .splitlines()
    )
    assert len(lines) == services.stream.head()


def test_checkpoint_file_records_the_watermark(services):
    services.persist_valves()
    checkpoint = services.repository.load_checkpoint()
    assert checkpoint is not None
    assert checkpoint.watermark == services.commits.watermark()
    assert checkpoint.head == services.stream.head()


def test_restart_restores_devices_from_the_record_stream(services, restart, handover):
    sheet_id = handover()
    services.start_pump("pump-a", sheet_id)
    services.open_valve(VALVE_VENT)
    fresh = restart()
    assert fresh.pumps.get("pump-a").running is True
    assert fresh.machine.stage() == STAGE_PUMP_RUNNING
    assert fresh.valves.position(VALVE_VENT) == POSITION_OPEN
    assert fresh.valves.position(VALVE_TANK_NEW) == POSITION_OPEN


def test_restart_restores_level_readings(services, restart):
    services.fill_inlet(250.0)
    fresh = restart()
    assert fresh.levels.read_raw(PROCESS_TANK) == 3450.0


def test_restart_skips_uncommitted_tail_records(services, restart):
    services.open_valve(VALVE_VENT)
    checkpoint = services.commits.watermark()
    services.journal.append(
        topics.VALVE_POSITION, {"valve_id": VALVE_VENT, "position": POSITION_CLOSED}
    )
    assert services.stream.head() == checkpoint + 1
    fresh = restart()
    assert fresh.valves.position(VALVE_VENT) == POSITION_OPEN
    assert fresh.commits.watermark() == checkpoint
    assert fresh.stream.head() == checkpoint + 1
    assert len(fresh.commits.pending()) == 1


def test_restart_ignores_rolled_back_records(services, restart):
    services.open_valve(VALVE_TANK_NEW)
    record = services.select_records(RecordFilter(subject=VALVE_TANK_NEW))[-1]
    services.rollback(record.seq, "operator rollback")
    fresh = restart()
    assert fresh.valves.position(VALVE_TANK_NEW) == POSITION_CLOSED


def test_restart_restores_the_config_revision(services, restart):
    services.revise_config({"high_limit_mm": 8800.0})
    fresh = restart()
    assert fresh.limits.high_limit() == 8800.0
    assert fresh.revisions.active().generation == 2


def test_restart_restores_registered_batches(services, restart):
    services.register_batch("batch-9", PROCESS_TANK)
    fresh = restart()
    assert fresh.get_batch("batch-9").tank_id == PROCESS_TANK


def test_restart_restores_active_latches(services, restart):
    services.fill_inlet(6000.0)
    assert services.engine.active_latches() == ("overfill",)
    fresh = restart()
    assert fresh.engine.is_active("overfill") is True


def test_restart_restores_header_setpoint(services, restart):
    services.set_setpoint("pump-a", 45.0)
    fresh = restart()
    assert fresh.header.setpoint() == 45.0
