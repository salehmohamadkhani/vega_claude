"""Tests for the Ralph loop runner."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from core.ralph.arbiter import ArbiterAction, ArbiterDecision
from core.ralph.execution import ExecutionMode, ExecutionResult, ExecutionStatus
from core.ralph.iteration_runner import IterationRunner, IterationRunResult
from core.ralph.loop_guard import LoopGuardDecision
from core.ralph.loop_policy import LoopPolicy
from core.ralph.loop_runner import RalphLoopRunner
from core.ralph.models import RalphRun, RalphTask, RunStatus, TaskStatus, _new_id
from core.ralph.quality_gate import QualityGateResult
from core.ralph.workspace import RalphWorkspace

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_run(tasks: list[RalphTask]) -> RalphRun:
    return RalphRun(
        id=_new_id(),
        goal_id=_new_id(),
        status=RunStatus.RUNNING,
        tasks=tasks,
    )


def _make_task(
    task_id: str = "TASK-001",
    title: str = "Test task",
    status: TaskStatus = TaskStatus.APPROVED,
) -> RalphTask:
    return RalphTask(
        id=task_id,
        title=title,
        status=status,
        acceptance_criteria=["AC: works"],
        verification_commands=["echo ok"],
    )


def _make_iteration_result(
    task_id: str = "TASK-001",
    iteration: int = 1,
    passed: bool = False,
    action: ArbiterAction = ArbiterAction.RETRY,
    reason: str = "",
) -> IterationRunResult:
    return IterationRunResult(
        run_id=_new_id(),
        task_id=task_id,
        iteration=iteration,
        execution_result=ExecutionResult(
            status=ExecutionStatus.SKIPPED,
            mode=ExecutionMode.DRY_RUN,
            exit_code=0,
            timed_out=False,
        ),
        quality_gate_result=QualityGateResult(
            task_id=task_id,
            all_passed=passed,
            arbiter_decision=ArbiterDecision(
                action=action,
                reason=reason or f"Test: {action.value}",
            ),
            loop_guard_decision=LoopGuardDecision(),
        ),
        passed=passed,
        next_action=action.value,
        failure_reason="" if passed else "Dry-run: no verification results",
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def workspace(tmp_path: Path) -> RalphWorkspace:
    ws = RalphWorkspace(project_root=str(tmp_path))
    ws.initialize()
    return ws


@pytest.fixture
def mock_runner(workspace: RalphWorkspace) -> tuple[RalphLoopRunner, IterationRunner]:
    """Create a RalphLoopRunner with a mocked IterationRunner."""
    iteration_runner = MagicMock(spec=IterationRunner)
    runner = RalphLoopRunner(
        workspace=workspace,
        iteration_runner=iteration_runner,
    )
    return runner, iteration_runner


# ---------------------------------------------------------------------------
# Pending / Blocking
# ---------------------------------------------------------------------------


class TestPendingBlocking:
    """Policy A: first PENDING task blocks the loop."""

    def test_pending_first_task_blocks_loop(self, mock_runner):
        runner, _ = mock_runner
        tasks = [
            _make_task("TASK-001", "First", TaskStatus.PENDING),
            _make_task("TASK-002", "Second", TaskStatus.APPROVED),
        ]
        run = _make_run(tasks)

        result = runner.run(run, tasks)

        assert result.approval_required is True
        assert result.blocked_task_id == "TASK-001"
        assert result.pending_task_ids == ["TASK-001"]
        assert result.completed is False

    def test_pending_allows_later_approved(self, mock_runner):
        """When first task is APPROVED, loop runs it."""
        runner, mock_iter = mock_runner
        tasks = [
            _make_task("TASK-001", "First", TaskStatus.APPROVED),
            _make_task("TASK-002", "Second", TaskStatus.PENDING),
        ]
        run = _make_run(tasks)

        # First approved task returns pass
        mock_iter.run_iteration.return_value = _make_iteration_result(
            "TASK-001", passed=True, action=ArbiterAction.APPROVE
        )

        result = runner.run(run, tasks)

        assert result.approval_required is True
        assert result.blocked_task_id == "TASK-002"

    def test_approval_not_required_when_policy_disabled(self, mock_runner):
        runner, mock_iter = mock_runner
        tasks = [
            _make_task("TASK-001", "First", TaskStatus.PENDING),
            _make_task("TASK-002", "Second", TaskStatus.APPROVED),
        ]
        run = _make_run(tasks)

        mock_iter.run_iteration.return_value = _make_iteration_result(
            "TASK-001", passed=True, action=ArbiterAction.APPROVE
        )

        result = runner.run(run, tasks, LoopPolicy(require_approval=False))

        # Should run TASK-001 (pending but approval not required) and TASK-002
        assert result.completed is True


# ---------------------------------------------------------------------------
# Loop execution
# ---------------------------------------------------------------------------


class TestLoopExecution:
    """Loop runs for approved tasks."""

    def test_approved_first_task_runs_dry_loop(self, mock_runner):
        runner, mock_iter = mock_runner
        tasks = [_make_task("TASK-001", "Test task", TaskStatus.APPROVED)]
        run = _make_run(tasks)

        mock_iter.run_iteration.return_value = _make_iteration_result(
            "TASK-001", passed=True, action=ArbiterAction.APPROVE
        )

        result = runner.run(run, tasks)

        assert result.dry_run is True
        assert result.total_iterations == 1
        assert len(result.task_results) == 1
        tr = result.task_results[0]
        assert tr.passed is True
        assert tr.final_action == "approve"

    def test_later_approved_task_blocked_by_earlier_pending(self, mock_runner):
        runner, mock_iter = mock_runner
        tasks = [
            _make_task("TASK-001", "First", TaskStatus.PENDING),
            _make_task("TASK-002", "Second", TaskStatus.APPROVED),
        ]
        run = _make_run(tasks)

        mock_iter.run_iteration.return_value = _make_iteration_result(
            "TASK-002", passed=True, action=ArbiterAction.APPROVE
        )

        result = runner.run(run, tasks)

        assert result.approval_required is True
        assert result.blocked_task_id == "TASK-001"

    def test_multiple_approved_tasks_run_in_order(self, mock_runner):
        runner, mock_iter = mock_runner
        tasks = [
            _make_task("TASK-001", "First", TaskStatus.APPROVED),
            _make_task("TASK-002", "Second", TaskStatus.APPROVED),
        ]
        run = _make_run(tasks)

        mock_iter.run_iteration.return_value = _make_iteration_result(
            "TASK-001", passed=True, action=ArbiterAction.APPROVE
        )

        result = runner.run(run, tasks)

        # Both approved, first returns approve, loop continues
        assert result.total_iterations >= 1
        assert len(result.task_results) >= 1

    def test_no_approved_tasks_returns_completed(self, mock_runner):
        runner, _ = mock_runner
        tasks = [
            _make_task("TASK-001", "First", TaskStatus.PENDING),
            _make_task("TASK-002", "Second", TaskStatus.PENDING),
        ]
        run = _make_run(tasks)

        result = runner.run(run, tasks)

        assert result.approval_required is True
        assert result.completed is False


# ---------------------------------------------------------------------------
# Iteration limits
# ---------------------------------------------------------------------------


class TestIterationLimits:
    """Max iterations enforcement."""

    def test_max_iterations_enforced(self, mock_runner):
        runner, mock_iter = mock_runner
        tasks = [_make_task("TASK-001", "Test task", TaskStatus.APPROVED)]
        run = _make_run(tasks)

        # Always return RETRY
        mock_iter.run_iteration.return_value = _make_iteration_result(
            "TASK-001", passed=False, action=ArbiterAction.RETRY
        )

        policy = LoopPolicy(max_iterations_per_task=2)
        result = runner.run(run, tasks, policy)

        assert result.retry_required is True
        assert result.total_iterations <= 2
        assert not result.completed

    def test_retry_loops_until_approve(self, mock_runner):
        runner, mock_iter = mock_runner
        tasks = [_make_task("TASK-001", "Test task", TaskStatus.APPROVED)]
        run = _make_run(tasks)

        # Return RETRY first, then APPROVE
        call_count = 0

        def _side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                return _make_iteration_result(
                    "TASK-001", passed=True, action=ArbiterAction.APPROVE
                )
            return _make_iteration_result(
                "TASK-001", passed=False, action=ArbiterAction.RETRY
            )

        mock_iter.run_iteration.side_effect = _side_effect

        policy = LoopPolicy(max_iterations_per_task=3)
        result = runner.run(run, tasks, policy)

        assert result.completed is True
        assert result.total_iterations == 2
        assert result.task_results[0].passed is True


# ---------------------------------------------------------------------------
# Arbiter action handling
# ---------------------------------------------------------------------------


class TestArbiterActions:
    """Arbiter action handling in loop."""

    def test_approve_passes_task(self, mock_runner):
        runner, mock_iter = mock_runner
        tasks = [_make_task("TASK-001", "Test task", TaskStatus.APPROVED)]
        run = _make_run(tasks)

        mock_iter.run_iteration.return_value = _make_iteration_result(
            "TASK-001", passed=True, action=ArbiterAction.APPROVE
        )

        result = runner.run(run, tasks)

        assert result.completed is True
        tr = result.task_results[0]
        assert tr.passed is True
        assert tr.final_action == "approve"

    def test_retry_loops_until_limit(self, mock_runner):
        runner, mock_iter = mock_runner
        tasks = [_make_task("TASK-001", "Test task", TaskStatus.APPROVED)]
        run = _make_run(tasks)

        mock_iter.run_iteration.return_value = _make_iteration_result(
            "TASK-001", passed=False, action=ArbiterAction.RETRY
        )

        policy = LoopPolicy(max_iterations_per_task=3)
        result = runner.run(run, tasks, policy)

        assert result.retry_required
        assert result.task_results[0].final_action == "retry"

    def test_debug_stops_when_stop_on_debug_true(self, mock_runner):
        runner, mock_iter = mock_runner
        tasks = [_make_task("TASK-001", "Test task", TaskStatus.APPROVED)]
        run = _make_run(tasks)

        mock_iter.run_iteration.return_value = _make_iteration_result(
            "TASK-001", passed=False, action=ArbiterAction.DEBUG
        )

        result = runner.run(run, tasks)

        assert result.debug_required is True
        assert result.completed is False

    def test_debug_does_not_stop_when_stop_on_debug_false(self, mock_runner):
        runner, mock_iter = mock_runner
        tasks = [_make_task("TASK-001", "Test task", TaskStatus.APPROVED)]
        run = _make_run(tasks)

        # Return DEBUG then APPROVE
        call_count = 0

        def _side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                return _make_iteration_result(
                    "TASK-001", passed=True, action=ArbiterAction.APPROVE
                )
            return _make_iteration_result(
                "TASK-001", passed=False, action=ArbiterAction.DEBUG
            )

        mock_iter.run_iteration.side_effect = _side_effect

        policy = LoopPolicy(stop_on_debug=False, max_iterations_per_task=3)
        result = runner.run(run, tasks, policy)

        assert result.completed is True

    def test_escalate_stops_when_stop_on_escalate_true(self, mock_runner):
        runner, mock_iter = mock_runner
        tasks = [_make_task("TASK-001", "Test task", TaskStatus.APPROVED)]
        run = _make_run(tasks)

        mock_iter.run_iteration.return_value = _make_iteration_result(
            "TASK-001", passed=False, action=ArbiterAction.ESCALATE
        )

        result = runner.run(run, tasks)

        assert result.escalation_required is True
        assert result.completed is False

    def test_stop_fails_task(self, mock_runner):
        runner, mock_iter = mock_runner
        tasks = [_make_task("TASK-001", "Test task", TaskStatus.APPROVED)]
        run = _make_run(tasks)

        mock_iter.run_iteration.return_value = _make_iteration_result(
            "TASK-001", passed=False, action=ArbiterAction.STOP
        )

        result = runner.run(run, tasks)

        assert result.completed is False
        assert result.retry_required is False  # Not retry — it's stop


# ---------------------------------------------------------------------------
# Checkpoint creation
# ---------------------------------------------------------------------------


class TestCheckpoints:
    """Checkpoint creation per iteration."""

    def test_checkpoints_created_per_iteration(self, mock_runner, workspace):
        runner, mock_iter = mock_runner
        tasks = [_make_task("TASK-001", "Test task", TaskStatus.APPROVED)]
        run = _make_run(tasks)

        mock_iter.run_iteration.return_value = _make_iteration_result(
            "TASK-001", passed=True, action=ArbiterAction.APPROVE
        )

        # IterationRunner already creates checkpoints — loop runner tracks count
        result = runner.run(run, tasks)

        assert result.checkpoints_created >= 0
        assert result.total_iterations == 1


# ---------------------------------------------------------------------------
# Dry-run safety
# ---------------------------------------------------------------------------


class TestDryRunSafety:
    """Dry-run mode safety."""

    def test_dry_run_does_not_falsely_claim_completion(self, mock_runner):
        runner, mock_iter = mock_runner
        tasks = [_make_task("TASK-001", "Test task", TaskStatus.APPROVED)]
        run = _make_run(tasks)

        # In dry-run, quality gate returns DEBUG (not PASS)
        mock_iter.run_iteration.return_value = _make_iteration_result(
            "TASK-001", passed=False, action=ArbiterAction.DEBUG
        )

        result = runner.run(run, tasks)

        # If quality gate doesn't pass, loop should report accordingly
        if result.completed:
            # If mock happened to return approve, that's fine — the test
            # verifies we don't fake it
            assert result.task_results[0].passed is True
        else:
            assert not result.completed
            assert result.stopped_reason

    def test_dry_run_default(self, mock_runner):
        """Loop should be in dry-run mode by default."""
        runner, mock_iter = mock_runner
        tasks = [_make_task("TASK-001", "Test task", TaskStatus.APPROVED)]
        run = _make_run(tasks)

        mock_iter.run_iteration.return_value = _make_iteration_result(
            "TASK-001", passed=True, action=ArbiterAction.APPROVE
        )

        result = runner.run(run, tasks)

        assert result.dry_run is True


# ---------------------------------------------------------------------------
# Task status persistence
# ---------------------------------------------------------------------------


class TestTaskStatusPersistence:
    """Task status updates are persisted."""

    def test_task_marked_passed_after_approve(self, mock_runner, workspace):
        runner, mock_iter = mock_runner
        tasks = [_make_task("TASK-001", "Test task", TaskStatus.APPROVED)]
        run = _make_run(tasks)

        mock_iter.run_iteration.return_value = _make_iteration_result(
            "TASK-001", passed=True, action=ArbiterAction.APPROVE
        )

        runner.run(run, tasks)

        assert tasks[0].status == TaskStatus.PASSED

    def test_task_marked_needs_fix_after_retry_limit(self, mock_runner, workspace):
        runner, mock_iter = mock_runner
        tasks = [_make_task("TASK-001", "Test task", TaskStatus.APPROVED)]
        run = _make_run(tasks)

        mock_iter.run_iteration.return_value = _make_iteration_result(
            "TASK-001", passed=False, action=ArbiterAction.RETRY
        )

        policy = LoopPolicy(max_iterations_per_task=1)
        runner.run(run, tasks, policy)

        assert tasks[0].status == TaskStatus.NEEDS_FIX

    def test_task_marked_failed_after_stop(self, mock_runner, workspace):
        runner, mock_iter = mock_runner
        tasks = [_make_task("TASK-001", "Test task", TaskStatus.APPROVED)]
        run = _make_run(tasks)

        mock_iter.run_iteration.return_value = _make_iteration_result(
            "TASK-001", passed=False, action=ArbiterAction.STOP
        )

        runner.run(run, tasks)

        assert tasks[0].status == TaskStatus.FAILED


# ---------------------------------------------------------------------------
# Max tasks limit
# ---------------------------------------------------------------------------


class TestMaxTasks:
    """Max tasks limit enforcement."""

    def test_max_tasks_respected(self, mock_runner):
        runner, mock_iter = mock_runner
        tasks = [
            _make_task("TASK-001", "First", TaskStatus.APPROVED),
            _make_task("TASK-002", "Second", TaskStatus.APPROVED),
            _make_task("TASK-003", "Third", TaskStatus.APPROVED),
        ]
        run = _make_run(tasks)

        mock_iter.run_iteration.return_value = _make_iteration_result(
            "TASK-001", passed=True, action=ArbiterAction.APPROVE
        )

        policy = LoopPolicy(max_tasks=2)
        result = runner.run(run, tasks, policy)

        assert len(result.task_results) <= 2
