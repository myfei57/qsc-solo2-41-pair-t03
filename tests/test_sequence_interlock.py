"""Contract (c): stage order, pre-gates and latch conditions."""

from __future__ import annotations

import pytest

from tankfarm.domain import (
    POSITION_CLOSED,
    POSITION_OPEN,
    PROCESS_TANK,
    VALVE_INLET,
    VALVE_TANK_NEW,
    VALVE_TANK_OLD,
)
from tankfarm.errors import (
    GateBlockedError,
    InertNotConfirmedError,
    LatchActiveError,
    LevelTooHighError,
    NotPersistedError,
    OutOfOrderError,
    StageAlreadyReachedError,
)
from tankfarm.event import topics
from tankfarm.interlock.rules import BLANKET_LATCH, OVERFILL_LATCH
from tankfarm.judgement.filters import RecordFilter
from tankfarm.sequence.stages import (
    FACT_NEW_TANK_OPEN,
    FACT_OLD_TANK_CLOSED,
    FACT_VALVE_PERSISTED,
    STAGE_NEW_TANK_OPEN,
    STAGE_OLD_TANK_CLOSED,
    STAGE_PUMP_RUNNING,
    STAGE_VALVES_PERSISTED,
)


def test_pump_start_is_rejected_out_of_order_before_handover(services):
    sheet = services.persist_valves()
    with pytest.raises(OutOfOrderError):
        services.start_pump("pump-a", sheet.sheet_id)


def test_tank_handover_before_persist_is_rejected(services):
    with pytest.raises(OutOfOrderError):
        services.change_tank()


def test_sequence_machine_rejects_stage_without_its_gate_evidence(services):
    services.machine.advance(STAGE_VALVES_PERSISTED)
    with pytest.raises(GateBlockedError):
        services.machine.advance("new-tank-open")


def test_pump_start_is_rejected_when_valve_positions_are_not_durable(
    services, handover
):
    sheet_id = handover()
    services.open_valve(VALVE_INLET)
    with pytest.raises(NotPersistedError):
        services.start_pump("pump-a", sheet_id)


def test_pump_start_succeeds_after_handover_and_fresh_persist(services, handover):
    sheet_id = handover()
    result = services.start_pump("pump-a", sheet_id)
    assert result["pump_id"] == "pump-a"
    assert services.pumps.get("pump-a").running is True
    assert services.machine.stage() == STAGE_PUMP_RUNNING


def test_pump_start_twice_is_rejected_as_stage_already_reached(services, handover):
    sheet_id = handover()
    services.start_pump("pump-a", sheet_id)
    services.persist_valves()
    with pytest.raises(StageAlreadyReachedError):
        services.start_pump("pump-a", sheet_id)


def test_persisting_positions_twice_refreshes_sheet_without_repeating_stage(services):
    first = services.persist_valves()
    assert services.machine.stage() == STAGE_VALVES_PERSISTED
    second = services.persist_valves()
    assert services.machine.stage() == STAGE_VALVES_PERSISTED
    assert second.sheet_id != first.sheet_id
    assert second.generation > first.generation


def test_tank_handover_opens_new_tank_before_closing_old(services):
    services.persist_valves()
    services.change_tank()
    assert services.valves.position(VALVE_TANK_NEW) == POSITION_OPEN
    assert services.valves.position(VALVE_TANK_OLD) == POSITION_CLOSED
    assert services.machine.stage() == STAGE_OLD_TANK_CLOSED


def test_tank_handover_twice_is_rejected_as_already_reached(services):
    services.persist_valves()
    services.change_tank()
    with pytest.raises(StageAlreadyReachedError):
        services.change_tank()


def test_handover_retry_completes_only_the_missing_step(services):
    services.persist_valves()
    services.change_tank()
    services.switcher.open(VALVE_TANK_OLD)
    assert services.retry_change_tank()["steps"] == ["old-close"]
    assert services.valves.position(VALVE_TANK_OLD) == POSITION_CLOSED


def test_handover_retry_before_start_is_rejected(services):
    with pytest.raises(GateBlockedError):
        services.retry_change_tank()


def test_overfill_latch_is_set_when_level_reaches_high_limit(services):
    services.fill_inlet(6000.0)
    assert services.limits.at_high(services.levels.read_confirmed(PROCESS_TANK)) is True
    assert services.engine.is_active(OVERFILL_LATCH) is True


def test_overfill_latch_blocks_pump_start(services, handover):
    sheet_id = handover()
    services.fill_inlet(6000.0)
    services.persist_valves()
    with pytest.raises(LatchActiveError):
        services.start_pump("pump-a", sheet_id)


def test_overfill_latch_clears_after_level_recovers(services):
    services.fill_inlet(6000.0)
    assert services.engine.is_active(OVERFILL_LATCH) is True
    services.draw_level(PROCESS_TANK, 400.0)
    assert services.engine.is_active(OVERFILL_LATCH) is False


def test_blanket_latch_is_set_on_alarm_and_blocks_inlet(services):
    services.raise_inert_alarm(PROCESS_TANK)
    assert services.engine.is_active(BLANKET_LATCH) is True
    with pytest.raises(InertNotConfirmedError):
        services.open_inlet()


def test_blanket_latch_clears_after_alarm_is_cleared(services):
    services.raise_inert_alarm(PROCESS_TANK)
    services.clear_inert_alarm(PROCESS_TANK)
    assert services.engine.is_active(BLANKET_LATCH) is False
    assert services.open_inlet()["open"] is True


def test_inlet_fill_is_rejected_when_blanket_pressure_leaves_window(services):
    services.set_inert_pressure(PROCESS_TANK, 60.0)
    with pytest.raises(InertNotConfirmedError):
        services.fill_inlet(100.0)


