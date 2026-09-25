"""Request handlers of the console API."""

from __future__ import annotations

from typing import Any, Mapping

from tankfarm.console.health import health_payload
from tankfarm.console.state import build_state
from tankfarm.console.wiring import Services
from tankfarm.domain import PROCESS_TANK
from tankfarm.judgement.filters import RecordFilter


def _int(source: Mapping[str, Any], key: str, default: int) -> int:
    raw = source.get(key)
    if raw is None or raw == "":
        return default
    return int(raw)


def _float(source: Mapping[str, Any], key: str) -> float:
    raw = source.get(key)
    if raw is None or raw == "":
        raise ValueError(f"missing {key}")
    return float(raw)


def _text(source: Mapping[str, Any], key: str, default: str = "") -> str:
    raw = source.get(key)
    if raw is None:
        return default
    return str(raw)


def _record_filter(source: Mapping[str, Any]) -> RecordFilter:
    raw_kinds = _text(source, "kind") or _text(source, "kinds")
    kinds = tuple(part for part in raw_kinds.split(",") if part)
    subject = _text(source, "subject")
    return RecordFilter(
        kinds=kinds,
        subject=subject or None,
        min_seq=_int(source, "min_seq", 0),
        max_seq=_int(source, "max_seq", 0),
        limit=_int(source, "limit", 0),
    )


