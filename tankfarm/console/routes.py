"""Route table and dispatcher."""

from __future__ import annotations

from typing import Any, Mapping

from tankfarm.console.handlers import Handlers

ROUTES: tuple[tuple[str, str, str], ...] = (
    ("GET", "/healthz", "health"),
    ("GET", "/api/state", "state"),
    ("GET", "/api/config", "config"),
    ("GET", "/api/clock", "clock"),
    ("GET", "/api/records", "records"),
    ("GET", "/api/history", "history"),
    ("GET", "/api/audit", "audit"),
    ("GET", "/api/audit/summary", "audit_summary"),
    ("GET", "/api/level/baseline", "baseline"),
    ("GET", "/api/batch", "batch_get"),
    ("POST", "/api/config/revise", "config_revise"),
    ("POST", "/api/clock/tick", "clock_tick"),
    ("POST", "/api/journal/commit", "journal_commit"),
    ("POST", "/api/journal/rollback", "journal_rollback"),
    ("POST", "/api/journal/snapshot", "journal_snapshot"),
    ("POST", "/api/journal/snapshot/validate", "journal_snapshot_validate"),
    ("POST", "/api/valve/persist", "valve_persist"),
    ("POST", "/api/valve/open", "valve_open"),
    ("POST", "/api/valve/close", "valve_close"),
    ("POST", "/api/pump/start", "pump_start"),
    ("POST", "/api/pump/stop", "pump_stop"),
    ("POST", "/api/pump/setpoint", "pump_setpoint"),
    ("POST", "/api/pump/ramp", "pump_ramp"),
    ("POST", "/api/tank/change", "tank_change"),
    ("POST", "/api/tank/retry", "tank_retry"),
    ("POST", "/api/inlet/open", "inlet_open"),
    ("POST", "/api/inlet/fill", "inlet_fill"),
    ("POST", "/api/inlet/release", "inlet_release"),
    ("POST", "/api/esd/trip", "esd_trip"),
    ("POST", "/api/esd/retrip", "esd_retrip"),
    ("POST", "/api/esd/test", "esd_test"),
    ("POST", "/api/esd/reset", "esd_reset"),
    ("POST", "/api/level/switch", "level_switch"),
    ("POST", "/api/level/confirm", "level_confirm"),
    ("POST", "/api/level/recalibrate", "level_recalibrate"),
    ("POST", "/api/level/draw", "level_draw"),
    ("POST", "/api/inert/pressure", "inert_pressure"),
    ("POST", "/api/inert/alarm", "inert_alarm"),
    ("POST", "/api/inert/clear", "inert_clear"),
    ("POST", "/api/batch", "batch_register"),
    ("POST", "/api/interlock/evaluate", "interlock_evaluate"),
)


class Router:
    """Maps a method and path to one handler method."""

    def __init__(self, handlers: Handlers) -> None:
        self._handlers = handlers
        self._table = {(method, path): name for method, path, name in ROUTES}

    def dispatch(
        self,
        method: str,
        path: str,
        payload: Mapping[str, Any],
        query: Mapping[str, Any],
    ) -> tuple[int, dict[str, Any]]:
        name = self._table.get((method, path))
        if name is None:
            return 404, {
                "error": f"no route for {method} {path}",
                "code": "route_not_found",
            }
        result = getattr(self._handlers, name)(payload, query)
        return 200, result
