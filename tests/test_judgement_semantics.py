"""Contract (d): current versus historical state, batch identity, filters."""

from __future__ import annotations

import pytest

from tankfarm.domain import (
    DESTINATION_TANK,
    POSITION_CLOSED,
    POSITION_OPEN,
    PROCESS_TANK,
    VALVE_INLET,
    VALVE_VENT,
)
from tankfarm.errors import BatchNotFoundError, DuplicateBatchError
from tankfarm.event import topics
from tankfarm.judgement.filters import RecordFilter
from tankfarm.measure import Threshold, Window
from tankfarm.sequence.stages import STAGE_OLD_TANK_CLOSED, STAGE_VALVES_PERSISTED


def test_batch_registration_is_unique(services):
    services.register_batch("batch-1")
    with pytest.raises(DuplicateBatchError):
        services.register_batch("batch-1")


def test_batch_registration_carries_active_config_generation(services):
    registration = services.register_batch("batch-7")
    assert registration.generation == services.revisions.active().generation
    assert registration.tank_id == PROCESS_TANK


def test_unknown_batch_lookup_is_rejected(services):
    with pytest.raises(BatchNotFoundError):
        services.get_batch("batch-missing")


def test_batches_for_tank_lists_only_matching_batches(services):
    services.register_batch("batch-a", PROCESS_TANK)
    services.register_batch("batch-b", DESTINATION_TANK)
    assert [item.batch_id for item in services.batches.for_tank(PROCESS_TANK)] == [
        "batch-a"
    ]


def test_current_state_matches_history_at_current_watermark(services):
    services.persist_valves()
    report = services.history()
    differences = services.current_view().differences(report["state"])
    assert differences["valves"]["same"] is True
    assert differences["stage"]["same"] is True
    assert differences["identical"] is True


def test_history_at_earlier_watermark_shows_earlier_stage(services):
    services.persist_valves()
    marker = services.commits.watermark()
    services.change_tank()
    assert services.history(marker)["state"]["stage"] == STAGE_VALVES_PERSISTED
    assert services.machine.stage() == STAGE_OLD_TANK_CLOSED


def test_current_state_differs_from_history_before_handover(services):
    services.persist_valves()
    marker = services.commits.watermark()
    services.change_tank()
    differences = services.current_view().differences(services.history(marker)["state"])
    assert differences["stage"]["same"] is False
    assert differences["identical"] is False


def test_threshold_reports_at_or_above_and_below():
    threshold = Threshold(9200.0)
    assert threshold.at_or_above(9200.0) is True
    assert threshold.at_or_above(9199.9) is False
    assert threshold.below(9199.9) is True
    assert threshold.below(9200.0) is False


def test_window_contains_and_classifies_values():
    window = Window(80.0, 120.0)
    assert window.contains(80.0) is True
    assert window.contains(120.0) is True
    assert window.contains(121.0) is False
    assert window.classify(50.0) == "low"
    assert window.classify(110.0) == "ok"
    assert window.classify(150.0) == "high"


def test_level_limits_follow_config_revision(services):
    assert services.limits.high_limit() == 9200.0
    services.revise_config({"high_limit_mm": 9000.0})
    assert services.limits.high_limit() == 9000.0
    assert services.limits.at_high(9100.0) is True


def test_blanket_limits_follow_config_revision(services):
    services.revise_config({"inert_low_kpa": 90.0, "inert_high_kpa": 130.0})
    assert services.blanket.confirmed(85.0) is False
    assert services.blanket.confirmed(100.0) is True


def test_inert_check_uses_blanket_window(services):
    services.set_inert_pressure(PROCESS_TANK, 150.0)
    assert services.inert.check(PROCESS_TANK) is False
    services.set_inert_pressure(PROCESS_TANK, 110.0)
    assert services.inert.check(PROCESS_TANK) is True


def test_record_filter_selects_by_kind(services):
    services.persist_valves()
    selected = services.select_records(RecordFilter(kinds=(topics.VALVE_PERSISTED,)))
    assert [record.kind for record in selected] == [topics.VALVE_PERSISTED]


def test_record_filter_respects_sequence_window(services):
    services.persist_valves()
    selected = services.select_records(RecordFilter(min_seq=3, max_seq=4))
    assert [record.seq for record in selected] == [3, 4]


def test_record_filter_limit_keeps_newest_records(services):
    services.persist_valves()
    selected = services.select_records(RecordFilter(limit=2))
    assert len(selected) == 2
    assert selected[-1].seq == services.stream.head()


def test_record_filter_matches_valve_subject(services):
    services.open_valve(VALVE_VENT)
    selected = services.select_records(RecordFilter(subject=VALVE_VENT))
    assert [record.payload["valve_id"] for record in selected] == [VALVE_VENT]


def test_rolled_back_record_disappears_from_state_and_selection(services):
    services.open_valve(VALVE_VENT)
    record = services.select_records(RecordFilter(subject=VALVE_VENT))[-1]
    services.rollback(record.seq, "wrong valve")
    assert services.valves.position(VALVE_VENT) == POSITION_CLOSED
    assert services.select_records(RecordFilter(subject=VALVE_VENT)) == ()


def test_record_filter_excludes_uncommitted_tail(services):
    checkpoint = services.commits.watermark()
    services.journal.append(
        topics.VALVE_POSITION, {"valve_id": VALVE_VENT, "position": "open"}
    )
    visible = services.select_records(RecordFilter(subject=VALVE_VENT))
    assert visible == ()
    assert services.stream.head() == checkpoint + 1


def test_history_excludes_the_effect_of_a_rolled_back_record(services):
    services.open_valve(VALVE_VENT)
    marker = services.commits.watermark()
    record = services.select_records(RecordFilter(subject=VALVE_VENT))[-1]
    services.rollback(record.seq, "wrong valve")
    state = services.history(marker)["state"]
    assert state["valves"].get(VALVE_VENT) != POSITION_OPEN


def test_batch_uniqueness_is_per_identifier_not_per_tank(services):
    services.register_batch("batch-1", PROCESS_TANK)
    with pytest.raises(DuplicateBatchError):
        services.register_batch("batch-1", DESTINATION_TANK)


def test_filter_subject_does_not_match_other_equipment(services):
    services.open_valve(VALVE_VENT)
    assert services.select_records(RecordFilter(subject=VALVE_INLET)) == ()
