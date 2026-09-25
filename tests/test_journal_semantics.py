"""Contract (a): append-only stream, commit watermark, replay and tombstones."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from tankfarm.clock import LogicalClock
from tankfarm.errors import (
    DuplicateTombstoneError,
    RecordNotFoundError,
    RollbackTargetError,
    UncommittedRecordError,
    WatermarkRegressionError,
)
from tankfarm.ids import IdFactory
from tankfarm.journal import (
    TOMBSTONE_KIND,
    CommitController,
    JournalCheckpoint,
    JournalWriter,
    RecordStream,
    RollbackService,
    TombstoneIndex,
    Watermark,
    replay,
)
from tankfarm.store.repository import Repository


@pytest.fixture
def journal(tmp_path):
    repository = Repository(tmp_path / "var")
    stream = RecordStream(IdFactory())
    commits = CommitController(stream, Watermark())
    index = TombstoneIndex()
    writer = JournalWriter(stream, repository, LogicalClock())
    return SimpleNamespace(
        repository=repository,
        stream=stream,
        commits=commits,
        index=index,
        writer=writer,
        rollback=RollbackService(writer, commits, index),
    )


def _append(journal, count: int) -> None:
    for index in range(count):
        journal.writer.append("step", {"index": index})


def test_appended_records_get_increasing_sequence_numbers(journal):
    first = journal.writer.append("valve.position", {"valve_id": "valve-inlet"})
    second = journal.writer.append("valve.position", {"valve_id": "valve-inlet"})
    assert (first.seq, second.seq) == (1, 2)
    assert journal.stream.head() == 2
    assert [record.seq for record in journal.stream.records()] == [1, 2]


def test_uncommitted_records_are_invisible_to_committed_readers(journal):
    _append(journal, 2)
    journal.commits.commit(1)
    assert [record.seq for record in journal.commits.committed()] == [1]
    assert [record.seq for record in journal.commits.pending()] == [2]


def test_commit_watermark_advances_monotonically(journal):
    _append(journal, 3)
    assert journal.commits.commit(1) == 1
    assert journal.commits.commit(3) == 3
    assert journal.commits.watermark() == 3


def test_watermark_regression_is_rejected(journal):
    _append(journal, 2)
    journal.commits.commit(2)
    with pytest.raises(WatermarkRegressionError):
        journal.commits.commit(1)


def test_committing_beyond_stream_head_is_rejected(journal):
    _append(journal, 1)
    with pytest.raises(RecordNotFoundError):
        journal.commits.commit(5)


def test_rollback_appends_tombstone_instead_of_removing_record(journal):
    _append(journal, 1)
    journal.commits.commit(1)
    tombstone = journal.rollback.rollback(1, "wrong valve position")
    assert tombstone.kind == TOMBSTONE_KIND
    assert tombstone.payload["target_seq"] == 1
    assert journal.stream.head() == 2
    assert journal.stream.get(1).kind == "step"


def test_rollback_hides_record_from_visible_stream(journal):
    _append(journal, 2)
    journal.commits.commit(2)
    journal.rollback.rollback(1, "operator undo")
    visible = [
        record.seq
        for record in journal.commits.committed()
        if not journal.index.is_tombstoned(record.seq)
    ]
    assert visible == [2, 3]
    assert journal.index.targets() == (1,)


def test_rollback_of_uncommitted_record_is_rejected(journal):
    _append(journal, 2)
    journal.commits.commit(1)
    with pytest.raises(UncommittedRecordError):
        journal.rollback.rollback(2, "too early")


def test_duplicate_rollback_is_rejected(journal):
    _append(journal, 1)
    journal.commits.commit(1)
    journal.rollback.rollback(1, "first")
    with pytest.raises(DuplicateTombstoneError):
        journal.rollback.rollback(1, "second")


def test_rollback_of_a_tombstone_is_rejected(journal):
    _append(journal, 1)
    journal.commits.commit(1)
    tombstone = journal.rollback.rollback(1, "first")
    with pytest.raises(RollbackTargetError):
        journal.rollback.rollback(tombstone.seq, "second")


def test_replay_from_watermark_applies_only_newer_committed_records(journal):
    _append(journal, 4)
    journal.commits.commit(2)
    applied = []
    result = replay(journal.stream, journal.commits, journal.index, 1, applied.append)
    assert [record.seq for record in applied] == [2]
    assert result.from_watermark == 1
    assert result.to_watermark == 2
    assert result.applied_count() == 1
    assert result.skipped_count() == 2


def test_replay_skips_pending_records_after_restart(journal):
    _append(journal, 3)
    journal.commits.commit(2)
    result = replay(journal.stream, journal.commits, journal.index, 0, lambda rec: None)
    assert [record.seq for record in result.skipped_uncommitted] == [3]


def test_replay_skips_tombstoned_records(journal):
    _append(journal, 3)
    journal.commits.commit(3)
    journal.rollback.rollback(2, "undo second step")
    applied = []
    result = replay(journal.stream, journal.commits, journal.index, 0, applied.append)
    assert [record.seq for record in applied] == [1, 3, 4]
    assert [record.seq for record in result.skipped_tombstoned] == [2]


def test_checkpoint_round_trips_watermark_and_state(journal):
    checkpoint = JournalCheckpoint(
        watermark=2,
        head=3,
        ts=17,
        state={"valves": {"valve-inlet": "open"}},
    )
    journal.repository.save_checkpoint(checkpoint)
    loaded = journal.repository.load_checkpoint()
    assert loaded is not None
    assert loaded.watermark == 2
    assert loaded.head == 3
    assert loaded.state["valves"]["valve-inlet"] == "open"


def test_journal_file_only_grows_by_appending(journal):
    _append(journal, 2)
    journal.commits.commit(2)
    journal.rollback.rollback(1, "undo")
    lines = journal.repository.layout.journal_file().read_text(encoding="utf-8")
    assert len(lines.splitlines()) == 3
    assert journal.stream.head() == 3


def test_rollback_never_rewrites_earlier_records(journal):
    _append(journal, 1)
    journal.commits.commit(1)
    before = journal.stream.records()
    journal.rollback.rollback(1, "undo")
    after = journal.stream.records()
    assert after[:1] == before
