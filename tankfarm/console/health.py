"""Health payload of the control service."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - typing only
    from tankfarm.console.wiring import Services


def health_payload(services: "Services") -> dict[str, Any]:
    replay = services.last_replay
    return {
        "status": "ok",
        "service": "control",
        "watermark": services.commits.watermark(),
        "head": services.stream.head(),
        "stage": services.machine.stage(),
        "config_generation": services.revisions.active().generation,
        "active_latches": list(services.engine.active_latches()),
        "id_counters": services.ids.counters(),
        "replay": None
        if replay is None
        else {
            "applied": replay.applied_count(),
            "skipped": replay.skipped_count(),
            "from_watermark": replay.from_watermark,
            "to_watermark": replay.to_watermark,
        },
        "data_dir": str(services.repository.layout.root),
    }
