"""Contract (b): generations, confirmation sheets, baselines and snapshots."""

from __future__ import annotations

import pytest

from tankfarm.domain import PROCESS_TANK
from tankfarm.errors import (
    BaselineNotFoundError,
    DuplicateSheetError,
    ExpiredBaselineError,
    ExpiredSheetError,
    ExpiredSnapshotError,
    SheetNotFoundError,
    StaleGenerationError,
    UnknownGenerationError,
)
from tankfarm.ids import IdFactory
from tankfarm.versioning import (
    BaselineBook,
    ExpiryPolicy,
    GenerationRegistry,
    SheetBook,
    SnapshotBook,
)
from tankfarm.versioning.generation import CONFIG_KEY, SCOPE_CONFIG, SCOPE_BASELINE

TEST_SCOPE = "test.resource"
TEST_KEY = "unit"


@pytest.fixture
def registry() -> GenerationRegistry:
    return GenerationRegistry()


@pytest.fixture
def sheets() -> SheetBook:
    return SheetBook(IdFactory())


def test_generation_bump_increments_per_scope_and_key(registry):
    assert registry.bump(TEST_SCOPE, TEST_KEY, 1).number == 1
    assert registry.bump(TEST_SCOPE, TEST_KEY, 2).number == 2
    assert registry.current(TEST_SCOPE, TEST_KEY) == 2
    assert registry.current(TEST_SCOPE, "other") == 0


def test_require_accepts_current_generation(registry):
    registry.bump(TEST_SCOPE, TEST_KEY, 1)
    assert registry.require(TEST_SCOPE, TEST_KEY, 1).number == 1


def test_require_rejects_stale_generation(registry):
    registry.bump(TEST_SCOPE, TEST_KEY, 1)
    registry.bump(TEST_SCOPE, TEST_KEY, 2)
    with pytest.raises(StaleGenerationError):
        registry.require(TEST_SCOPE, TEST_KEY, 1)


def test_require_rejects_generation_ahead_of_current(registry):
    registry.bump(TEST_SCOPE, TEST_KEY, 1)
    with pytest.raises(UnknownGenerationError):
        registry.require(TEST_SCOPE, TEST_KEY, 4)


def test_restore_sets_generation_without_bumping(registry):
    registry.restore(TEST_SCOPE, TEST_KEY, 7, 11)
    assert registry.current(TEST_SCOPE, TEST_KEY) == 7
    assert registry.generation(TEST_SCOPE, TEST_KEY).issued_at == 11


def test_expiry_policy_never_expires_when_max_age_is_zero():
    policy = ExpiryPolicy(0)
    assert policy.expired(1, 10_000) is False


def test_expiry_policy_expires_after_max_age():
    policy = ExpiryPolicy(5)
    assert policy.expired(100, 105) is False
    assert policy.expired(100, 106) is True
    assert policy.age(100, 106) == 6


def test_sheet_consume_rejects_expired_sheet(registry, sheets):
    sheet = sheets.issue(TEST_SCOPE, TEST_KEY, 0, 0, 100, ExpiryPolicy(3))
    with pytest.raises(ExpiredSheetError):
        sheets.consume(sheet.sheet_id, 104, registry)
    assert sheets.get(sheet.sheet_id).state == "expired"


def test_sheet_consume_rejects_duplicate_use(registry, sheets):
    sheet = sheets.issue(TEST_SCOPE, TEST_KEY, 0, 0, 100, ExpiryPolicy(0))
    sheets.consume(sheet.sheet_id, 100, registry)
    with pytest.raises(DuplicateSheetError):
        sheets.consume(sheet.sheet_id, 101, registry)


def test_sheet_consume_rejects_stale_subject_generation(registry, sheets):
    registry.bump(TEST_SCOPE, TEST_KEY, 1)
    sheet = sheets.issue(TEST_SCOPE, TEST_KEY, 1, 0, 100, ExpiryPolicy(0))
    registry.bump(TEST_SCOPE, TEST_KEY, 2)
    with pytest.raises(StaleGenerationError):
        sheets.consume(sheet.sheet_id, 100, registry)


def test_sheet_consume_rejects_stale_config_generation(registry, sheets):
    registry.bump(SCOPE_CONFIG, CONFIG_KEY, 1)
    sheet = sheets.issue(TEST_SCOPE, TEST_KEY, 0, 1, 100, ExpiryPolicy(0))
    registry.bump(SCOPE_CONFIG, CONFIG_KEY, 2)
    with pytest.raises(StaleGenerationError):
        sheets.consume(sheet.sheet_id, 100, registry)


def test_sheet_consume_rejects_unknown_sheet(registry, sheets):
    with pytest.raises(SheetNotFoundError):
        sheets.consume("sheet-missing", 100, registry)


