"""Rejection catalog shared by every control service."""

from __future__ import annotations

from typing import Any


class ControlError(Exception):
    """Base class for a request that the control plane refuses to serve."""

    code = "control_error"

    def __init__(self, message: str, **details: Any) -> None:
        super().__init__(message)
        self.message = message
        self.details: dict[str, Any] = dict(details)

    def as_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"error": self.message, "code": self.code}
        payload.update(self.details)
        return payload


class UnknownTankError(ControlError):
    code = "unknown_tank"

    def __init__(self, tank_id: str) -> None:
        super().__init__(f"unknown tank: {tank_id}", tank_id=tank_id)


class UnknownValveError(ControlError):
    code = "unknown_valve"

    def __init__(self, valve_id: str) -> None:
        super().__init__(f"unknown valve: {valve_id}", valve_id=valve_id)


class UnknownPumpError(ControlError):
    code = "unknown_pump"

    def __init__(self, pump_id: str) -> None:
        super().__init__(f"unknown pump: {pump_id}", pump_id=pump_id)


class NotPersistedError(ControlError):
    code = "not_persisted"

    def __init__(self, subject: str) -> None:
        super().__init__(f"{subject} has no durable write", subject=subject)


class OutOfOrderError(ControlError):
    code = "out_of_order"

    def __init__(self, stage: str, target: str) -> None:
        super().__init__(
            f"stage {stage} may not jump to {target}", stage=stage, target=target
        )


class StageAlreadyReachedError(ControlError):
    code = "stage_already_reached"

    def __init__(self, stage: str) -> None:
        super().__init__(f"stage {stage} is already reached", stage=stage)


class GateBlockedError(ControlError):
    code = "gate_blocked"

    def __init__(self, gate: str) -> None:
        super().__init__(f"gate is not satisfied: {gate}", gate=gate)


class WatermarkRegressionError(ControlError):
    code = "watermark_regression"

    def __init__(self, current: int, requested: int) -> None:
        super().__init__(
            f"watermark {requested} is behind committed {current}",
            current=current,
            requested=requested,
        )


class RecordNotFoundError(ControlError):
    code = "record_not_found"

    def __init__(self, seq: int) -> None:
        super().__init__(f"record {seq} is not in the stream", seq=seq)


class UncommittedRecordError(ControlError):
    code = "uncommitted_record"

    def __init__(self, seq: int) -> None:
        super().__init__(f"record {seq} is not committed", seq=seq)


class DuplicateTombstoneError(ControlError):
    code = "duplicate_tombstone"

    def __init__(self, seq: int) -> None:
        super().__init__(f"record {seq} is already rolled back", seq=seq)


class RollbackTargetError(ControlError):
    code = "rollback_target"

    def __init__(self, seq: int) -> None:
        super().__init__(f"record {seq} is itself a tombstone", seq=seq)


class StaleGenerationError(ControlError):
    code = "stale_generation"

    def __init__(self, scope: str, key: str, current: int, carried: int) -> None:
        super().__init__(
            f"generation {carried} for {scope}/{key} is behind {current}",
            scope=scope,
            key=key,
            current=current,
            carried=carried,
        )


class UnknownGenerationError(ControlError):
    code = "unknown_generation"

    def __init__(self, scope: str, key: str, current: int, carried: int) -> None:
        super().__init__(
            f"generation {carried} for {scope}/{key} is ahead of {current}",
            scope=scope,
            key=key,
            current=current,
            carried=carried,
        )


class SheetNotFoundError(ControlError):
    code = "sheet_not_found"

    def __init__(self, sheet_id: str) -> None:
        super().__init__(f"confirmation sheet {sheet_id} is unknown", sheet_id=sheet_id)


class ExpiredSheetError(ControlError):
    code = "expired_sheet"

    def __init__(self, sheet_id: str, age: int, max_age: int) -> None:
        super().__init__(
            f"confirmation sheet {sheet_id} expired after {age} ticks",
            sheet_id=sheet_id,
            age=age,
            max_age=max_age,
        )


