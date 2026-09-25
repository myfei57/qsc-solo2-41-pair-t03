"""Level service: gauge confirmation, calibration and level movement."""

from __future__ import annotations

from tankfarm.clock import LogicalClock
from tankfarm.config.schema import ControlSettings
from tankfarm.domain import (
    TANK_BASELINE_SEED,
    TANK_GAUGE,
    TANK_LEVEL_SEED,
    TANK_OFFSET_SEED,
    TANKS,
)
from tankfarm.errors import (
    GaugeNotConfirmedError,
    NonPositiveAmountError,
    SheetNotFoundError,
    UnknownTankError,
)
from tankfarm.event import Event, EventBus
from tankfarm.event import topics
from tankfarm.journal.writer import JournalWriter
from tankfarm.judgement.limits import LevelLimits
from tankfarm.level.model import LevelState
from tankfarm.level.offset import BaselineRecorder
from tankfarm.level.update import UpdateLog, UpdateRecord
from tankfarm.versioning.baseline import Baseline, BaselineBook
from tankfarm.versioning.expiry import ExpiryPolicy
from tankfarm.versioning.generation import (
    CONFIG_KEY,
    SCOPE_CONFIG,
    SCOPE_GAUGE_CONFIRM,
    GenerationRegistry,
)
from tankfarm.versioning.sheet import ConfirmationSheet, SheetBook

UPDATE_LOG_CAPACITY = 120


