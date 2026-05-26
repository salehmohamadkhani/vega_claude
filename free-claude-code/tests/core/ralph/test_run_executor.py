"""Tests for RunExecutor — multi-task run coordination."""

from __future__ import annotations

from unittest.mock import MagicMock, create_autospec

from core.ralph.execution import ExecutionStatus
from core.ralph.models import RalphRun, RalphTask, RunStatus, TaskStatus
from core.ralph.run_executor import RunExecutor
from core.ralph.run_lifecycle import RunLifecycle


def _make_lifecycle_with_table(tasks: list[RalphTask]) -> MagicMock:
    """Create a mock RunLifecycle that registers tasks in its run table."""
    lifecycle = create_autospec(RunLifecycle, instance=True)
    entry = MagicMock()
    lifecycle._run_table = MagicMock()
    lifecycle._run_table.get_entry.return_value = entry
    return lifecycle


def _make_run(tasks: list[RalphTask] | None = None) -> RalphRun:
    run = RalphRun(id="run-1", goal_id="goal-1", status=RunStatus.RUNNING)
    for t in tasks or []:
        run.add_task(t)
    return run


def _make_task(task_id: str, status: TaskStatus = TaskStatus.PENDING) -> RalphTask:
    return RalphTask(
        id=task_id,
        title=f"Task {task_id}",
        status=status,
    )


class TestRunExecutor:
    def setup_method(self) -> None:
        self.executor = RunExecutor()

    def test_selects_next_pending_task(self) -> None:
        tasks = [
            _make_task("task-1", TaskStatus.PENDING),
            _make_task("task-2", TaskStatus.PASSED),
        ]
        run = _make_run(tasks)
        found = self.executor._find_next_task(run)
        assert found is not None
        assert found.id == "task-1"

    def test_selects_next_approved_task(self) -> None:
        tasks = [
            _make_task("task-1", TaskStatus.PASSED),
            _make_task("task-2", TaskStatus.APPROVED),
        ]
        run = _make_run(tasks)
        found = self.executor._find_next_task(run)
        assert found is not None
        assert found.id == "task-2"

    def test_returns_none_when_no_tasks(self) -> None:
        run = _make_run([])
        found = self.executor._find_next_task(run)
        assert found is None

    def test_returns_none_when_all_done(self) -> None:
        tasks = [
            _make_task("task-1", TaskStatus.PASSED),
            _make_task("task-2", TaskStatus.PASSED),
        ]
        run = _make_run(tasks)
        found = self.executor._find_next_task(run)
        assert found is None

    def test_approves_pending_task(self) -> None:
        tasks = [_make_task("task-1", TaskStatus.PENDING)]
        run = _make_run(tasks)
        lifecycle = _make_lifecycle_with_table(tasks)
        executor = RunExecutor(run_lifecycle=lifecycle)
        result = executor.run_next_task(run)
        assert result is not None
        assert result.task_id == "task-1"

    def test_dry_run_safe(self) -> None:
        """Verify executor never triggers real execution."""
        tasks = [_make_task("task-1", TaskStatus.PENDING)]
        run = _make_run(tasks)
        lifecycle = _make_lifecycle_with_table(tasks)
        executor = RunExecutor(run_lifecycle=lifecycle)
        result = executor.run_next_task(run)
        assert result is not None
        assert result.execution_result.status == ExecutionStatus.SKIPPED

    def test_respects_task_order(self) -> None:
        """Verify tasks are processed in insertion order."""
        tasks = [
            _make_task("task-a", TaskStatus.PENDING),
            _make_task("task-b", TaskStatus.PENDING),
        ]
        run = _make_run(tasks)
        lifecycle = _make_lifecycle_with_table(tasks)
        executor = RunExecutor(run_lifecycle=lifecycle)

        result1 = executor.run_next_task(run)
        assert result1 is not None
        assert result1.task_id == "task-a"

        result2 = executor.run_next_task(run)
        assert result2 is not None
        assert result2.task_id == "task-b"
