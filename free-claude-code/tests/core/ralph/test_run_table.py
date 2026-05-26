"""Tests for core.ralph.run_table."""

from __future__ import annotations

from core.ralph.models import TaskStatus
from core.ralph.roles import AgentRole
from core.ralph.run_table import RunTable, RunTableEntry
from core.ralph.scoring import HallucinationRisk, ScoreCard


def _entry(
    task_id: str = "t1",
    run_id: str = "r1",
    status: TaskStatus = TaskStatus.PENDING,
) -> RunTableEntry:
    return RunTableEntry(
        run_id=run_id,
        task_id=task_id,
        task_title=f"Task {task_id}",
        agent_role=AgentRole.DOER,
        status=status,
    )


class TestRunTable:
    def test_can_add_entries(self) -> None:
        table = RunTable()
        table.add_entry(_entry())
        assert table.entry_count == 1

    def test_can_update_status(self) -> None:
        table = RunTable()
        table.add_entry(_entry("t1"))
        assert table.update_status("t1", TaskStatus.RUNNING) is True
        entry = table.get_entry("t1")
        assert entry is not None
        assert entry.status == TaskStatus.RUNNING

    def test_update_status_unknown_task_returns_false(self) -> None:
        table = RunTable()
        assert table.update_status("nonexistent", TaskStatus.PASSED) is False

    def test_can_list_failed_entries(self) -> None:
        table = RunTable()
        table.add_entry(_entry("t1", status=TaskStatus.PASSED))
        table.add_entry(_entry("t2", status=TaskStatus.FAILED))
        table.add_entry(_entry("t3", status=TaskStatus.BLOCKED))
        table.add_entry(_entry("t4", status=TaskStatus.RUNNING))
        failed = table.list_failed_entries()
        assert len(failed) == 2
        assert {e.task_id for e in failed} == {"t2", "t3"}

    def test_can_list_active_entries(self) -> None:
        table = RunTable()
        table.add_entry(_entry("t1", status=TaskStatus.PENDING))
        table.add_entry(_entry("t2", status=TaskStatus.RUNNING))
        table.add_entry(_entry("t3", status=TaskStatus.PASSED))
        active = table.list_active_entries()
        assert len(active) == 2
        assert {e.task_id for e in active} == {"t1", "t2"}

    def test_completion_percentage(self) -> None:
        table = RunTable()
        table.add_entry(_entry("t1", status=TaskStatus.PASSED))
        table.add_entry(_entry("t2", status=TaskStatus.PASSED))
        table.add_entry(_entry("t3", status=TaskStatus.RUNNING))
        table.add_entry(_entry("t4", status=TaskStatus.PENDING))
        pct = table.completion_percentage("r1")
        assert pct == 50.0

    def test_completion_percentage_empty_run(self) -> None:
        table = RunTable()
        assert table.completion_percentage("empty") == 0.0

    def test_completion_percentage_no_tasks(self) -> None:
        table = RunTable()
        # Add an entry for a different run
        table.add_entry(_entry("t1", run_id="other"))
        assert table.completion_percentage("r1") == 0.0

    def test_serialization(self) -> None:
        table = RunTable()
        table.add_entry(_entry("t1", status=TaskStatus.RUNNING))
        table.add_entry(_entry("t2", status=TaskStatus.PASSED))
        serial = table.serializable()
        assert len(serial) == 2
        assert serial[0]["task_id"] == "t1"
        assert serial[0]["status"] == "running"
        assert serial[1]["status"] == "passed"

    def test_serialization_with_score(self) -> None:
        table = RunTable()
        entry = _entry("t1")
        score = ScoreCard(
            implementation_score=90,
            test_score=80,
            kpi_score=85,
            risk_score=10,
            confidence_score=88,
            hallucination_risk=HallucinationRisk.LOW,
        )
        entry.score = score
        table.add_entry(entry)
        serial = table.serializable()
        assert serial[0]["score"] is not None
        assert serial[0]["score"]["implementation_score"] == 90
        assert serial[0]["score"]["is_passing"] is True

    def test_record_error(self) -> None:
        table = RunTable()
        table.add_entry(_entry("t1"))
        assert table.record_error("t1", "Something broke") is True
        entry = table.get_entry("t1")
        assert entry is not None
        assert entry.last_error == "Something broke"

    def test_record_error_unknown_task(self) -> None:
        table = RunTable()
        assert table.record_error("nonexistent", "error") is False

    def test_clear(self) -> None:
        table = RunTable()
        table.add_entry(_entry("t1"))
        table.add_entry(_entry("t2"))
        assert table.entry_count == 2
        table.clear()
        assert table.entry_count == 0

    def test_get_entries_for_run(self) -> None:
        table = RunTable()
        table.add_entry(_entry("t1", run_id="r1"))
        table.add_entry(_entry("t2", run_id="r1"))
        table.add_entry(_entry("t3", run_id="r2"))
        r1_entries = table.get_entries_for_run("r1")
        assert len(r1_entries) == 2
        r2_entries = table.get_entries_for_run("r2")
        assert len(r2_entries) == 1

    def test_duplicate_task_id_does_not_duplicate_entry(self) -> None:
        table = RunTable()
        entry = _entry("t1", run_id="r1")
        table.add_entry(entry)
        table.add_entry(entry)  # same task_id again
        entries = table.get_entries_for_run("r1")
        assert len(entries) == 1, "Duplicate task_id must not create duplicate entries"

    def test_duplicate_task_id_updates_not_duplicates(self) -> None:
        table = RunTable()
        table.add_entry(_entry("t1", run_id="r1", status=TaskStatus.PENDING))
        # Re-add same task_id with different status
        table.add_entry(_entry("t1", run_id="r1", status=TaskStatus.PASSED))
        entries = table.get_entries_for_run("r1")
        assert len(entries) == 1
        assert entries[0].status == TaskStatus.PASSED

    def test_completion_accurate_after_duplicate_add(self) -> None:
        table = RunTable()
        table.add_entry(_entry("t1", run_id="r1", status=TaskStatus.PASSED))
        table.add_entry(
            _entry("t1", run_id="r1", status=TaskStatus.PASSED)
        )  # duplicate
        table.add_entry(_entry("t2", run_id="r1", status=TaskStatus.PENDING))
        pct = table.completion_percentage("r1")
        assert pct == 50.0, "Duplicate must not inflate denominator"
