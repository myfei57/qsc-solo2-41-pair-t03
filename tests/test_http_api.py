"""HTTP surface: health, commands, rejections and read models."""

from __future__ import annotations

from tankfarm.domain import (
    POSITION_CLOSED,
    PUMPS,
    VALVES,
    VALVE_VENT,
)
from tankfarm.event import topics
from tankfarm.sequence.stages import STAGE_IDLE, STAGE_VALVES_PERSISTED


def test_health_endpoint_reports_ok(client):
    status, body = client.get("/healthz")
    assert status == 200
    assert body["status"] == "ok"
    assert body["stage"] == STAGE_IDLE
    assert body["watermark"] == 0


def test_unknown_route_returns_404(client):
    status, body = client.get("/api/does-not-exist")
    assert status == 404
    assert body["code"] == "route_not_found"


def test_state_endpoint_lists_all_equipment(client):
    status, body = client.get("/api/state")
    assert status == 200
    assert len(body["valves"]) == len(VALVES)
    assert len(body["pumps"]) == len(PUMPS)
    assert body["sequence"]["stage"] == STAGE_IDLE
    assert body["journal"]["watermark"] == 0


def test_persist_endpoint_returns_confirmation_sheet(client):
    status, body = client.post("/api/valve/persist")
    assert status == 200
    assert body["sheet"]["state"] == "open"
    assert body["stage"] == STAGE_VALVES_PERSISTED


def test_pump_start_out_of_order_returns_conflict(client):
    client.post("/api/valve/persist")
    status, body = client.post(
        "/api/pump/start", {"pump_id": "pump-a", "sheet_id": "sheet-000001"}
    )
    assert status == 409
    assert body["code"] == "out_of_order"


def test_pump_start_happy_path(client):
    client.post("/api/valve/persist")
    client.post("/api/tank/change")
    _, body = client.post("/api/valve/persist")
    sheet_id = body["sheet"]["sheet_id"]
    status, body = client.post(
        "/api/pump/start", {"pump_id": "pump-a", "sheet_id": sheet_id}
    )
    assert status == 200
    assert body["pump_id"] == "pump-a"


def test_confirm_sheet_expiry_returns_conflict(client):
    _, body = client.post("/api/level/switch", {"gauge_id": "gauge-b2"})
    sheet_id = body["sheet"]["sheet_id"]
    client.post("/api/clock/tick", {"steps": 100})
    status, body = client.post("/api/level/confirm", {"sheet_id": sheet_id})
    assert status == 409
    assert body["code"] == "expired_sheet"


def test_config_revision_invalidates_pending_sheet(client):
    _, body = client.post("/api/level/switch", {"gauge_id": "gauge-b2"})
    sheet_id = body["sheet"]["sheet_id"]
    client.post("/api/config/revise", {"high_limit_mm": 9500.0})
    status, body = client.post("/api/level/confirm", {"sheet_id": sheet_id})
    assert status == 409
    assert body["code"] == "stale_generation"


def test_duplicate_confirmation_sheet_returns_conflict(client):
    _, body = client.post("/api/level/switch", {"gauge_id": "gauge-b2"})
    sheet_id = body["sheet"]["sheet_id"]
    assert client.post("/api/level/confirm", {"sheet_id": sheet_id})[0] == 200
    status, body = client.post("/api/level/confirm", {"sheet_id": sheet_id})
    assert status == 409
    assert body["code"] == "duplicate_sheet"


def test_duplicate_batch_returns_conflict(client):
    assert client.post("/api/batch", {"batch_id": "b-1"})[0] == 200
    status, body = client.post("/api/batch", {"batch_id": "b-1"})
    assert status == 409
    assert body["code"] == "duplicate_batch"


def test_rollback_endpoint_hides_record_from_state(client):
    client.post("/api/valve/open", {"valve_id": VALVE_VENT})
    _, records = client.get("/api/records", subject=VALVE_VENT)
    seq = records["records"][-1]["seq"]
    status, _ = client.post(
        "/api/journal/rollback", {"seq": seq, "reason": "wrong valve"}
    )
    assert status == 200
    _, state = client.get("/api/state")
    vent = [item for item in state["valves"] if item["valve_id"] == VALVE_VENT][0]
    assert vent["position"] == POSITION_CLOSED
    assert state["journal"]["tombstones"] == [seq]


def test_records_endpoint_filters_by_kind(client):
    client.post("/api/valve/persist")
    status, body = client.get("/api/records", kind=topics.VALVE_PERSISTED)
    assert status == 200
    assert body["count"] == 1


def test_audit_endpoints_return_entries_and_summary(client):
    client.post("/api/valve/persist")
    status, body = client.get("/api/audit", limit=5)
    assert status == 200
    assert body["count"] >= 1
    status, summary = client.get("/api/audit/summary")
    assert status == 200
    assert summary["total"] >= 1


def test_history_endpoint_compares_current_against_history(client):
    client.post("/api/valve/persist")
    _, state = client.get("/api/state")
    watermark = state["journal"]["watermark"]
    client.post("/api/tank/change")
    status, body = client.get("/api/history", watermark=watermark)
    assert status == 200
    assert body["state"]["stage"] == STAGE_VALVES_PERSISTED
    assert body["differences"]["stage"]["same"] is False


def test_snapshot_validation_returns_conflict_after_revision(client):
    _, body = client.post("/api/journal/snapshot")
    snapshot_id = body["snapshot_id"]
    client.post("/api/config/revise", {"high_limit_mm": 9100.0})
    status, body = client.post(
        "/api/journal/snapshot/validate", {"snapshot_id": snapshot_id}
    )
    assert status == 409
    assert body["code"] == "stale_generation"


def test_interlock_evaluate_reports_over_limit(client):
    client.post("/api/inlet/fill", {"amount": 6000.0})
    status, body = client.post("/api/interlock/evaluate", {})
    assert status == 200
    assert body["report"]["overfilled"] is True
    assert "overfill" in body["active"]


def test_malformed_json_body_returns_400(client):
    status, body = client.raw("/api/valve/persist", b"{not json")
    assert status == 400
    assert body["code"] == "bad_request"


def test_missing_required_field_returns_400(client):
    status, body = client.post("/api/pump/setpoint", {"pump_id": "pump-a"})
    assert status == 400
    assert body["code"] == "bad_request"


def test_baseline_endpoint_exposes_generation(client):
    status, body = client.get("/api/level/baseline")
    assert status == 200
    assert body["generation"] == 0