def test_baseline_validate_rejects_expired_baseline(registry):
    book = BaselineBook()
    registry.bump(SCOPE_BASELINE, PROCESS_TANK, 1)
    book.record(PROCESS_TANK, 3000.0, 1, 0, 100, ExpiryPolicy(10))
    with pytest.raises(ExpiredBaselineError):
        book.validate(PROCESS_TANK, 200, registry)


def test_baseline_validate_rejects_stale_baseline(registry):
    book = BaselineBook()
    registry.bump(SCOPE_BASELINE, PROCESS_TANK, 1)
    book.record(PROCESS_TANK, 3000.0, 1, 0, 100, ExpiryPolicy(0))
    registry.bump(SCOPE_BASELINE, PROCESS_TANK, 2)
    with pytest.raises(StaleGenerationError):
        book.validate(PROCESS_TANK, 100, registry)


def test_baseline_validate_rejects_unknown_tank(registry):
    book = BaselineBook()
    with pytest.raises(BaselineNotFoundError):
        book.validate(PROCESS_TANK, 100, registry)


def test_snapshot_validate_rejects_expired_snapshot(registry):
    book = SnapshotBook(IdFactory())
    registry.bump(TEST_SCOPE, TEST_KEY, 1)
    snapshot = book.capture({}, 3, TEST_SCOPE, TEST_KEY, 1, 0, 100, ExpiryPolicy(5))
    with pytest.raises(ExpiredSnapshotError):
        book.validate(snapshot.snapshot_id, 200, registry)


def test_snapshot_validate_rejects_stale_generation(registry):
    book = SnapshotBook(IdFactory())
    registry.bump(TEST_SCOPE, TEST_KEY, 1)
    snapshot = book.capture({}, 3, TEST_SCOPE, TEST_KEY, 1, 0, 100, ExpiryPolicy(0))
    registry.bump(TEST_SCOPE, TEST_KEY, 2)
    with pytest.raises(StaleGenerationError):
        book.validate(snapshot.snapshot_id, 100, registry)


def test_confirm_sheet_is_rejected_after_clock_tick(services):
    sheet = services.switch_gauge(PROCESS_TANK, "gauge-b2")
    services.tick_clock(100)
    with pytest.raises(ExpiredSheetError):
        services.confirm_gauge(sheet.sheet_id)


def test_confirm_sheet_is_rejected_after_config_revision(services):
    sheet = services.switch_gauge(PROCESS_TANK, "gauge-b2")
    services.revise_config({"high_limit_mm": 9500.0})
    with pytest.raises(StaleGenerationError):
        services.confirm_gauge(sheet.sheet_id)


def test_confirm_sheet_cannot_be_consumed_twice(services):
    sheet = services.switch_gauge(PROCESS_TANK, "gauge-b2")
    services.confirm_gauge(sheet.sheet_id)
    with pytest.raises(DuplicateSheetError):
        services.confirm_gauge(sheet.sheet_id)


def test_unconfirmed_gauge_cannot_be_used(services):
    from tankfarm.errors import GaugeNotConfirmedError

    services.switch_gauge(PROCESS_TANK, "gauge-b2")
    with pytest.raises(GaugeNotConfirmedError):
        services.levels.read_confirmed(PROCESS_TANK)


def test_persist_sheet_expires_before_pump_start(services, handover):
    sheet_id = handover()
    services.tick_clock(100)
    with pytest.raises(ExpiredSheetError):
        services.start_pump("pump-a", sheet_id)


def test_baseline_expires_before_pump_start(services, handover):
    sheet_id = handover()
    services.tick_clock(500)
    with pytest.raises(ExpiredBaselineError):
        services.start_pump("pump-a", sheet_id)


def test_snapshot_is_rejected_after_config_revision(services):
    snapshot = services.capture_snapshot()
    services.revise_config({"high_limit_mm": 9000.0})
    with pytest.raises(StaleGenerationError):
        services.validate_snapshot(snapshot.snapshot_id)


def test_snapshot_is_rejected_after_clock_tick(services):
    snapshot = services.capture_snapshot()
    services.tick_clock(200)
    with pytest.raises(ExpiredSnapshotError):
        services.validate_snapshot(snapshot.snapshot_id)


def test_validated_baseline_expires_after_clock_tick(services):
    services.tick_clock(500)
    with pytest.raises(ExpiredBaselineError):
        services.validate_baseline(PROCESS_TANK)


def test_recalibration_refreshes_baseline_generation(services):
    before = services.validate_baseline(PROCESS_TANK)
    services.recalibrate(PROCESS_TANK, 150.0)
    after = services.validate_baseline(PROCESS_TANK)
    assert after.generation > before.generation
    assert services.levels.state(PROCESS_TANK).baseline == pytest.approx(3050.0)