class Handlers:
    """One method per route; every method returns a JSON ready mapping."""

    def __init__(self, services: Services) -> None:
        self.services = services

    # ------------------------------------------------------------- reads

    def health(self, payload: Mapping[str, Any], query: Mapping[str, Any]) -> dict[str, Any]:
        return health_payload(self.services)

    def state(self, payload: Mapping[str, Any], query: Mapping[str, Any]) -> dict[str, Any]:
        return build_state(self.services)

    def config(self, payload: Mapping[str, Any], query: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "active": self.services.revisions.active().as_payload(),
            "history": [item.as_payload() for item in self.services.revisions.history()],
        }

    def clock(self, payload: Mapping[str, Any], query: Mapping[str, Any]) -> dict[str, Any]:
        return {"now": self.services.clock.now()}

    def records(self, payload: Mapping[str, Any], query: Mapping[str, Any]) -> dict[str, Any]:
        record_filter = _record_filter(query)
        selected = self.services.select_records(record_filter)
        return {
            "count": len(selected),
            "filter": record_filter.as_payload(),
            "records": [record.as_payload() for record in selected],
        }

    def history(self, payload: Mapping[str, Any], query: Mapping[str, Any]) -> dict[str, Any]:
        requested = _int(query, "watermark", 0)
        current = self.services.current_view()
        report = self.services.history(requested if requested > 0 else None)
        report["current"] = current.as_payload()
        report["differences"] = current.differences(report["state"])
        return report

    def audit(self, payload: Mapping[str, Any], query: Mapping[str, Any]) -> dict[str, Any]:
        record_filter = _record_filter(query)
        selected = self.services.audit.select(record_filter)
        return {
            "count": len(selected),
            "filter": record_filter.as_payload(),
            "kinds": list(self.services.audit.kinds()),
            "subjects": list(self.services.audit.subjects()),
            "entries": [entry.as_payload() for entry in selected],
        }

    def audit_summary(
        self, payload: Mapping[str, Any], query: Mapping[str, Any]
    ) -> dict[str, Any]:
        return self.services.audit_summary().as_payload()

    def baseline(self, payload: Mapping[str, Any], query: Mapping[str, Any]) -> dict[str, Any]:
        tank_id = _text(query, "tank_id", PROCESS_TANK)
        return self.services.validate_baseline(tank_id).as_payload()

    def batch_get(self, payload: Mapping[str, Any], query: Mapping[str, Any]) -> dict[str, Any]:
        registration = self.services.get_batch(_text(query, "batch_id"))
        siblings = self.services.batches.for_tank(registration.tank_id)
        return {
            "batch": registration.as_payload(),
            "tank_batches": [item.batch_id for item in siblings],
        }

    def interlock_evaluate(
        self, payload: Mapping[str, Any], query: Mapping[str, Any]
    ) -> dict[str, Any]:
        tank_id = _text(payload, "tank_id", PROCESS_TANK)
        changed = self.services.evaluate_interlocks()
        return {
            "report": self.services.interlock_report(tank_id).as_payload(),
            "changed": [item.as_payload() for item in changed],
            "active": list(self.services.engine.active_latches()),
        }

    # ------------------------------------------------------------- writes

    def valve_persist(
        self, payload: Mapping[str, Any], query: Mapping[str, Any]
    ) -> dict[str, Any]:
        sheet = self.services.persist_valves()
        return {"sheet": sheet.as_payload(), "stage": self.services.machine.stage()}

    def valve_open(self, payload: Mapping[str, Any], query: Mapping[str, Any]) -> dict[str, Any]:
        return self.services.open_valve(_text(payload, "valve_id")).as_payload()

    def valve_close(self, payload: Mapping[str, Any], query: Mapping[str, Any]) -> dict[str, Any]:
        return self.services.close_valve(_text(payload, "valve_id")).as_payload()

    def pump_start(self, payload: Mapping[str, Any], query: Mapping[str, Any]) -> dict[str, Any]:
        return self.services.start_pump(
            _text(payload, "pump_id"), _text(payload, "sheet_id")
        )

    def pump_stop(self, payload: Mapping[str, Any], query: Mapping[str, Any]) -> dict[str, Any]:
        return self.services.stop_pump(_text(payload, "pump_id")).as_payload()

    def pump_setpoint(
        self, payload: Mapping[str, Any], query: Mapping[str, Any]
    ) -> dict[str, Any]:
        pump = self.services.set_setpoint(
            _text(payload, "pump_id"), _float(payload, "setpoint")
        )
        return pump.as_payload()

    def pump_ramp(self, payload: Mapping[str, Any], query: Mapping[str, Any]) -> dict[str, Any]:
        return self.services.ramp_pump(
            _text(payload, "pump_id"), _float(payload, "setpoint")
        )

    def tank_change(self, payload: Mapping[str, Any], query: Mapping[str, Any]) -> dict[str, Any]:
        return self.services.change_tank()

    def tank_retry(self, payload: Mapping[str, Any], query: Mapping[str, Any]) -> dict[str, Any]:
        return self.services.retry_change_tank()

    def inlet_open(self, payload: Mapping[str, Any], query: Mapping[str, Any]) -> dict[str, Any]:
        return self.services.open_inlet()

    def inlet_fill(self, payload: Mapping[str, Any], query: Mapping[str, Any]) -> dict[str, Any]:
        return self.services.fill_inlet(_float(payload, "amount"))

    def inlet_release(
        self, payload: Mapping[str, Any], query: Mapping[str, Any]
    ) -> dict[str, Any]:
        return self.services.release_inlet()

    def esd_trip(self, payload: Mapping[str, Any], query: Mapping[str, Any]) -> dict[str, Any]:
        return self.services.trip_esd().as_payload()

    def esd_retrip(self, payload: Mapping[str, Any], query: Mapping[str, Any]) -> dict[str, Any]:
        return self.services.retrip_esd().as_payload()

    def esd_test(self, payload: Mapping[str, Any], query: Mapping[str, Any]) -> dict[str, Any]:
        return self.services.test_esd()

    def esd_reset(self, payload: Mapping[str, Any], query: Mapping[str, Any]) -> dict[str, Any]:
        return self.services.reset_esd()

    def level_switch(self, payload: Mapping[str, Any], query: Mapping[str, Any]) -> dict[str, Any]:
        sheet = self.services.switch_gauge(
            _text(payload, "tank_id", PROCESS_TANK), _text(payload, "gauge_id")
        )
        return {"sheet": sheet.as_payload(), "writable": False}

    def level_confirm(self, payload: Mapping[str, Any], query: Mapping[str, Any]) -> dict[str, Any]:
        return self.services.confirm_gauge(_text(payload, "sheet_id"))

    def level_recalibrate(
        self, payload: Mapping[str, Any], query: Mapping[str, Any]
    ) -> dict[str, Any]:
        return self.services.recalibrate(
            _text(payload, "tank_id", PROCESS_TANK), _float(payload, "offset")
        )

    def level_draw(self, payload: Mapping[str, Any], query: Mapping[str, Any]) -> dict[str, Any]:
        state = self.services.draw_level(
            _text(payload, "tank_id", PROCESS_TANK), _float(payload, "amount")
        )
        return state.as_payload()

    def inert_pressure(
        self, payload: Mapping[str, Any], query: Mapping[str, Any]
    ) -> dict[str, Any]:
        return self.services.set_inert_pressure(
            _text(payload, "tank_id", PROCESS_TANK), _float(payload, "pressure")
        )

    def inert_alarm(self, payload: Mapping[str, Any], query: Mapping[str, Any]) -> dict[str, Any]:
        return self.services.raise_inert_alarm(
            _text(payload, "tank_id", PROCESS_TANK)
        )

    def inert_clear(self, payload: Mapping[str, Any], query: Mapping[str, Any]) -> dict[str, Any]:
        return self.services.clear_inert_alarm(
            _text(payload, "tank_id", PROCESS_TANK)
        )

    def config_revise(
        self, payload: Mapping[str, Any], query: Mapping[str, Any]
    ) -> dict[str, Any]:
        return self.services.revise_config({key: value for key, value in payload.items()})

    def clock_tick(self, payload: Mapping[str, Any], query: Mapping[str, Any]) -> dict[str, Any]:
        return {"now": self.services.tick_clock(_int(payload, "steps", 1))}

    def journal_commit(
        self, payload: Mapping[str, Any], query: Mapping[str, Any]
    ) -> dict[str, Any]:
        raw = payload.get("seq")
        seq = None if raw is None or raw == "" else int(raw)
        return {
            "watermark": self.services.commit(seq),
            "head": self.services.stream.head(),
        }

    def journal_rollback(
        self, payload: Mapping[str, Any], query: Mapping[str, Any]
    ) -> dict[str, Any]:
        record = self.services.rollback(
            _int(payload, "seq", 0), _text(payload, "reason", "operator rollback")
        )
        return {
            "tombstone": record.as_payload(),
            "watermark": self.services.commits.watermark(),
        }

    def journal_snapshot(
        self, payload: Mapping[str, Any], query: Mapping[str, Any]
    ) -> dict[str, Any]:
        return self.services.capture_snapshot().as_payload()

    def journal_snapshot_validate(
        self, payload: Mapping[str, Any], query: Mapping[str, Any]
    ) -> dict[str, Any]:
        snapshot = self.services.validate_snapshot(_text(payload, "snapshot_id"))
        return {"valid": True, "snapshot": snapshot.as_payload()}

    def batch_register(
        self, payload: Mapping[str, Any], query: Mapping[str, Any]
    ) -> dict[str, Any]:
        registration = self.services.register_batch(
            _text(payload, "batch_id"), _text(payload, "tank_id") or None
        )
        return registration.as_payload()
