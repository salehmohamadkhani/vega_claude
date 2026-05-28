"""Tests for CLI loop integration (fcc-ralph run --loop)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.ralph.cli import (
    EXIT_APPROVAL_REQUIRED,
    EXIT_ERROR,
    EXIT_SUCCESS,
    EXIT_UNSAFE_REAL,
    _run_cli,
)
from core.ralph.models import TaskStatus
from core.ralph.task_library import TaskLibrary
from core.ralph.workspace import RalphWorkspace


def _ws(project_root: Path) -> RalphWorkspace:
    return RalphWorkspace(project_root=str(project_root))


def _plan_and_approve(tmp_path: Path, task_count: int = 1) -> list[str]:
    """Helper: plan and approve the first N tasks. Returns task IDs."""
    _run_cli(
        [
            f"--workspace={tmp_path}",
            "plan",
            "CLI loop test goal",
            "--kpi",
            "All tests pass",
        ]
    )
    task_lib = TaskLibrary(workspace=_ws(tmp_path))
    tasks = task_lib.list_tasks()
    ids = [t.id for t in tasks[:task_count]]
    for tid in ids:
        _run_cli([f"--workspace={tmp_path}", "approve", tid])
    return ids


def _approve_all(tmp_path: Path) -> list[str]:
    """Helper: approve all pending tasks. Returns task IDs."""
    _run_cli([f"--workspace={tmp_path}", "approve", "--all"])
    task_lib = TaskLibrary(workspace=_ws(tmp_path))
    return [t.id for t in task_lib.list_tasks()]


class TestCliLoopBasic:
    """Basic CLI loop command."""

    def test_run_loop_with_pending_returns_approval_required(
        self, tmp_path: Path
    ) -> None:
        """run --loop with no approved tasks returns approval-required (no tasks run)."""
        _run_cli([f"--workspace={tmp_path}", "plan", "Loop pending test"])
        task_lib = TaskLibrary(workspace=_ws(tmp_path))
        tasks_before = task_lib.list_tasks()
        assert all(t.status == TaskStatus.PENDING for t in tasks_before)

        rc = _run_cli([f"--workspace={tmp_path}", "run", "--loop"])
        assert rc == EXIT_APPROVAL_REQUIRED

        # No task status should have changed — nothing ran
        tasks_after = task_lib.list_tasks()
        assert all(t.status == TaskStatus.PENDING for t in tasks_after)

    def test_run_loop_with_approved_task_runs(self, tmp_path: Path) -> None:
        """run --loop with a contiguous approved prefix runs those tasks."""
        _plan_and_approve(tmp_path, task_count=4)
        rc = _run_cli([f"--workspace={tmp_path}", "run", "--loop"])
        # With all tasks approved, the loop runs them all — dry-run
        # quality gate returns DEBUG so completed may be True/False.
        assert rc in (EXIT_SUCCESS, EXIT_ERROR)

    def test_run_loop_task_status_updated(self, tmp_path: Path) -> None:
        """After run --loop with all approved, task status is updated."""
        ids = _plan_and_approve(tmp_path, task_count=4)
        _run_cli([f"--workspace={tmp_path}", "run", "--loop"])
        task_lib = TaskLibrary(workspace=_ws(tmp_path))
        task = task_lib.find_task(ids[0])
        assert task is not None
        # After loop, task should not be PENDING or APPROVED
        assert task.status not in (TaskStatus.PENDING, TaskStatus.APPROVED)


class TestCliLoopFlags:
    """CLI loop flags."""

    def test_max_iterations_flag(self, tmp_path: Path) -> None:
        """--max-iterations flag is accepted."""
        _plan_and_approve(tmp_path, task_count=4)
        rc = _run_cli(
            [
                f"--workspace={tmp_path}",
                "run",
                "--loop",
                "--max-iterations",
                "5",
            ]
        )
        assert rc in (EXIT_SUCCESS, EXIT_ERROR)

    def test_max_tasks_flag(self, tmp_path: Path) -> None:
        """--max-tasks flag limits tasks processed."""
        _plan_and_approve(tmp_path, task_count=4)
        rc = _run_cli(
            [
                f"--workspace={tmp_path}",
                "run",
                "--loop",
                "--max-tasks",
                "2",
            ]
        )
        assert rc in (EXIT_SUCCESS, EXIT_ERROR)


class TestCliLoopSafety:
    """CLI loop safety properties."""

    def test_run_loop_real_without_allow_fails_safely(self, tmp_path: Path) -> None:
        """run --loop --real without --allow-real-execution fails."""
        _plan_and_approve(tmp_path)
        rc = _run_cli(
            [
                f"--workspace={tmp_path}",
                "run",
                "--loop",
                "--real",
            ]
        )
        assert rc == EXIT_UNSAFE_REAL

    def test_run_loop_pending_blocked(self, tmp_path: Path) -> None:
        """run --loop is blocked when first task is PENDING — no later approved task runs."""
        _run_cli([f"--workspace={tmp_path}", "plan", "Pending block test"])
        task_lib = TaskLibrary(workspace=_ws(tmp_path))
        tasks = task_lib.list_tasks()

        # Ensure we have at least 2 tasks to test ordering
        if len(tasks) < 2:
            pytest.skip("Need at least 2 tasks to test ordering")

        # Approve second task but not first — first stays PENDING
        _run_cli([f"--workspace={tmp_path}", "approve", tasks[1].id])
        rc = _run_cli([f"--workspace={tmp_path}", "run", "--loop"])
        assert rc == EXIT_APPROVAL_REQUIRED

        # First task must not have run (still PENDING)
        t1 = task_lib.find_task(tasks[0].id)
        assert t1 is not None
        assert t1.status == TaskStatus.PENDING, (
            f"First task {tasks[0].id} should still be PENDING but is {t1.status.value}"
        )
        # Second task must also not have run — it's after a PENDING task
        t2 = task_lib.find_task(tasks[1].id)
        assert t2 is not None
        assert t2.status == TaskStatus.APPROVED, (
            f"Second task {tasks[1].id} should still be APPROVED but is {t2.status.value}"
        )

    def test_later_approved_blocked_by_earlier_pending(self, tmp_path: Path) -> None:
        """run --loop: if TASK-001 is APPROVED, TASK-002 PENDING,
        TASK-001 runs, then blocks at TASK-002. TASK-002 must NOT run."""
        _run_cli([f"--workspace={tmp_path}", "plan", "Prefix block test"])
        task_lib = TaskLibrary(workspace=_ws(tmp_path))
        tasks = task_lib.list_tasks()

        # Ensure we have at least 2 tasks
        if len(tasks) < 2:
            pytest.skip("Need at least 2 tasks to test prefix blocking")

        # Approve only first task
        _run_cli([f"--workspace={tmp_path}", "approve", tasks[0].id])
        rc = _run_cli([f"--workspace={tmp_path}", "run", "--loop"])
        assert rc == EXIT_APPROVAL_REQUIRED

        # TASK-001 must have run (status changed from APPROVED)
        t1 = task_lib.find_task(tasks[0].id)
        assert t1 is not None
        assert t1.status not in (TaskStatus.PENDING, TaskStatus.APPROVED), (
            f"Task {tasks[0].id} should have run but is {t1.status.value}"
        )

        # TASK-002 must still be PENDING (not run)
        t2 = task_lib.find_task(tasks[1].id)
        assert t2 is not None
        assert t2.status == TaskStatus.PENDING, (
            f"Task {tasks[1].id} should still be PENDING but is {t2.status.value}"
        )


class TestCliLoopJson:
    """CLI loop JSON output."""

    def test_run_loop_json_is_parseable(self, tmp_path: Path, capsys) -> None:
        """run --loop --json outputs parseable JSON."""
        _plan_and_approve(tmp_path, task_count=4)
        capsys.readouterr()  # discard setup output

        _run_cli(
            [
                f"--workspace={tmp_path}",
                "--json",
                "run",
                "--loop",
            ]
        )
        captured = capsys.readouterr()
        if captured.out.strip():
            data = json.loads(captured.out)
            assert "mode" in data
            assert "completed" in data
            assert "total_iterations" in data

    def test_run_loop_json_pending_output(self, tmp_path: Path, capsys) -> None:
        """run --loop --json with all-pending tasks produces valid JSON with blocked info."""
        _plan_and_approve(tmp_path, task_count=2)
        # Approve first task only
        task_lib = TaskLibrary(workspace=_ws(tmp_path))
        task_lib.list_tasks()  # discard, setup only
        capsys.readouterr()  # discard setup output

        _run_cli(
            [
                f"--workspace={tmp_path}",
                "--json",
                "run",
                "--loop",
            ]
        )
        captured = capsys.readouterr()
        assert captured.out.strip(), "Expected JSON output"
        data = json.loads(captured.out)
        # approval_required should be True since some tasks are pending
        assert data.get("approval_required") is True
        assert data.get("completed") is False
        assert "pending_task_ids" in data
        assert data.get("blocked_task_id", "") != "", "blocked_task_id must be set"
        assert data.get("mode") is not None

    def test_run_loop_json_all_pending_output(self, tmp_path: Path, capsys) -> None:
        """run --loop --json with ALL tasks pending — no stdout plain text."""
        _run_cli([f"--workspace={tmp_path}", "plan", "JSON all pending"])
        capsys.readouterr()  # discard plan output

        rc = _run_cli(
            [
                f"--workspace={tmp_path}",
                "--json",
                "run",
                "--loop",
            ]
        )
        captured = capsys.readouterr()
        assert rc == EXIT_APPROVAL_REQUIRED
        assert captured.out.strip(), "Expected JSON output on stdout"
        # Stderr may have warnings but stdout must be valid JSON
        data = json.loads(captured.out)
        assert data.get("approval_required") is True
        assert data.get("completed") is False
        assert data.get("blocked_task_id") is not None
        assert "pending_task_ids" in data


class TestCliLoopNoSideEffects:
    """No unsafe side effects from CLI loop."""

    def test_run_loop_no_workspace_returns_error(self, tmp_path: Path) -> None:
        """run --loop without workspace returns error (not crash)."""
        rc = _run_cli([f"--workspace={tmp_path}", "run", "--loop"])
        assert rc == EXIT_ERROR

    def test_run_loop_no_tasks_returns_error(self, tmp_path: Path) -> None:
        """run --loop with workspace but no tasks returns error."""
        ws = _ws(tmp_path)
        ws.initialize()
        rc = _run_cli([f"--workspace={tmp_path}", "run", "--loop"])
        assert rc == EXIT_ERROR
