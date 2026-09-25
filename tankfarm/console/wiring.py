"""Service graph of the control plane."""

from __future__ import annotations

from tankfarm.audit.query import AuditQuery
from tankfarm.audit.record import AuditLog
from tankfarm.audit.summary import AuditSummary, summarize
from tankfarm.clock import LogicalClock
from tankfarm.config.loader import ConfigRevisions, settings_from_payload, settings_from_state
from tankfarm.config.schema import DEFAULT_SETTINGS, ConfigRevision, ControlSettings
from tankfarm.domain import (
    DESTINATION_TANK,
    HEADER_ID,
    PROCESS_TANK,
    SOURCE_TANK,
    VALVE_INLET,
)
from tankfarm.errors import (
    GateBlockedError,
    GaugeNotConfirmedError,
    StageAlreadyReachedError,
)
from tankfarm.esd.test import TestController
from tankfarm.esd.trip import TripController, TripResult
from tankfarm.esd.valve import EsdValve
from tankfarm.event import EventBus
from tankfarm.event import topics
from tankfarm.ids import IdFactory
from tankfarm.inert.latch import VentLatch
from tankfarm.inert.service import InertService
from tankfarm.inlet.controller import InletController
from tankfarm.inlet.fill import FillingController
from tankfarm.interlock.engine import InterlockEngine
from tankfarm.interlock.latch import LatchState
from tankfarm.interlock.rules import (
    BLANKET_LATCH,
    OVERFILL_LATCH,
    ControlContext,
)
from tankfarm.journal import (
    TOMBSTONE_KIND,
    CommitController,
    JournalCheckpoint,
    JournalWriter,
    Record,
    RecordStream,
    ReplayResult,
    RollbackService,
    TombstoneIndex,
    Watermark,
    replay,
)
from tankfarm.judgement.batch import BatchRegistration, BatchRegistry
from tankfarm.judgement.current import CurrentView
from tankfarm.judgement.filters import RecordFilter
from tankfarm.judgement.history import StateProjection
from tankfarm.judgement.limits import BlanketLimits, LevelLimits
from tankfarm.level.model import LevelState
from tankfarm.level.service import LevelService
from tankfarm.pump.arbiter import HeaderArbiter
from tankfarm.pump.gate import PumpStartGate
from tankfarm.pump.model import Pump
from tankfarm.pump.registry import PumpRegistry
from tankfarm.pump.setpoint import SetpointController
from tankfarm.pump.start import start_pump
from tankfarm.pump.stop import stop_all_pumps, stop_pump
from tankfarm.sequence.machine import SequenceMachine
from tankfarm.sequence.stages import (
    FACT_NEW_TANK_OPEN,
    FACT_OLD_TANK_CLOSED,
    FACT_VALVE_PERSISTED,
    STAGE_NEW_TANK_OPEN,
    STAGE_OLD_TANK_CLOSED,
    STAGE_PUMP_RUNNING,
    STAGE_VALVES_PERSISTED,
    STAGE_IDLE,
)
from tankfarm.store.repository import Repository
from tankfarm.tank.capacity import CapacityEstimator
from tankfarm.tank.handoff import Handoff
from tankfarm.tank.interlock import InterlockReport, TransferInterlock
from tankfarm.tank.registry import TankRegistry
from tankfarm.tank.summary import TankSummary, build_summary
from tankfarm.valve.header import Header
from tankfarm.valve.model import Valve
from tankfarm.valve.persist import ValvePersister
from tankfarm.valve.registry import ValveRegistry
from tankfarm.valve.switch import ValveSwitcher
from tankfarm.versioning import ExpiryPolicy
from tankfarm.versioning.baseline import Baseline, BaselineBook
from tankfarm.versioning.generation import (
    SCOPE_SNAPSHOT,
    SNAPSHOT_KEY,
    GenerationRegistry,
)
from tankfarm.versioning.sheet import ConfirmationSheet, SheetBook
from tankfarm.versioning.snapshot import SnapshotBook, VersionedSnapshot

