"""Tests for core.ralph.checkpoint."""

from __future__ import annotations

from core.ralph.checkpoint import (
    Checkpoint,
    CheckpointNotFoundError,
    CheckpointStore,
)
from core.ralph.models import RunStatus, TaskStatus
from core.ralph.scoring import ScoreCard
from core.ralph.workspace import RalphWorkspace


class TestCheckpointStore:
    def make_store(self, tmp_path) -> CheckpointStore:
        ws = RalphWorkspace(tmp_path)
        ws.initialize()
        return CheckpointStore(ws)

    def test_saves_and_loads_checkpoint(self, tmp_path) -> None:
        store = self.make_store(tmp_path)
        cp = Checkpoint(id="cp1", run_id="r1", task_id="t1", iteration_number=1)
        store.save_checkpoint(cp)
        loaded = store.load_checkpoint("cp1")
        assert loaded.id == "cp1"
        assert loaded.run_id == "r1"
        assert loaded.task_id == "t1"
        assert loaded.iteration_number == 1

    def test_latest_checkpoint_per_run(self, tmp_path) -> None:
        store = self.make_store(tmp_path)
        cp1 = Checkpoint(id="c1", run_id="run1", iteration_number=1)
        cp2 = Checkpoint(id="c2", run_id="run1", iteration_number=2)
        cp3 = Checkpoint(id="c3", run_id="run2", iteration_number=1)
        for c in (cp1, cp2, cp3):
            store.save_checkpoint(c)

        latest = store.latest_for_run("run1")
        assert latest is not None
        assert latest.id == "c2"
        assert latest.iteration_number == 2

        assert store.latest_for_run("nonexistent") is None

    def test_list_checkpoints_ordered(self, tmp_path) -> None:
        store = self.make_store(tmp_path)
        c1 = Checkpoint(id="a1", run_id="r1", iteration_number=1)
        c2 = Checkpoint(id="a2", run_id="r1", iteration_number=3)
        c3 = Checkpoint(id="a3", run_id="r1", iteration_number=2)
        for c in (c1, c2, c3):
            store.save_checkpoint(c)

        result = store.list_for_run("r1")
        ids = [cp.id for cp in result]
        # Highest iteration first
        assert ids == ["a2", "a3", "a1"]

    def test_checkpoint_from_run_state(self) -> None:
        score = ScoreCard(
            implementation_score=90,
            test_score=80,
            kpi_score=85,
            risk_score=10,
            confidence_score=88,
        )
        cp = Checkpoint.from_run_state(
            run_id="r1",
            task_id="t1",
            iteration_number=2,
            run_status=RunStatus.RUNNING,
            task_status=TaskStatus.RUNNING,
            score_card=score,
            arbiter_action="approve",
            next_action="continue",
        )
        assert cp.run_id == "r1"
        assert cp.iteration_number == 2
        assert cp.run_status == "running"
        assert cp.arbiter_action == "approve"
        assert cp.score.get("implementation_score") == 90

    def test_load_nonexistent_raises(self, tmp_path) -> None:
        store = self.make_store(tmp_path)
        with __import__("pytest").raises(CheckpointNotFoundError):
            store.load_checkpoint("nosuch")

    def test_delete_checkpoint(self, tmp_path) -> None:
        store = self.make_store(tmp_path)
        cp = Checkpoint(id="delcp", run_id="r1")
        store.save_checkpoint(cp)
        assert store.delete_checkpoint("delcp") is True
        assert store.delete_checkpoint("delcp") is False

    def test_from_run_state_round_trip(self, tmp_path) -> None:
        """Ensure from_run_state checkpoint round-trips via save/load."""
        store = self.make_store(tmp_path)
        score = ScoreCard(
            implementation_score=85, test_score=90, kpi_score=75,
            risk_score=15, confidence_score=80,
        )
        cp = Checkpoint.from_run_state(
            run_id="r-round",
            task_id="t-round",
            iteration_number=3,
            run_status=RunStatus.RUNNING,
            task_status=TaskStatus.PASSED,
            score_card=score,
            arbiter_action="approve",
            next_action="finish",
            extra_meta="preserved",
        )
        store.save_checkpoint(cp)
        loaded = store.load_checkpoint(cp.id)
        assert loaded.run_id == "r-round"
        assert loaded.task_id == "t-round"
        assert loaded.iteration_number == 3
        assert loaded.run_status == "running"
        assert loaded.task_status == "passed"
        assert loaded.score.get("implementation_score") == 85
        assert loaded.score.get("final_weighted_score") is not None
        assert loaded.arbiter_action == "approve"
        assert loaded.next_action == "finish"
        assert loaded.metadata.get("extra_meta") == "preserved"
