"""Device level behaviour of valves, pumps, tanks and levels."""

from __future__ import annotations

import pytest

from tankfarm.clock import LogicalClock
from tankfarm.domain import (
    POSITION_OPEN,
    PROCESS_TANK,
    VALVE_VENT,
)
from tankfarm.errors import (
    AlreadyRunningError,
    NegativeSetpointError,
    NonPositiveAmountError,
    NotRunningError,
    UnknownValveError,
)
from tankfarm.event import Event, EventBus
from tankfarm.event import topics
from tankfarm.ids import IdFactory
from tankfarm.judgement.filters import RecordFilter


def test_valve_open_sets_position_and_clears_durable_flag(services):
    services.persist_valves()
    assert services.valves.get(VALVE_VENT).persisted is True
    services.open_valve(VALVE_VENT)
    assert services.valves.position(VALVE_VENT) == POSITION_OPEN
    assert services.valves.get(VALVE_VENT).persisted is False


def test_unknown_valve_is_rejected(services):
    with pytest.raises(UnknownValveError):
        services.open_valve("valve-unknown")


def test_negative_setpoint_is_rejected(services):
    with pytest.raises(NegativeSetpointError):
        services.set_setpoint("pump-a", -1.0)


def test_header_arbiter_tracks_the_last_writer(services):
    services.set_setpoint("pump-a", 20.0)
    services.set_setpoint("pump-b", 35.0)
    assert services.arbiter.last_writer() == "pump-b"
    assert services.arbiter.value() == 35.0
    assert services.arbiter.demands() == {"pump-a": 20.0, "pump-b": 35.0}


def test_header_history_is_bounded(services):
    for value in range(12):
        services.set_setpoint("pump-a", float(value))
    assert len(services.header.history()) == 8
    assert services.header.history()[-1][1] == 11.0


def test_pump_ramp_walks_towards_the_target(services):
    steps = services.ramp_pump("pump-a", 12.0)["steps"]
    assert steps == [5.0, 10.0, 12.0]
    assert services.pumps.get("pump-a").setpoint == 12.0


def test_pump_ramp_to_current_setpoint_changes_nothing(services):
    assert services.ramp_pump("pump-a", 0.0)["steps"] == []


def test_pump_stop_without_running_is_rejected(services):
    with pytest.raises(NotRunningError):
        services.stop_pump("pump-a")


def test_pump_start_on_running_pump_is_rejected(services, handover):
    from tankfarm.pump.start import start_pump

    sheet_id = handover()
    services.start_pump("pump-a", sheet_id)
    with pytest.raises(AlreadyRunningError):
        start_pump(
            services.pumps.get("pump-a"),
            services.journal,
            services.bus,
            services.clock,
        )


def test_level_fill_rejects_non_positive_amount(services):
    with pytest.raises(NonPositiveAmountError):
        services.levels.fill(PROCESS_TANK, 0.0)


def test_level_draw_never_goes_below_zero(services):
    state = services.levels.draw(PROCESS_TANK, 999_999.0)
    assert state.reading == 0.0


def test_gauge_switch_unconfirms_channel_until_confirmed(services):
    sheet = services.switch_gauge(PROCESS_TANK, "gauge-b2")
    assert services.levels.is_confirmed(PROCESS_TANK) is False
    services.confirm_gauge(sheet.sheet_id)
    assert services.levels.is_confirmed(PROCESS_TANK) is True
    assert services.levels.gauge_of(PROCESS_TANK) == "gauge-b2"


def test_recent_level_updates_keep_newest_entries(services):
    services.levels.fill(PROCESS_TANK, 10.0)
    services.levels.fill(PROCESS_TANK, 20.0)
    updates = services.levels.recent_updates(1)
    assert len(updates) == 1
    assert updates[0].reading == 3230.0


def test_tank_summary_reports_remaining_headroom(services):
    summary = [item for item in services.tank_summaries() if item.tank_id == PROCESS_TANK][
        0
    ]
    assert summary.capacity_mm == 12000.0
    assert summary.remaining_mm == pytest.approx(12000.0 - 3100.0)


def test_capacity_estimator_clamps_negative_net_volume(services):
    services.recalibrate(PROCESS_TANK, 10_000.0)
    assert services.capacity.net_volume(PROCESS_TANK) == 0.0


def test_event_bus_delivers_to_every_handler():
    bus = EventBus()
    seen: list[str] = []
    bus.subscribe("topic", lambda event: seen.append("first"))
    bus.subscribe("topic", lambda event: seen.append("second"))
    delivered = bus.publish(Event(topic="topic", value=None, ts=1))
    assert delivered == 2
    assert seen == ["first", "second"]
    assert bus.topics() == ("topic",)
    bus.close()
    assert bus.topics() == ()


def test_id_factory_produces_deterministic_identifiers():
    ids = IdFactory()
    assert ids.new("rec") == "rec-000001"
    assert ids.new("rec") == "rec-000002"
    assert ids.new("sheet") == "sheet-000001"
    assert ids.counters() == {"rec": 2, "sheet": 1}


def test_logical_clock_ticks_are_monotonic():
    clock = LogicalClock(start=100)
    assert clock.now() == 100
    assert clock.tick() == 101
    assert clock.tick(4) == 105
    assert clock.age(100) == 5
    with pytest.raises(ValueError):
        clock.tick(0)


def test_valve_payload_describes_the_current_position(services):
    services.open_valve(VALVE_VENT)
    payload = services.valves.get(VALVE_VENT).as_payload()
    assert payload == {
        "valve_id": VALVE_VENT,
        "name": "vent",
        "position": POSITION_OPEN,
        "persisted": False,
    }


def test_ramp_records_intermediate_setpoints_in_order(services):
    services.ramp_pump("pump-a", 12.0)
    assert [value for _, value in services.header.history()] == [5.0, 10.0, 12.0]


def test_ramp_rejects_a_negative_target(services):
    with pytest.raises(NegativeSetpointError):
        services.ramp_pump("pump-a", -5.0)


def test_header_setpoint_follows_the_last_writer(services):
    services.set_setpoint("pump-a", 20.0)
    services.set_setpoint("pump-b", 30.0)
    assert services.arbiter.value() == 30.0
    assert services.arbiter.demands()["pump-a"] == 20.0


def test_pump_stop_records_the_esd_state(services, handover):
    sheet_id = handover()
    services.start_pump("pump-a", sheet_id)
    services.stop_pump("pump-a")
    selected = services.select_records(RecordFilter(kinds=(topics.PUMP_STOPPED,)))
    assert selected[-1].payload["esd_closed"] is True
