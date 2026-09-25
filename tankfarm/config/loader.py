"""Settings overlay and revision bookkeeping."""

from __future__ import annotations

from typing import Any, Mapping

from tankfarm.config.schema import DEFAULT_SETTINGS, ConfigRevision, ControlSettings
from tankfarm.errors import ConfigRejectedError
from tankfarm.versioning.generation import CONFIG_KEY, SCOPE_CONFIG, GenerationRegistry

_FLOAT_KEYS = {
    "high_limit_mm": "high_limit_mm",
    "inert_low_kpa": "inert_low_kpa",
    "inert_high_kpa": "inert_high_kpa",
}
_INT_KEYS = {
    "sheet_max_age": "sheet_max_age",
    "baseline_max_age": "baseline_max_age",
    "snapshot_max_age": "snapshot_max_age",
}


def settings_from_payload(
    payload: Mapping[str, Any], base: ControlSettings = DEFAULT_SETTINGS
) -> ControlSettings:
    """Overlay known keys on ``base``; unknown keys and bad types are refused."""

    values: dict[str, Any] = {}
    for key, value in payload.items():
        if key in _FLOAT_KEYS:
            try:
                values[_FLOAT_KEYS[key]] = float(value)
            except (TypeError, ValueError) as exc:
                raise ConfigRejectedError(f"{key} is not numeric") from exc
        elif key in _INT_KEYS:
            try:
                values[_INT_KEYS[key]] = int(value)
            except (TypeError, ValueError) as exc:
                raise ConfigRejectedError(f"{key} is not an integer") from exc
        else:
            raise ConfigRejectedError(f"unknown setting {key}")
    if values.get("inert_low_kpa", base.inert_low_kpa) >= values.get(
        "inert_high_kpa", base.inert_high_kpa
    ):
        raise ConfigRejectedError("blanket window low bound must be below high bound")
    if values.get("high_limit_mm", base.high_limit_mm) <= 0:
        raise ConfigRejectedError("high limit must be positive")
    merged = ControlSettings(
        addr=base.addr,
        data_dir=base.data_dir,
        high_limit_mm=values.get("high_limit_mm", base.high_limit_mm),
        inert_low_kpa=values.get("inert_low_kpa", base.inert_low_kpa),
        inert_high_kpa=values.get("inert_high_kpa", base.inert_high_kpa),
        sheet_max_age=values.get("sheet_max_age", base.sheet_max_age),
        baseline_max_age=values.get("baseline_max_age", base.baseline_max_age),
        snapshot_max_age=values.get("snapshot_max_age", base.snapshot_max_age),
    )
    return merged


def settings_from_state(payload: Mapping[str, Any]) -> ControlSettings:
    """Rebuilds a full settings object that was recovered from a checkpoint."""

    return ControlSettings(
        addr=str(payload.get("addr", DEFAULT_SETTINGS.addr)),
        data_dir=str(payload.get("data_dir", DEFAULT_SETTINGS.data_dir)),
        high_limit_mm=float(payload.get("high_limit_mm", DEFAULT_SETTINGS.high_limit_mm)),
        inert_low_kpa=float(payload.get("inert_low_kpa", DEFAULT_SETTINGS.inert_low_kpa)),
        inert_high_kpa=float(
            payload.get("inert_high_kpa", DEFAULT_SETTINGS.inert_high_kpa)
        ),
        sheet_max_age=int(payload.get("sheet_max_age", DEFAULT_SETTINGS.sheet_max_age)),
        baseline_max_age=int(
            payload.get("baseline_max_age", DEFAULT_SETTINGS.baseline_max_age)
        ),
        snapshot_max_age=int(
            payload.get("snapshot_max_age", DEFAULT_SETTINGS.snapshot_max_age)
        ),
    )


class ConfigRevisions:
    """Activates settings revisions; every activation bumps the generation."""

    def __init__(
        self, registry: GenerationRegistry, settings: ControlSettings, now: int
    ) -> None:
        self._registry = registry
        self._history: list[ConfigRevision] = []
        self._active = self.activate(settings, now)

    def activate(self, settings: ControlSettings, now: int) -> ConfigRevision:
        generation = self._registry.bump(SCOPE_CONFIG, CONFIG_KEY, now)
        revision = ConfigRevision(
            generation=generation.number, settings=settings, issued_at=int(now)
        )
        self._history.append(revision)
        self._active = revision
        return revision

    def active(self) -> ConfigRevision:
        return self._active

    def history(self) -> tuple[ConfigRevision, ...]:
        return tuple(self._history)

    def restore(self, revision: ConfigRevision) -> None:
        """Adopts a revision that was recovered from the record stream."""

        self._registry.restore(
            SCOPE_CONFIG, CONFIG_KEY, revision.generation, revision.issued_at
        )
        self._history.append(revision)
        self._active = revision
