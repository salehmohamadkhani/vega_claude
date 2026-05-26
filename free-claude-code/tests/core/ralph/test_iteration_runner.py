"""Tests for IterationRunner — single iteration orchestration."""

from __future__ import annotations

from unittest.mock import MagicMock

from core.ralph.execution import ExecutionMode, ExecutionResult, ExecutionStatus
from core.ralph.iteration_runner import IterationRunner, IterationRunResult
from core.ralph.models import RalphRun, RalphTask, RunStatus, TaskStatus
from core.ralph.quality_gate import QualityGateResult


def _make_run(**overrides: object) -> RalphRun:
    params: dict = {"id": "run-1", "goal_id": "goal-1", "status": RunStatus.RUNNING}
    params.update(overrides)
    return RalphRun(**params)


def _make_task(**overrides: object) -> RalphTask:
    params: dict = {
        "id": "task-1",
        "title": "Test Task",
        "description": "A test task",
        "status": TaskStatus.APPROVED,
    }
    params.update(overrides)
    return RalphTask(**params)


def _make_gate_result() -> QualityGateResult:
    """Return a minimal QualityGateResult for mock returns."""
    return QualityGateResult(
        task_id="task-1",
        summary="dry-run: no verification",
        all_passed=False,
    )


class TestIterationRunner:
    def setup_method(self) -> None:
        self.run = _make_run()
        self.task = _make_task()
        self.runner = IterationRunner()

    def test_dry_run_returns_structured_result(self) -> None:
        result = self.runner.run_iteration(self.run, self.task)
        assert isinstance(result, IterationRunResult)
        assert result.run_id == "run-1"
        assert result.task_id == "task-1"
        assert result.iteration == 1

    def test_dry_run_returns_not_passed(self) -> None:
        result = self.runner.run_iteration(self.run, self.task)
        assert result.passed is False
        assert "Dry-run" in result.failure_reason

    def test_no_provider_calls(self) -> None:
        """Verify iteration runner never calls providers."""
        result = self.runner.run_iteration(self.run, self.task)
        assert result.execution_result.mode == ExecutionMode.DRY_RUN
        assert result.execution_result.status == ExecutionStatus.SKIPPED

    def test_builds_prompt(self) -> None:
        mock_builder = MagicMock()
        mock_builder.build_task_prompt.return_value = "test prompt"
        runner = IterationRunner(prompt_builder=mock_builder)
        runner.run_iteration(self.run, self.task)
        mock_builder.build_task_prompt.assert_called_once()

    def test_calls_adapter(self) -> None:
        mock_adapter = MagicMock()
        mock_adapter.execute.return_value = ExecutionResult.skipped("dry")
        runner = IterationRunner(execution_adapter=mock_adapter)
        runner.run_iteration(self.run, self.task)
        mock_adapter.execute.assert_called_once()

    def test_calls_quality_gate(self) -> None:
        mock_gate = MagicMock()
        mock_gate.evaluate.return_value = _make_gate_result()
        runner = IterationRunner(quality_gate=mock_gate)
        runner.run_iteration(self.run, self.task)
        mock_gate.evaluate.assert_called_once()

    def test_creates_checkpoint(self) -> None:
        mock_cp = MagicMock()
        runner = IterationRunner(checkpoint_store=mock_cp)
        runner.run_iteration(self.run, self.task)
        mock_cp.save_checkpoint.assert_called_once()

    def test_updates_run_table(self) -> None:
        mock_table = MagicMock()
        mock_table.get_entry.return_value = MagicMock()
        runner = IterationRunner(run_table=mock_table)
        runner.run_iteration(self.run, self.task)
        assert mock_table.get_entry.called
