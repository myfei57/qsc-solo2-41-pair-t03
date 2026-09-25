"""Console state assembly."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tankfarm.domain import PROCESS_TANK

if TYPE_CHECKING:  # pragma: no cover - typing only
    from tankfarm.console.wiring import Services


def build_state(services: "Services") -> dict[str, Any]:
    revision = services.revisions.active()
    return {
        "config": revision.as_payload(),
        "limits": {
            "level": services.limits.as_payload(),
            "blanket": services.blanket.as_payload(),
        },
        "valves": [valve.as_payload() for valve in services.valves.all()],
        "header": {
            "header_id": services.header.header_id,
            "history": [
                {"ts": ts, "setpoint": value} for ts, value in services.header.history()
            ],
            **services.arbiter.as_payload(),
        },
        "pumps": [pump.as_payload() for pump in services.pumps.all()],
        "tanks": [summary.as_payload() for summary in services.tank_summaries()],
        "levels": [state.as_payload() for state in services.levels.states()],
        "inert": [state.as_payload() for state in services.inert.states()],
        "inlet": services.inlet.state().as_payload(),
        "esd": {"valve_closed": services.esd_valve.is_closed()},
        "latches": services.engine.as_payload(),
        "sequence": {
            "stage": services.machine.stage(),
            "facts": services.machine.facts(),
            "history": list(services.machine.history()),
        },
        "interlock": services.interlock_report(PROCESS_TANK).as_payload(),
        "journal": {
            "head": services.stream.head(),
            "watermark": services.commits.watermark(),
            "committed": len(services.commits.committed()),
            "pending": len(services.commits.pending()),
            "visible": len(services.visible_records()),
            "tombstones": list(services.tombstones.targets()),
        },
        "sheets": [sheet.as_payload() for sheet in services.sheets.open_sheets()],
        "latest_snapshot": _snapshot_payload(services),
        "baselines": services.baselines.values(),
        "batches": services.batches.count(),
        "recent_updates": list(services.recent_updates(8)),
        "current": services.current_view().as_payload(),
    }


def _snapshot_payload(services: "Services") -> dict[str, Any] | None:
    snapshot = services.snapshots.latest()
    if snapshot is None:
        return None
    return {"snapshot_id": snapshot.snapshot_id, "watermark": snapshot.watermark}