class DuplicateSheetError(ControlError):
    code = "duplicate_sheet"

    def __init__(self, sheet_id: str) -> None:
        super().__init__(
            f"confirmation sheet {sheet_id} was already consumed", sheet_id=sheet_id
        )


class BaselineNotFoundError(ControlError):
    code = "baseline_not_found"

    def __init__(self, tank_id: str) -> None:
        super().__init__(f"baseline for {tank_id} is unknown", tank_id=tank_id)


class ExpiredBaselineError(ControlError):
    code = "expired_baseline"

    def __init__(self, tank_id: str, age: int, max_age: int) -> None:
        super().__init__(
            f"baseline for {tank_id} expired after {age} ticks",
            tank_id=tank_id,
            age=age,
            max_age=max_age,
        )


class SnapshotNotFoundError(ControlError):
    code = "snapshot_not_found"

    def __init__(self, snapshot_id: str) -> None:
        super().__init__(f"snapshot {snapshot_id} is unknown", snapshot_id=snapshot_id)


class ExpiredSnapshotError(ControlError):
    code = "expired_snapshot"

    def __init__(self, snapshot_id: str, age: int, max_age: int) -> None:
        super().__init__(
            f"snapshot {snapshot_id} expired after {age} ticks",
            snapshot_id=snapshot_id,
            age=age,
            max_age=max_age,
        )


class DuplicateBatchError(ControlError):
    code = "duplicate_batch"

    def __init__(self, batch_id: str, tank_id: str) -> None:
        super().__init__(
            f"batch {batch_id} is already registered", batch_id=batch_id, tank_id=tank_id
        )


class BatchNotFoundError(ControlError):
    code = "batch_not_found"

    def __init__(self, batch_id: str) -> None:
        super().__init__(f"batch {batch_id} is unknown", batch_id=batch_id)


class LatchActiveError(ControlError):
    code = "latch_active"

    def __init__(self, latch: str) -> None:
        super().__init__(f"interlock latch {latch} is active", latch=latch)


class InertNotConfirmedError(ControlError):
    code = "inert_not_confirmed"

    def __init__(self, tank_id: str) -> None:
        super().__init__(
            f"blanket pressure for {tank_id} is not confirmed", tank_id=tank_id
        )


class GaugeNotConfirmedError(ControlError):
    code = "gauge_not_confirmed"

    def __init__(self, tank_id: str) -> None:
        super().__init__(f"level gauge for {tank_id} is not confirmed", tank_id=tank_id)


class LevelTooHighError(ControlError):
    code = "level_too_high"

    def __init__(self, tank_id: str, reading: float, limit: float) -> None:
        super().__init__(
            f"level {reading} of {tank_id} is above {limit}",
            tank_id=tank_id,
            reading=reading,
            limit=limit,
        )


class AlreadyRunningError(ControlError):
    code = "already_running"

    def __init__(self, pump_id: str) -> None:
        super().__init__(f"pump {pump_id} is already running", pump_id=pump_id)


class NotRunningError(ControlError):
    code = "not_running"

    def __init__(self, pump_id: str) -> None:
        super().__init__(f"pump {pump_id} is not running", pump_id=pump_id)


class NonPositiveAmountError(ControlError):
    code = "non_positive_amount"

    def __init__(self, amount: float) -> None:
        super().__init__(f"amount {amount} must be positive", amount=amount)


class NegativeSetpointError(ControlError):
    code = "negative_setpoint"

    def __init__(self, setpoint: float) -> None:
        super().__init__(f"setpoint {setpoint} must not be negative", setpoint=setpoint)


class ConfigRejectedError(ControlError):
    code = "config_rejected"

    def __init__(self, detail: str) -> None:
        super().__init__(f"configuration rejected: {detail}", detail=detail)


class StoreError(ControlError):
    code = "store_error"

    def __init__(self, path: str, detail: str) -> None:
        super().__init__(f"store {path} failed: {detail}", path=path, detail=detail)