class LevelService:
    """Owns every level state and refuses readings from unconfirmed gauges."""

    def __init__(
        self,
        journal: JournalWriter,
        bus: EventBus,
        clock: LogicalClock,
        generations: GenerationRegistry,
        sheets: SheetBook,
        baselines: BaselineBook,
        limits: LevelLimits,
        settings: ControlSettings,
    ) -> None:
        self._journal = journal
        self._bus = bus
        self._clock = clock
        self._generations = generations
        self._sheets = sheets
        self._limits = limits
        self._recorder = BaselineRecorder(
            baselines, generations, clock, ExpiryPolicy(settings.baseline_max_age)
        )
        self._sheet_policy = ExpiryPolicy(settings.sheet_max_age)
        self._updates = UpdateLog(UPDATE_LOG_CAPACITY)
        self._states: dict[str, LevelState] = {}
        self.seed()

    def seed(self) -> None:
        self._updates.clear()
        self._states = {}
        for tank_id in TANKS:
            self._states[tank_id] = LevelState(
                tank_id=tank_id,
                gauge_id=TANK_GAUGE[tank_id],
                reading=TANK_LEVEL_SEED[tank_id],
                baseline=TANK_BASELINE_SEED[tank_id],
                offset=TANK_OFFSET_SEED,
                confirmed=True,
            )
            self._recorder.seed(tank_id, TANK_BASELINE_SEED[tank_id])

    def tank_ids(self) -> tuple[str, ...]:
        return tuple(self._states)

    def state(self, tank_id: str) -> LevelState:
        state = self._states.get(tank_id)
        if state is None:
            raise UnknownTankError(tank_id)
        return state

    def states(self) -> tuple[LevelState, ...]:
        return tuple(self._states.values())

    def high_limit(self) -> float:
        return self._limits.high_limit()

    def read_raw(self, tank_id: str) -> float:
        return self.state(tank_id).reading

    def read_confirmed(self, tank_id: str) -> float:
        state = self.state(tank_id)
        if not state.confirmed:
            raise GaugeNotConfirmedError(tank_id)
        return state.reading

    def is_confirmed(self, tank_id: str) -> bool:
        state = self._states.get(tank_id)
        return bool(state is not None and state.confirmed)

    def gauge_of(self, tank_id: str) -> str:
        return self.state(tank_id).gauge_id

    def at_high(self, tank_id: str) -> bool:
        return self._limits.at_high(self.read_confirmed(tank_id))

    def switch_gauge(self, tank_id: str, gauge_id: str) -> ConfirmationSheet:
        state = self.state(tank_id)
        now = self._clock.now()
        state.gauge_id = gauge_id
        state.confirmed = False
        generation = self._generations.bump(SCOPE_GAUGE_CONFIRM, tank_id, now)
        state.generation = generation.number
        sheet = self._sheets.issue(
            SCOPE_GAUGE_CONFIRM,
            tank_id,
            generation.number,
            self._generations.current(SCOPE_CONFIG, CONFIG_KEY),
            now,
            self._sheet_policy,
        )
        state.pending_sheet = sheet.sheet_id
        payload = {
            "tank_id": tank_id,
            "gauge_id": gauge_id,
            "confirmed": False,
            "generation": generation.number,
        }
        self._journal.append(topics.LEVEL_GAUGE, payload)
        self._bus.publish(Event(topics.LEVEL_GAUGE, payload, now))
        return sheet

    def confirm_gauge(self, sheet_id: str) -> LevelState:
        consumed = self._sheets.consume(sheet_id, self._clock.now(), self._generations)
        state = self.state(consumed.key)
        if state.pending_sheet != sheet_id:
            raise SheetNotFoundError(sheet_id)
        state.confirmed = True
        state.pending_sheet = None
        payload = {
            "tank_id": state.tank_id,
            "gauge_id": state.gauge_id,
            "confirmed": True,
            "generation": consumed.generation,
        }
        self._journal.append(topics.LEVEL_GAUGE, payload)
        self._bus.publish(Event(topics.LEVEL_GAUGE, payload, self._clock.now()))
        return state

    def recalibrate(self, tank_id: str, offset: float) -> float:
        state = self.state(tank_id)
        state.offset = float(offset)
        state.baseline = state.reading - state.offset
        baseline = self._recorder.record(tank_id, state.baseline, state.offset)
        payload = {
            "tank_id": tank_id,
            "value": state.baseline,
            "offset": state.offset,
            "generation": baseline.generation,
        }
        self._journal.append(topics.LEVEL_BASELINE, payload)
        self._bus.publish(Event(topics.LEVEL_BASELINE, payload, self._clock.now()))
        recalibrated = {
            "tank_id": tank_id,
            "offset": state.offset,
            "baseline": state.baseline,
        }
        self._journal.append(topics.LEVEL_RECALIBRATED, recalibrated)
        self._bus.publish(
            Event(topics.LEVEL_RECALIBRATED, recalibrated, self._clock.now())
        )
        return state.baseline

    def validated_baseline(self, tank_id: str) -> Baseline:
        return self._recorder.validate(tank_id)

    def fill(self, tank_id: str, amount: float) -> LevelState:
        return self._move(tank_id, amount, "fill")

    def draw(self, tank_id: str, amount: float) -> LevelState:
        return self._move(tank_id, -amount, "draw")

    def recent_updates(self, limit: int) -> tuple[UpdateRecord, ...]:
        return self._updates.recent(limit)

    def apply_reading(self, tank_id: str, reading: float) -> None:
        state = self._states.get(tank_id)
        if state is not None:
            state.reading = float(reading)

    def apply_gauge(self, tank_id: str, gauge_id: str, confirmed: bool, generation: int) -> None:
        state = self._states.get(tank_id)
        if state is None:
            return
        state.gauge_id = gauge_id
        state.confirmed = confirmed
        state.generation = int(generation)
        if not confirmed:
            state.pending_sheet = None

    def apply_calibration(self, tank_id: str, baseline: float, offset: float) -> None:
        state = self._states.get(tank_id)
        if state is None:
            return
        state.baseline = float(baseline)
        state.offset = float(offset)

    def apply_offset(self, tank_id: str, offset: float) -> None:
        state = self._states.get(tank_id)
        if state is not None:
            state.offset = float(offset)

    def _move(self, tank_id: str, delta: float, kind: str) -> LevelState:
        if delta == 0 or (delta < 0 and kind == "fill") or (delta > 0 and kind == "draw"):
            raise NonPositiveAmountError(abs(delta))
        state = self.state(tank_id)
        state.reading = max(0.0, state.reading + delta)
        entry = self._updates.record(tank_id, kind, state.reading)
        payload = {
            "tank_id": tank_id,
            "reading": state.reading,
            "delta": delta,
            "kind": kind,
            "seq": entry.seq,
        }
        self._journal.append(topics.LEVEL_READING, payload)
        self._bus.publish(Event(topics.LEVEL_READING, payload, self._clock.now()))
        return state
