"""Tests for RunExecutor — multi-task run coordination."""

from __future__ import annotations

from unittest.mock import MagicMock, create_autospec

from core.ralph.arbiter import ArbiterAction, ArbiterDecision
from core.ralph.execution import ExecutionResult, ExecutionStatus
from core.ralph.iteration_runner import IterationRunResult
from core.ralph.models import RalphRun, RalphTask, RunStatus, TaskStatus
from core.ralph.quality_gate import QualityGateResult
from core.ralph.run_executor import RunExecutor, RunExecutorConfig
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

    def test_selects_approved_over_pending(self) -> None:
        tasks = [
            _make_task("task-1", TaskStatus.PENDING),
            _make_task("task-2", TaskStatus.APPROVED),
        ]
        run = _make_run(tasks)
        found = self.executor._find_next_task(run)
        assert found is not None
        assert found.id == "task-1"  # insertion order

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

    # ------------------------------------------------------------------
    # Approval gate tests
    # ------------------------------------------------------------------

    def test_does_not_auto_approve_pending_by_default(self) -> None:
        """Default executor returns None for pending tasks, does not approve."""
        tasks = [_make_task("task-1", TaskStatus.PENDING)]
        run = _make_run(tasks)
        lifecycle = _make_lifecycle_with_table(tasks)
        executor = RunExecutor(run_lifecycle=lifecycle)
        result = executor.run_next_task(run)
        assert result is None
        lifecycle.approve_task.assert_not_called()
        lifecycle.mark_task_running.assert_not_called()

    def test_pending_only_run_returns_approval_required(self) -> None:
        """run_until_blocked returns approval_required=True for pending-only runs."""
        tasks = [_make_task("task-1", TaskStatus.PENDING)]
        run = _make_run(tasks)
        lifecycle = _make_lifecycle_with_table(tasks)
        executor = RunExecutor(run_lifecycle=lifecycle)
        result = executor.run_until_blocked(run)
        assert result.approval_required is True
        assert "task-1" in result.pending_task_ids
        assert result.completed is False

    def test_approved_task_can_run(self) -> None:
        """Approved tasks can execute directly."""
        tasks = [_make_task("task-1", TaskStatus.APPROVED)]
        run = _make_run(tasks)
        lifecycle = _make_lifecycle_with_table(tasks)
        executor = RunExecutor(run_lifecycle=lifecycle)
        result = executor.run_next_task(run)
        assert result is not None
        assert result.task_id == "task-1"
        lifecycle.mark_task_running.assert_called_once_with("task-1")

    def test_auto_approve_when_explicitly_enabled(self) -> None:
        """Pending tasks are auto-approved when config allows it."""
        tasks = [_make_task("task-1", TaskStatus.PENDING)]
        run = _make_run(tasks)
        lifecycle = _make_lifecycle_with_table(tasks)
        config = RunExecutorConfig(auto_approve_pending_tasks=True)
        executor = RunExecutor(config=config, run_lifecycle=lifecycle)
        result = executor.run_next_task(run)
        assert result is not None
        assert result.task_id == "task-1"
        lifecycle.approve_task.assert_called_once_with("task-1")
        lifecycle.mark_task_running.assert_called_once_with("task-1")

    def test_run_until_blocked_stops_when_approval_required(self) -> None:
        """run_until_blocked stops immediately when approval is needed."""
        tasks = [
            _make_task("task-1", TaskStatus.PENDING),
            _make_task("task-2", TaskStatus.PENDING),
        ]
        run = _make_run(tasks)
        lifecycle = _make_lifecycle_with_table(tasks)
        executor = RunExecutor(run_lifecycle=lifecycle)
        result = executor.run_until_blocked(run)
        assert result.approval_required is True
        assert len(result.pending_task_ids) == 2
        assert "task-1" in result.pending_task_ids
        assert "task-2" in result.pending_task_ids
        assert len(result.task_results) == 0

    def test_mixed_approval_status_only_runs_approved(self) -> None:
        """Only approved tasks run; pending tasks block further progress."""
        tasks = [
            _make_task("task-a", TaskStatus.APPROVED),
            _make_task("task-b", TaskStatus.PENDING),
        ]
        run = _make_run(tasks)
        lifecycle = _make_lifecycle_with_table(tasks)
        executor = RunExecutor(run_lifecycle=lifecycle)
        result1 = executor.run_next_task(run)
        assert result1 is not None
        assert result1.task_id == "task-a"
        result2 = executor.run_next_task(run)
        assert result2 is None  # task-b is pending, requires approval

    def test_dry_run_safe(self) -> None:
        """Verify executor never triggers real execution."""
        tasks = [_make_task("task-1", TaskStatus.APPROVED)]
        run = _make_run(tasks)
        lifecycle = _make_lifecycle_with_table(tasks)
        executor = RunExecutor(run_lifecycle=lifecycle)
        result = executor.run_next_task(run)
        assert result is not None
        assert result.execution_result.status == ExecutionStatus.SKIPPED

    def test_respects_task_order_with_approval(self) -> None:
        """Verify approved tasks are processed in insertion order."""
        tasks = [
            _make_task("task-a", TaskStatus.APPROVED),
            _make_task("task-b", TaskStatus.APPROVED),
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

    def test_run_executor_config_defaults(self) -> None:
        config = RunExecutorConfig()
        assert config.auto_approve_pending_tasks is False
        assert config.max_iterations_per_task == 1
        assert config.stop_on_debug is True
        assert config.stop_on_escalate is True

    # ------------------------------------------------------------------
    # Arbiter action handling
    # ------------------------------------------------------------------

    def test_stop_on_debug_returns_debug_required(self) -> None:
        """When arbiter returns DEBUG and stop_on_debug=True, executor stops."""
        tasks = [_make_task("task-1", TaskStatus.APPROVED)]
        run = _make_run(tasks)
        lifecycle = _make_lifecycle_with_table(tasks)
        mock_runner = MagicMock()
        mock_runner.run_iteration.return_value = _make_dry_fail(
            "task-1", ArbiterAction.DEBUG
        )
        executor = RunExecutor(
            run_lifecycle=lifecycle,
            iteration_runner=mock_runner,
        )
        result = executor.run_until_blocked(run)
        assert result.debug_required is True
        assert result.completed is False
        assert "DEBUG" in result.stopped_reason or "debug" in result.stopped_reason

    def test_stop_on_debug_false_continues(self) -> None:
        """When arbiter returns DEBUG and stop_on_debug=False, executor continues."""
        tasks = [
            _make_task("task-1", TaskStatus.APPROVED),
            _make_task("task-2", TaskStatus.APPROVED),
        ]
        run = _make_run(tasks)
        lifecycle = _make_lifecycle_with_table(tasks)
        mock_runner = MagicMock()
        mock_runner.run_iteration.side_effect = [
            _make_dry_fail("task-1", ArbiterAction.DEBUG),
            _make_dry_fail("task-2", ArbiterAction.APPROVE),
        ]
        config = RunExecutorConfig(stop_on_debug=False)
        executor = RunExecutor(
            config=config,
            run_lifecycle=lifecycle,
            iteration_runner=mock_runner,
        )
        result = executor.run_until_blocked(run)
        assert result.debug_required is False
        assert len(result.task_results) == 2

    def test_stop_on_escalate_returns_escalation_required(self) -> None:
        """When arbiter returns ESCALATE and stop_on_escalate=True, executor fails."""
        tasks = [_make_task("task-1", TaskStatus.APPROVED)]
        run = _make_run(tasks)
        lifecycle = _make_lifecycle_with_table(tasks)
        mock_runner = MagicMock()
        mock_runner.run_iteration.return_value = _make_dry_fail(
            "task-1", ArbiterAction.ESCALATE
        )
        executor = RunExecutor(
            run_lifecycle=lifecycle,
            iteration_runner=mock_runner,
        )
        result = executor.run_until_blocked(run)
        assert result.escalation_required is True
        assert result.failed is True
        assert (
            "ESCALATE" in result.stopped_reason or "escalate" in result.stopped_reason
        )

    def test_stop_on_escalate_false_continues(self) -> None:
        """When arbiter returns ESCALATE and stop_on_escalate=False, continues."""
        tasks = [
            _make_task("task-1", TaskStatus.APPROVED),
            _make_task("task-2", TaskStatus.APPROVED),
        ]
        run = _make_run(tasks)
        lifecycle = _make_lifecycle_with_table(tasks)
        mock_runner = MagicMock()
        mock_runner.run_iteration.side_effect = [
            _make_dry_fail("task-1", ArbiterAction.ESCALATE),
            _make_dry_fail("task-2", ArbiterAction.APPROVE),
        ]
        config = RunExecutorConfig(stop_on_escalate=False)
        executor = RunExecutor(
            config=config,
            run_lifecycle=lifecycle,
            iteration_runner=mock_runner,
        )
        result = executor.run_until_blocked(run)
        assert result.escalation_required is False
        assert result.failed is False
        assert len(result.task_results) == 2

    def test_retry_returns_retry_required(self) -> None:
        """When arbiter returns RETRY, executor reports retry_required."""
        tasks = [_make_task("task-1", TaskStatus.APPROVED)]
        run = _make_run(tasks)
        lifecycle = _make_lifecycle_with_table(tasks)
        mock_runner = MagicMock()
        mock_runner.run_iteration.return_value = _make_dry_fail(
            "task-1", ArbiterAction.RETRY
        )
        executor = RunExecutor(
            run_lifecycle=lifecycle,
            iteration_runner=mock_runner,
        )
        result = executor.run_until_blocked(run)
        assert result.retry_required is True
        assert result.completed is False
        assert "RETRY" in result.stopped_reason or "retry" in result.stopped_reason

    def test_stop_returns_failed(self) -> None:
        """When arbiter returns STOP, executor reports failed."""
        tasks = [_make_task("task-1", TaskStatus.APPROVED)]
        run = _make_run(tasks)
        lifecycle = _make_lifecycle_with_table(tasks)
        mock_runner = MagicMock()
        mock_runner.run_iteration.return_value = _make_dry_fail(
            "task-1", ArbiterAction.STOP
        )
        executor = RunExecutor(
            run_lifecycle=lifecycle,
            iteration_runner=mock_runner,
        )
        result = executor.run_until_blocked(run)
        assert result.failed is True
        assert "STOP" in result.stopped_reason or "stop" in result.stopped_reason

    # ------------------------------------------------------------------
    # Approval order (Policy A)
    # ------------------------------------------------------------------

    def test_policy_a_blocks_on_first_pending(self) -> None:
        """First PENDING task blocks even if later tasks are APPROVED."""
        tasks = [
            _make_task("task-1", TaskStatus.APPROVED),
            _make_task("task-2", TaskStatus.PENDING),
            _make_task("task-3", TaskStatus.APPROVED),
        ]
        run = _make_run(tasks)
        lifecycle = _make_lifecycle_with_table(tasks)
        mock_runner = MagicMock()
        mock_runner.run_iteration.return_value = _make_dry_fail(
            "task-1", ArbiterAction.APPROVE
        )
        executor = RunExecutor(
            run_lifecycle=lifecycle,
            iteration_runner=mock_runner,
        )
        result = executor.run_until_blocked(run)
        assert result.approval_required is True
        assert result.blocked_task_id == "task-2"
        assert len(result.task_results) == 1  # only task-1 ran

    def test_run_until_blocked_returns_blocked_task_id(self) -> None:
        """blocked_task_id identifies the first pending task blocking execution."""
        tasks = [
            _make_task("task-a", TaskStatus.PENDING),
            _make_task("task-b", TaskStatus.PENDING),
        ]
        run = _make_run(tasks)
        lifecycle = _make_lifecycle_with_table(tasks)
        executor = RunExecutor(run_lifecycle=lifecycle)
        result = executor.run_until_blocked(run)
        assert result.blocked_task_id == "task-a"
        assert result.approval_required is True

    def test_max_tasks_limit(self) -> None:
        """max_tasks parameter limits the number of tasks executed."""
        tasks = [
            _make_task("task-1", TaskStatus.APPROVED),
            _make_task("task-2", TaskStatus.APPROVED),
            _make_task("task-3", TaskStatus.APPROVED),
        ]
        run = _make_run(tasks)
        lifecycle = _make_lifecycle_with_table(tasks)
        mock_runner = MagicMock()
        mock_runner.run_iteration.return_value = _make_dry_fail(
            "any", ArbiterAction.APPROVE
        )
        executor = RunExecutor(
            run_lifecycle=lifecycle,
            iteration_runner=mock_runner,
        )
        result = executor.run_until_blocked(run, max_tasks=2)
        assert result.completed is False
        assert len(result.task_results) == 2
        assert "max_tasks" in result.stopped_reason


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def _make_dry_fail(task_id: str, arbiter_action: ArbiterAction) -> IterationRunResult:
    """Create a dry-run IterationRunResult with a specific arbiter action.

    The result is always ``passed=False`` (dry-run semantics).
    """
    return IterationRunResult(
        run_id="run-1",
        task_id=task_id,
        iteration=1,
        execution_result=ExecutionResult(
            status=ExecutionStatus.SKIPPED,
        ),
        quality_gate_result=QualityGateResult(
            task_id=task_id,
            arbiter_decision=ArbiterDecision(action=arbiter_action),
        ),
        passed=False,
    )
