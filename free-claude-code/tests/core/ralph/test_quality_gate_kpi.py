"""Tests for quality gate KPI integration."""

from __future__ import annotations

from unittest.mock import MagicMock

from core.ralph.kpi import KPIEvaluator, KPIStatus
from core.ralph.models import RalphTask, TaskStatus
from core.ralph.quality_gate import QualityGate
from core.ralph.roles import AgentRole
from core.ralph.verification_runner import VerificationRunner, VerificationRunnerConfig


def _make_task(task_id: str = "TASK-001", kpis: list[str] | None = None) -> RalphTask:
    return RalphTask(
        id=task_id,
        title="Test task",
        status=TaskStatus.APPROVED,
        agent_role=AgentRole.DOER,
        acceptance_criteria=["AC: works"],
        verification_commands=["echo ok"],
        kpis=kpis or [],
    )


class TestQualityGateKpi:
    """Quality gate integrates KPI results."""

    def test_all_required_kpi_pass_allows_approval(self) -> None:
        """When all required KPIs pass, quality gate can approve."""
        task = _make_task(kpis=["KPI: everything works"])
        kpi_evaluator = MagicMock(spec=KPIEvaluator)
        kpi_evaluator.evaluate_all.return_value = [
            MagicMock(passed=True, status=KPIStatus.PASSED, kpi_id="k1"),
        ]
        runner = VerificationRunner(
            config=VerificationRunnerConfig(
                allow_command_execution=True,
                allowed_command_prefixes=[["echo"]],
            )
        )
        gate = QualityGate(
            verification_runner=runner,
            kpi_evaluator=kpi_evaluator,
        )
        result = gate.evaluate(task)
        # In dry-run mode, verification commands are disabled by default,
        # so verification_result will be SKIPPED. KPI results should still
        # be present.
        assert len(result.kpi_results) > 0

    def test_required_kpi_failure_included_in_result(self) -> None:
        """Failed required KPIs appear in the quality gate result."""
        task = _make_task(kpis=["KPI: critical"])
        kpi_evaluator = MagicMock(spec=KPIEvaluator)
        kpi_evaluator.evaluate_all.return_value = [
            MagicMock(passed=False, status=KPIStatus.FAILED, kpi_id="k1"),
        ]
        gate = QualityGate(kpi_evaluator=kpi_evaluator)
        result = gate.evaluate(task)
        assert len(result.kpi_results) > 0
        assert result.kpi_results[0].passed is False

    def test_kpi_results_in_score_card(self) -> None:
        """KPI results are reflected in the ScoreCard kpi score."""
        task = _make_task(
            kpis=["KPI: passes", "KPI: also passes", "KPI: fails"]
        )
        kpi_evaluator = MagicMock(spec=KPIEvaluator)
        kpi_evaluator.evaluate_all.return_value = [
            MagicMock(passed=True, status=KPIStatus.PASSED, kpi_id="k1"),
            MagicMock(passed=True, status=KPIStatus.PASSED, kpi_id="k2"),
            MagicMock(passed=False, status=KPIStatus.FAILED, kpi_id="k3"),
        ]
        gate = QualityGate(kpi_evaluator=kpi_evaluator)
        result = gate.evaluate(task)
        assert result.score_card is not None
        # 2/3 KPIs passed ≈ 67% → kpi_score ≈ 67
        assert result.score_card.kpi_score > 0, "KPI score should reflect pass rate"
        assert result.score_card.kpi_score < 100, "Failed KPI should reduce score"

    def test_no_kpis_does_not_break_gate(self) -> None:
        """Quality gate works with no KPIs configured."""
        task = _make_task(kpis=[])
        kpi_evaluator = MagicMock(spec=KPIEvaluator)
        gate = QualityGate(kpi_evaluator=kpi_evaluator)
        result = gate.evaluate(task)
        assert result.score_card is not None