def test_esd_trip_closes_valve_and_stops_running_pump(services, handover):
    sheet_id = handover()
    services.start_pump("pump-a", sheet_id)
    services.fill_inlet(6000.0)
    result = services.trip_esd()
    assert result.tripped is True
    assert services.esd_valve.is_closed() is True
    assert services.pumps.get("pump-a").running is False
    assert services.engine.is_active(OVERFILL_LATCH) is True


def test_esd_retrip_is_idempotent_when_plant_is_already_safe(services):
    services.fill_inlet(6000.0)
    services.trip_esd()
    second = services.retrip_esd()
    assert second.tripped is False
    assert second.latched is True


def test_esd_reset_is_rejected_while_level_is_high(services):
    services.fill_inlet(6000.0)
    with pytest.raises(LevelTooHighError):
        services.reset_esd()


def test_esd_reset_releases_latch_after_level_recovers(services):
    services.fill_inlet(6000.0)
    services.draw_level(PROCESS_TANK, 500.0)
    services.test_esd()
    assert services.engine.is_active(OVERFILL_LATCH) is True
    services.reset_esd()
    assert services.engine.is_active(OVERFILL_LATCH) is False


def test_overfill_interlock_reports_limit_and_reading(services):
    services.fill_inlet(6000.0)
    report = services.interlock_report(PROCESS_TANK)
    assert report.overfilled is True
    assert report.safe is False
    assert report.limit == 9200.0
    assert report.reading == pytest.approx(9200.0)
    assert report.raw_reading == pytest.approx(9200.0)


def test_sequence_machine_rejects_a_multi_stage_jump(services):
    with pytest.raises(OutOfOrderError):
        services.machine.advance(STAGE_OLD_TANK_CLOSED)


def test_each_stage_step_is_recorded_exactly_once(services):
    services.persist_valves()
    services.change_tank()
    selected = services.select_records(RecordFilter(kinds=(topics.SEQUENCE_STAGE,)))
    assert [record.payload["stage"] for record in selected] == [
        STAGE_VALVES_PERSISTED,
        STAGE_NEW_TANK_OPEN,
        STAGE_OLD_TANK_CLOSED,
    ]


def test_handover_records_one_entry_per_movement_phase(services):
    services.persist_valves()
    services.change_tank()
    selected = services.select_records(RecordFilter(kinds=(topics.TANK_SWITCHED,)))
    assert [record.payload["phase"] for record in selected] == ["new-open", "old-close"]


def test_restart_restores_sequence_stage_and_gate_facts(services, restart, handover):
    sheet_id = handover()
    services.start_pump("pump-a", sheet_id)
    fresh = restart()
    assert fresh.machine.stage() == STAGE_PUMP_RUNNING
    assert fresh.machine.facts() == {
        FACT_VALVE_PERSISTED: True,
        FACT_NEW_TANK_OPEN: True,
        FACT_OLD_TANK_CLOSED: True,
    }


def test_overfill_latch_stays_set_while_a_pump_is_running(services, handover):
    sheet_id = handover()
    services.start_pump("pump-a", sheet_id)
    services.engine.set(OVERFILL_LATCH, "manual trip")
    services.draw_level(PROCESS_TANK, 100.0)
    assert services.engine.is_active(OVERFILL_LATCH) is True


def test_overfill_latch_stays_set_while_the_esd_valve_is_open(services):
    services.esd_valve.open()
    services.engine.set(OVERFILL_LATCH, "manual trip")
    services.draw_level(PROCESS_TANK, 100.0)
    assert services.engine.is_active(OVERFILL_LATCH) is True


def test_blanket_latch_stays_set_while_pressure_is_outside_the_window(services):
    services.raise_inert_alarm(PROCESS_TANK)
    services.set_inert_pressure(PROCESS_TANK, 60.0)
    services.clear_inert_alarm(PROCESS_TANK)
    assert services.inert.check(PROCESS_TANK) is False
    assert services.engine.is_active(BLANKET_LATCH) is True


def test_latches_release_independently(services):
    services.esd_valve.open()
    services.engine.set(OVERFILL_LATCH, "manual trip")
    services.raise_inert_alarm(PROCESS_TANK)
    services.clear_inert_alarm(PROCESS_TANK)
    assert services.engine.is_active(BLANKET_LATCH) is False
    assert services.engine.is_active(OVERFILL_LATCH) is True


def test_restart_restores_each_latch_separately(services, restart):
    services.esd_valve.open()
    services.engine.set(OVERFILL_LATCH, "manual trip")
    services.raise_inert_alarm(PROCESS_TANK)
    fresh = restart()
    assert fresh.engine.is_active(OVERFILL_LATCH) is True
    assert fresh.engine.is_active(BLANKET_LATCH) is True


def test_esd_reset_releases_only_the_overfill_latch(services):
    services.esd_valve.open()
    services.engine.set(OVERFILL_LATCH, "manual trip")
    services.raise_inert_alarm(PROCESS_TANK)
    services.esd_valve.close()
    services.reset_esd()
    assert services.engine.is_active(OVERFILL_LATCH) is False
    assert services.engine.is_active(BLANKET_LATCH) is True


def test_trip_records_the_pumps_it_stopped(services, handover):
    sheet_id = handover()
    services.start_pump("pump-a", sheet_id)
    services.fill_inlet(6000.0)
    services.trip_esd()
    selected = services.select_records(RecordFilter(kinds=(topics.ESD_TRIP,)))
    assert selected
    assert selected[-1].payload["stopped"] == ["pump-a"]