class Services:
    """Facade used by the HTTP layer and by the tests."""

    def __init__(
        self,
        settings: ControlSettings = DEFAULT_SETTINGS,
        repository: Repository | None = None,
    ) -> None:
        self._base_settings = settings
        self.settings = settings
        self.clock = LogicalClock()
        self.ids = IdFactory()
        self.repository = repository or Repository(settings.data_dir)
        self.generations = GenerationRegistry()
        self.revisions = ConfigRevisions(self.generations, settings, self.clock.now())
        self.limits = LevelLimits(settings.high_limit_mm)
        self.blanket = BlanketLimits(settings.inert_low_kpa, settings.inert_high_kpa)
        self.stream = RecordStream(self.ids)
        self.watermark = Watermark()
        self.commits = CommitController(self.stream, self.watermark)
        self.tombstones = TombstoneIndex()
        self.journal = JournalWriter(self.stream, self.repository, self.clock)
        self.rollbacks = RollbackService(self.journal, self.commits, self.tombstones)
        self.bus = EventBus()
        self.sheets = SheetBook(self.ids)
        self.baselines = BaselineBook()
        self.snapshots = SnapshotBook(self.ids)
        self.projection = StateProjection()
        self.journal.add_observer(self._observe)
        self.valves = ValveRegistry.seeded()
        self.switcher = ValveSwitcher(self.valves, self.journal, self.bus, self.clock)
        self.persister = ValvePersister(
            self.valves,
            self.journal,
            self.bus,
            self.clock,
            self.generations,
            self.sheets,
            ExpiryPolicy(settings.sheet_max_age),
        )
        self.header = Header(HEADER_ID, self.journal, self.bus, self.clock)
        self.arbiter = HeaderArbiter(self.header)
        self.pumps = PumpRegistry.seeded()
        self.setpoints = SetpointController(self.arbiter)
        self.tanks = TankRegistry.seeded()
        self.levels = LevelService(
            self.journal,
            self.bus,
            self.clock,
            self.generations,
            self.sheets,
            self.baselines,
            self.limits,
            settings,
        )
        self.inert = InertService(
            self.journal, self.bus, self.clock, self.blanket, VentLatch(self.switcher)
        )
        self.esd_valve = EsdValve(self.switcher)
        self.engine = InterlockEngine(self.journal, self.bus, self.clock)
        self.batches = BatchRegistry()
        self.machine = SequenceMachine(self.journal, self.bus, self.clock)
        self.interlock = TransferInterlock(
            self.levels, self.limits, self.baselines, self.generations, self.clock
        )
        self.gate = PumpStartGate(
            self.sheets,
            self.generations,
            self.persister,
            self.engine,
            self.interlock,
            self.clock,
        )
        self.inlet = InletController(
            SOURCE_TANK,
            VALVE_INLET,
            self.inert,
            self.engine,
            self.switcher,
            self.journal,
            self.bus,
            self.clock,
        )
        self.filling = FillingController(self.inlet, self.levels)
        self.handoff = Handoff(self.switcher, self.journal, self.bus, self.clock)
        self.trip = TripController(
            PROCESS_TANK,
            self.levels,
            self.engine,
            self.esd_valve,
            self.journal,
            self.bus,
            self.clock,
            self.pumps.running_ids,
            self.stop_pumps,
        )
        self.tests = TestController(
            PROCESS_TANK,
            self.levels,
            self.engine,
            self.esd_valve,
            self.journal,
            self.bus,
            self.clock,
        )
        self.capacity = CapacityEstimator(self.tanks, self.levels)
        self.auditor = AuditLog(self.repository, self.bus, self.ids, self.clock)
        self.auditor.subscribe()
        self.audit = AuditQuery(self.auditor)
        self.last_replay: ReplayResult | None = None

    # ---------------------------------------------------------------- journal

    def commit(self, seq: int | None = None) -> int:
        value = self.commits.commit(seq)
        self.repository.save_checkpoint(
            JournalCheckpoint(
                watermark=value,
                head=self.stream.head(),
                ts=self.clock.tick(),
                state=self.projection.snapshot(),
            )
        )
        return value

    def rollback(self, seq: int, reason: str) -> Record:
        record = self.rollbacks.rollback(seq, reason)
        self.rebuild()
        self.commit()
        return record

    def project(self, watermark: int) -> StateProjection:
        projection = StateProjection()
        for record in self.stream.records():
            if record.seq > watermark:
                break
            if self.tombstones.is_tombstoned(record.seq):
                continue
            projection.apply(record)
        return projection

    def visible_records(self, watermark: int | None = None) -> tuple[Record, ...]:
        limit = self.commits.watermark() if watermark is None else int(watermark)
        return tuple(
            record
            for record in self.stream.records()
            if record.seq <= limit and not self.tombstones.is_tombstoned(record.seq)
        )

    def select_records(self, record_filter: RecordFilter) -> tuple[Record, ...]:
        return record_filter.apply(self.visible_records())

    def rebuild(self) -> None:
        self.projection = self.project(self.commits.watermark())
        self._apply_projection()

    def restore(self) -> ReplayResult | None:
        records = self.repository.load_records()
        if not records:
            return None
        self.stream.load(records)
        for record in records:
            if record.kind == TOMBSTONE_KIND:
                target = record.payload.get("target_seq")
                if isinstance(target, int):
                    self.tombstones.mark(target)
        checkpoint = self.repository.load_checkpoint()
        if checkpoint is None:
            self.projection = self.project(0)
            self._apply_projection()
            self.auditor.restore()
            return None
        self.projection = StateProjection.from_snapshot(checkpoint.state)
        self.watermark.advance_to(checkpoint.watermark)
        result = replay(
            self.stream,
            self.commits,
            self.tombstones,
            checkpoint.watermark,
            self.projection.apply,
        )
        self._apply_projection()
        self.auditor.restore()
        self.last_replay = result
        return result

    def history(self, watermark: int | None = None) -> dict[str, object]:
        limit = self.commits.watermark() if watermark is None else int(watermark)
        projection = self.project(limit)
        return {
            "watermark": limit,
            "current_watermark": self.commits.watermark(),
            "state": projection.snapshot(),
        }

    def capture_snapshot(self) -> VersionedSnapshot:
        generation = self.generations.bump(SCOPE_SNAPSHOT, SNAPSHOT_KEY, self.clock.now())
        snapshot = self.snapshots.capture(
            state=self.projection.snapshot(),
            watermark=self.commits.watermark(),
            scope=SCOPE_SNAPSHOT,
            key=SNAPSHOT_KEY,
            generation=generation.number,
            config_generation=self.revisions.active().generation,
            now=self.clock.now(),
            policy=ExpiryPolicy(self.settings.snapshot_max_age),
        )
        return snapshot

    def validate_snapshot(self, snapshot_id: str) -> VersionedSnapshot:
        return self.snapshots.validate(snapshot_id, self.clock.now(), self.generations)

    def tick_clock(self, steps: int) -> int:
        return self.clock.tick(steps)

    # ------------------------------------------------------------- transfer

    def persist_valves(self) -> ConfirmationSheet:
        sheet = self.persister.persist()
        self.machine.set_fact(FACT_VALVE_PERSISTED, True)
        if self.machine.stage() == STAGE_IDLE:
            self.machine.advance(STAGE_VALVES_PERSISTED)
        self.commit()
        return sheet

    def open_valve(self, valve_id: str) -> Valve:
        valve = self.switcher.open(valve_id)
        self.commit()
        return valve

    def close_valve(self, valve_id: str) -> Valve:
        valve = self.switcher.close(valve_id)
        self.commit()
        return valve

    def start_pump(self, pump_id: str, sheet_id: str) -> dict[str, object]:
        pump = self.pumps.get(pump_id)
        self.machine.backfill(STAGE_PUMP_RUNNING)
        sheet, report = self.gate.verify(sheet_id, PROCESS_TANK)
        start_pump(pump, self.journal, self.bus, self.clock)
        self.commit()
        return {
            "pump_id": pump.pump_id,
            "sheet_id": sheet.sheet_id,
            "interlock": report.as_payload(),
        }

    def stop_pump(self, pump_id: str) -> Pump:
        pump = self.pumps.get(pump_id)
        stop_pump(pump, self.esd_valve, self.journal, self.bus, self.clock)
        self.commit()
        return pump

    def stop_pumps(self) -> tuple[str, ...]:
        stopped = stop_all_pumps(
            self.pumps, self.esd_valve, self.journal, self.bus, self.clock
        )
        return stopped

    def set_setpoint(self, pump_id: str, value: float) -> Pump:
        pump = self.pumps.get(pump_id)
        self.setpoints.apply(pump, value)
        self.commit()
        return pump

    def ramp_pump(self, pump_id: str, target: float) -> dict[str, object]:
        pump = self.pumps.get(pump_id)
        applied = self.setpoints.ramp(pump, target)
        self.commit()
        return {
            "pump_id": pump.pump_id,
            "setpoint": pump.setpoint,
            "steps": list(applied),
        }

    def change_tank(self) -> dict[str, str]:
        if self.machine.stage() == STAGE_OLD_TANK_CLOSED:
            raise StageAlreadyReachedError(STAGE_OLD_TANK_CLOSED)
        self.machine.backfill(STAGE_OLD_TANK_CLOSED)
        self.handoff.open_new(SOURCE_TANK)
        self.handoff.close_old(SOURCE_TANK, DESTINATION_TANK)
        self.commit()
        return {"new_tank_id": SOURCE_TANK, "old_tank_id": DESTINATION_TANK}

    def retry_change_tank(self) -> dict[str, object]:
        steps = self.handoff.retry(SOURCE_TANK, DESTINATION_TANK)
        self.commit()
        return {"steps": list(steps)}

    def open_inlet(self) -> dict[str, object]:
        state = self.inlet.open()
        self.evaluate_interlocks()
        self.commit()
        return state.as_payload()

    def fill_inlet(self, amount: float) -> dict[str, object]:
        state = self.filling.fill(amount)
        self.evaluate_interlocks()
        self.commit()
        return {"tank_id": state.tank_id, "reading": state.reading}

    def release_inlet(self) -> dict[str, object]:
        state = self.inlet.release()
        self.evaluate_interlocks()
        self.commit()
        return state.as_payload()

    def draw_level(self, tank_id: str, amount: float) -> LevelState:
        state = self.levels.draw(tank_id, amount)
        self.evaluate_interlocks()
        self.commit()
        return state

    # ------------------------------------------------------------------ esd

    def trip_esd(self) -> TripResult:
        result = self.trip.trip()
        self.evaluate_interlocks()
        self.commit()
        return result

    def retrip_esd(self) -> TripResult:
        result = self.trip.retrip()
        self.evaluate_interlocks()
        self.commit()
        return result

    def test_esd(self) -> dict[str, object]:
        self.tests.start()
        self.commit()
        return {"latched": self.engine.is_active(OVERFILL_LATCH)}

    def reset_esd(self) -> dict[str, object]:
        self.tests.reset()
        self.evaluate_interlocks()
        self.commit()
        return {"latched": self.engine.is_active(OVERFILL_LATCH)}

    # ---------------------------------------------------------------- level

    def switch_gauge(self, tank_id: str, gauge_id: str) -> ConfirmationSheet:
        sheet = self.levels.switch_gauge(tank_id, gauge_id)
        self.commit()
        return sheet

    def confirm_gauge(self, sheet_id: str) -> dict[str, object]:
        state = self.levels.confirm_gauge(sheet_id)
        self.commit()
        return state.as_payload()

    def recalibrate(self, tank_id: str, offset: float) -> dict[str, object]:
        baseline = self.levels.recalibrate(tank_id, offset)
        self.commit()
        return {"tank_id": tank_id, "baseline": baseline}

    def validate_baseline(self, tank_id: str) -> Baseline:
        return self.levels.validated_baseline(tank_id)

    def recent_updates(self, limit: int) -> tuple[dict[str, object], ...]:
        return tuple(item.as_payload() for item in self.levels.recent_updates(limit))

    # ------------------------------------------------------------- blanket

    def set_inert_pressure(self, tank_id: str, pressure: float) -> dict[str, object]:
        state = self.inert.set_pressure(tank_id, pressure)
        self.evaluate_interlocks()
        self.commit()
        return state.as_payload()

    def raise_inert_alarm(self, tank_id: str) -> dict[str, object]:
        state = self.inert.alarm(tank_id)
        self.evaluate_interlocks()
        self.commit()
        return state.as_payload()

    def clear_inert_alarm(self, tank_id: str) -> dict[str, object]:
        state = self.inert.clear_alarm(tank_id)
        self.evaluate_interlocks()
        self.commit()
        return state.as_payload()

    # --------------------------------------------------------------- config

    def revise_config(self, payload: dict[str, object]) -> dict[str, object]:
        settings = settings_from_payload(
            payload, base=self.revisions.active().settings
        ).with_addr(self._base_settings.addr).with_data_dir(self._base_settings.data_dir)
        revision = self.revisions.activate(settings, self.clock.tick())
        self.settings = settings
        self.limits.update(settings.high_limit_mm)
        self.blanket.update(settings.inert_low_kpa, settings.inert_high_kpa)
        self.journal.append(
            topics.CONFIG_REVISED,
            {
                "generation": revision.generation,
                "settings": settings.as_payload(),
            },
        )
        self.commit()
        return revision.as_payload()

    # --------------------------------------------------------------- batch

    def register_batch(self, batch_id: str, tank_id: str | None = None) -> BatchRegistration:
        target = tank_id or PROCESS_TANK
        registration = self.batches.register(
            batch_id, target, self.revisions.active().generation, self.clock.now()
        )
        self.journal.append(
            topics.BATCH_REGISTERED,
            {
                "batch_id": registration.batch_id,
                "tank_id": registration.tank_id,
                "generation": registration.generation,
            },
        )
        self.commit()
        return registration

    def get_batch(self, batch_id: str) -> BatchRegistration:
        return self.batches.get(batch_id)

    # ----------------------------------------------------------- interlock

    def evaluate_interlocks(self) -> tuple[LatchState, ...]:
        overfilled = False
        try:
            overfilled = self.limits.at_high(self.levels.read_confirmed(PROCESS_TANK))
        except GaugeNotConfirmedError:
            overfilled = False
        blanket_state = self.inert.state(PROCESS_TANK)
        ctx = ControlContext(
            level_overfilled=overfilled,
            gauge_confirmed=self.levels.is_confirmed(PROCESS_TANK),
            blanket_alarm=blanket_state.alarm,
            blanket_confirmed=blanket_state.confirmed,
            pumps_running=bool(self.pumps.running_ids()),
            esd_closed=self.esd_valve.is_closed(),
        )
        return self.engine.evaluate(ctx)

    def current_view(self) -> CurrentView:
        return CurrentView(
            valve_positions={valve.valve_id: valve.position for valve in self.valves.all()},
            header_setpoint=self.header.setpoint(),
            pumps={pump.pump_id: pump.as_payload() for pump in self.pumps.all()},
            levels={state.tank_id: state.as_payload() for state in self.levels.states()},
            latches={
                latch.name: latch.active for latch in self.engine.all() if latch.active
            },
            stage=self.machine.stage(),
            watermark=self.commits.watermark(),
            head=self.stream.head(),
        )

    def audit_summary(self) -> AuditSummary:
        return summarize(self.auditor.entries())

    def tank_summaries(self) -> tuple[TankSummary, ...]:
        return tuple(
            build_summary(tank, self.levels, self.capacity) for tank in self.tanks.all()
        )

    def interlock_report(self, tank_id: str) -> InterlockReport:
        return self.interlock.report(tank_id)

    # ------------------------------------------------------------- internal

    def _observe(self, record: Record) -> None:
        self.projection.apply(record)

    def _restore_generations(self) -> None:
        for (scope, key), (number, ts) in self.projection.generations.items():
            self.generations.restore(scope, key, number, ts)

    def _restore_config(self) -> None:
        if not self.projection.config_generation:
            return
        settings = settings_from_state(self.projection.settings)
        settings = settings.with_addr(self._base_settings.addr).with_data_dir(
            self._base_settings.data_dir
        )
        self.settings = settings
        self.revisions.restore(
            ConfigRevision(
                generation=self.projection.config_generation,
                settings=settings,
                issued_at=0,
            )
        )
        self.limits.update(settings.high_limit_mm)
        self.blanket.update(settings.inert_low_kpa, settings.inert_high_kpa)

    def _reset_devices(self) -> None:
        self.valves.reset_to_seed()
        self.pumps.reset_to_seed()
        self.levels.seed()
        self.inert.seed()
        self.machine.reset()
        self.engine.reset()
        self.header.restore(0.0)
        self.inlet.apply_open(False)
        self.batches.restore({})

    def _apply_projection(self) -> None:
        self._restore_generations()
        self._restore_config()
        self._reset_devices()
        self.valves.apply_positions(
            dict(self.projection.valve_positions), dict(self.projection.valve_ts)
        )
        self.header.restore(self.projection.header_setpoint)
        self.pumps.apply_running(dict(self.projection.pump_running))
        policy = ExpiryPolicy(self.settings.baseline_max_age)
        for tank_id in self.levels.tank_ids():
            if tank_id in self.projection.readings:
                self.levels.apply_reading(tank_id, self.projection.readings[tank_id])
            if tank_id in self.projection.gauges:
                self.levels.apply_gauge(
                    tank_id,
                    self.projection.gauges[tank_id],
                    self.projection.gauge_confirmed.get(tank_id, False),
                    self.projection.gauge_generation.get(tank_id, 0),
                )
            if tank_id in self.projection.baselines:
                self.levels.apply_calibration(
                    tank_id,
                    self.projection.baselines[tank_id],
                    self.projection.offsets.get(tank_id, 0.0),
                )
                self.baselines.record(
                    tank_id=tank_id,
                    value=self.projection.baselines[tank_id],
                    generation=self.projection.baseline_generation.get(tank_id, 0),
                    config_generation=self.revisions.active().generation,
                    now=self.clock.now(),
                    policy=policy,
                )
            elif tank_id in self.projection.offsets:
                self.levels.apply_offset(tank_id, self.projection.offsets[tank_id])
        for tank_id, pressure in self.projection.pressures.items():
            self.inert.apply_pressure(tank_id, pressure)
        for tank_id, alarm in self.projection.inert_alarm.items():
            self.inert.apply_alarm(tank_id, alarm)
        for name, active in self.projection.latches.items():
            self.engine.restore(name, active, self.projection.latch_reason.get(name, ""))
        self.batches.restore(dict(self.projection.batches))


def build_services(
    settings: ControlSettings = DEFAULT_SETTINGS, repository: Repository | None = None
) -> Services:
    return Services(settings, repository)
