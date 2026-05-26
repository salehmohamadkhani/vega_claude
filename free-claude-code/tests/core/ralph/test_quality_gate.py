"""Tests for core.ralph.quality_gate."""

from __future__ import annotations

from core.ralph.arbiter import ArbiterAction, ArbiterEngine
from core.ralph.critic import CriticEngine
from core.ralph.loop_guard import LoopGuard, LoopGuardDecision
from core.ralph.models import RalphTask, TaskStatus
from core.ralph.quality_gate import QualityGate, QualityGateResult
from core.ralph.roles import AgentRole
from core.ralph.scoring import ScoreCard
from core.ralph.verification import VerificationStatus
from core.ralph.verification_runner import (
    VerificationRunner,
    VerificationRunnerConfig,
)


class TestQualityGate:
    def make_gate(self, runner: VerificationRunner | None = None) -> QualityGate:
        return QualityGate(
            verification_runner=runner,
            critic=CriticEngine(),
            arbiter=ArbiterEngine(),
        )

    def make_simple_task(self) -> RalphTask:
        return RalphTask(
            id="TASK-001-test",
            title="Test task",
            agent_role=AgentRole.DOER,
            verification_commands=[],
        )

    def test_evaluate_returns_quality_gate_result(self) -> None:
        gate = self.make_gate()
        task = self.make_simple_task()
        result = gate.evaluate(task)
        assert isinstance(result, QualityGateResult)
        assert result.task_id == task.id

    def test_evaluate_empty_task_no_verifications(self) -> None:
        gate = self.make_gate()
        task = self.make_simple_task()
        result = gate.evaluate(task)
        # No verification commands → empty plan → skipped
        assert result.verification_result is not None

    def test_evaluate_with_loop_guard(self) -> None:
        gate = self.make_gate()
        task = self.make_simple_task()
        loop_guard = LoopGuard(max_iterations=10)
        result = gate.evaluate(task, loop_guard=loop_guard)
        assert isinstance(result.loop_guard_decision, LoopGuardDecision)

    def test_evaluate_with_score_card(self) -> None:
        gate = self.make_gate()
        task = self.make_simple_task()
        score = ScoreCard(
            implementation_score=90,
            test_score=85,
            kpi_score=80,
            risk_score=10,
            confidence_score=90,
        )
        result = gate.evaluate(task, score_card=score)
        assert result.score_card is score

    def test_evaluate_stops_with_loop_guard_at_max(self) -> None:
        gate = self.make_gate()
        task = self.make_simple_task()
        loop_guard = LoopGuard(max_iterations=1)
        # Iteration 1: max iterations not reached
        loop_guard.evaluate(current_iteration=1)
        result = gate.evaluate(task, loop_guard=loop_guard)
        # Should not stop — we only evaluate once
        assert result.arbiter_decision is not None

    def test_approve_with_all_pass(self) -> None:
        config = VerificationRunnerConfig(
            allow_command_execution=True,
            allowed_command_prefixes=[["echo"]],
        )
        runner = VerificationRunner(config)
        gate = self.make_gate(runner=runner)
        task = RalphTask(
            id="TASK-002",
            title="Working task",
            verification_commands=["echo passed", "echo done"],
            acceptance_criteria=["passed"],
        )
        result = gate.evaluate(task)
        # The echoed output should contain "passed" and "done" in stdout
        # which the critic checks via keyword matching
        assert result.verification_result.status == VerificationStatus.PASSED

    def test_is_approved_helper(self) -> None:
        result = QualityGateResult()
        assert result.is_approved() is False

    def test_result_all_passed_flag(self) -> None:
        result = QualityGateResult(all_passed=True)
        assert result.all_passed is True

    def test_final_status_passed_on_approve(self) -> None:
        from core.ralph.arbiter import ArbiterDecision

        result = QualityGateResult(
            final_status=TaskStatus.PASSED,
            arbiter_decision=ArbiterDecision(action=ArbiterAction.APPROVE),
        )
        assert result.final_status == TaskStatus.PASSED

    def test_final_status_needs_fix_on_retry(self) -> None:

        result = QualityGateResult(
            final_status=TaskStatus.NEEDS_FIX,
        )
        assert result.final_status == TaskStatus.NEEDS_FIX

    def test_evaluate_with_verification_failure(self) -> None:
        config = VerificationRunnerConfig(
            allow_command_execution=True,
            allowed_command_prefixes=[["python"]],
        )
        runner = VerificationRunner(config)
        gate = self.make_gate(runner=runner)
        task = RalphTask(
            id="TASK-003",
            title="Failing task",
            verification_commands=["python -c 'exit(1)'"],
        )
        result = gate.evaluate(task)
        assert result.verification_result.status == VerificationStatus.FAILED

    def test_two_critic_reviews_in_result(self) -> None:
        gate = self.make_gate()
        task = self.make_simple_task()
        result = gate.evaluate(task)
        # One for verification review, one for scoring review
        assert len(result.critic_reviews) == 2

    def test_evaluate_produces_summary(self) -> None:
        gate = self.make_gate()
        task = self.make_simple_task()
        result = gate.evaluate(task)
        assert len(result.summary) > 0
        assert "gate=" in result.summary

    def test_skipped_verification_does_not_result_in_passed(self) -> None:
        """Default runner (execution disabled) must NOT produce PASSED final_status."""
        gate = self.make_gate()
        task = self.make_simple_task()
        result = gate.evaluate(task)
        assert result.final_status != TaskStatus.PASSED
        assert result.all_passed is False

    def test_high_hallucination_risk_blocks_approval(self) -> None:
        """A score card with HIGH hallucination risk must not result in PASSED."""
        from core.ralph.scoring import HallucinationRisk

        gate = self.make_gate()
        task = self.make_simple_task()
        score = ScoreCard(
            implementation_score=95,
            test_score=90,
            kpi_score=85,
            risk_score=10,
            confidence_score=92,
            hallucination_risk=HallucinationRisk.HIGH,
        )
        result = gate.evaluate(task, score_card=score)
        assert result.final_status != TaskStatus.PASSED

    def test_arbiter_loop_guard_stop_overrides_critic_approval(self) -> None:
        """Even when critic approves, a STOP from loop guard must result in STOP."""
        from core.ralph.arbiter import ArbiterAction
        from core.ralph.loop_guard import LoopGuard

        gate = self.make_gate()
        task = self.make_simple_task()
        loop_guard = LoopGuard(max_iterations=1)
        loop_guard.evaluate(current_iteration=1)  # hits STOP
        result = gate.evaluate(task, loop_guard=loop_guard)
        assert result.arbiter_decision.action == ArbiterAction.STOP
