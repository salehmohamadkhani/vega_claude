"""Quality gate orchestrator for Ralph Runtime.

Coordinates verification planning, command execution, scoring, critic
review, loop guard evaluation, and arbiter resolution into a single
structured result.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .arbiter import ArbiterDecision, ArbiterEngine
from .critic import CriticEngine, CriticReview
from .loop_guard import LoopGuard, LoopGuardDecision
from .models import RalphTask, TaskStatus
from .scoring import HallucinationRisk, ScoreCard
from .verification import (
    VerificationPlan,
    VerificationResult,
    VerificationStatus,
    build_verification_plan_for_task,
)
from .verification_runner import VerificationRunner


@dataclass
class QualityGateResult:
    """Structured outcome of running a full quality gate."""

    task_id: str = ""
    task_title: str = ""
    verification_plan: VerificationPlan = field(default_factory=VerificationPlan)
    verification_result: VerificationResult = field(default_factory=VerificationResult)
    score_card: ScoreCard = field(default_factory=ScoreCard)
    critic_reviews: list[CriticReview] = field(default_factory=list)
    loop_guard_decision: LoopGuardDecision = field(default_factory=LoopGuardDecision)
    arbiter_decision: ArbiterDecision = field(default_factory=ArbiterDecision)
    final_status: TaskStatus = TaskStatus.PENDING
    summary: str = ""
    all_passed: bool = False

    def is_approved(self) -> bool:
        """Return True if the arbiter approved the task."""
        return self.arbiter_decision.action.value == "approve"


def _compute_score_from_verification(
    verification_result: VerificationResult,
) -> ScoreCard:
    """Build a ScoreCard from verification results.

    Scores are derived from pass rates converted to 0-100 scale.
    """
    cmd_results = verification_result.command_results
    smoke_results = verification_result.smoke_results

    passed_cmd = sum(1 for v in cmd_results.values() if v)
    total_cmd = len(cmd_results)
    passed_smoke = sum(1 for v in smoke_results.values() if v)
    total_smoke = len(smoke_results)

    impl_score = _rate_to_score(passed_cmd, total_cmd)
    test_score = _rate_to_score(passed_smoke, total_smoke)

    # KPI score: what fraction of defined KPIs passed
    kpi_results = verification_result.kpi_results
    passed_kpi = sum(1 for v in kpi_results.values() if v)
    total_kpi = len(kpi_results)
    kpi_score = _rate_to_score(passed_kpi, total_kpi)

    # Risk score: inverse of pass rate, higher = more risk
    total_checks = total_cmd + total_smoke + total_kpi
    total_passed = passed_cmd + passed_smoke + passed_kpi
    risk_score = (
        100 - _rate_to_score(total_passed, total_checks) if total_checks > 0 else 0
    )

    # Confidence: how many checks were actually run vs expected
    confidence_score = _rate_to_score(total_checks, max(total_checks, 1))

    # Hallucination risk: if nothing passed, HIGH; if most passed, LOW
    if total_checks == 0:
        h_risk = HallucinationRisk.LOW
    elif total_passed == 0:
        h_risk = HallucinationRisk.HIGH
    elif total_passed / total_checks < 0.5:
        h_risk = HallucinationRisk.MEDIUM
    else:
        h_risk = HallucinationRisk.LOW

    return ScoreCard(
        implementation_score=impl_score,
        test_score=test_score,
        kpi_score=kpi_score,
        risk_score=risk_score,
        confidence_score=confidence_score,
        hallucination_risk=h_risk,
        notes=[f"Verification: {total_passed}/{total_checks} checks passed"],
    )


def _rate_to_score(passed: int, total: int) -> int:
    """Convert a pass rate (passed/total) to a 0-100 integer score."""
    if total <= 0:
        return 0
    return round(passed / total * 100)


class QualityGate:
    """Orchestrates the full quality gate pipeline for a task.

    Pipeline::

        VerificationPlan → VerificationRunner → Scoring → CriticReview
        → LoopGuard → Arbiter → QualityGateResult

    Usage::

        gate = QualityGate(verification_runner, critic, arbiter)
        result = gate.evaluate(task, loop_guard)
    """

    def __init__(
        self,
        verification_runner: VerificationRunner | None = None,
        critic: CriticEngine | None = None,
        arbiter: ArbiterEngine | None = None,
    ) -> None:
        self._runner = verification_runner or VerificationRunner()
        self._critic = critic or CriticEngine()
        self._arbiter = arbiter or ArbiterEngine()

    def evaluate(
        self,
        task: RalphTask,
        loop_guard: LoopGuard | None = None,
        score_card: ScoreCard | None = None,
        retry_count: int = 0,
        critic_rejection_count: int = 0,
    ) -> QualityGateResult:
        """Run the full quality gate pipeline for a single task.

        Parameters
        ----------
        task:
            The task to evaluate.
        loop_guard:
            Optional LoopGuard for monitoring iteration health.
        score_card:
            Optional pre-built ScoreCard. If omitted, one is derived
            from the verification results.
        retry_count:
            How many times this task has been retried.
        critic_rejection_count:
            How many times the critic has rejected this task.

        Returns
        -------
        A QualityGateResult with all intermediate and final decisions.
        """
        # Step 1: Build verification plan from task
        plan = build_verification_plan_for_task(task)

        # Step 2: Run the verification plan
        verification_result = self._runner.run_plan(plan)

        # Step 3: Build or use provided score card
        if score_card is None:
            score_card = _compute_score_from_verification(verification_result)

        # Step 4: Critic review of verification + scoring
        verifier_review = self._critic.review_verification(
            verification_result,
            acceptance_criteria=task.acceptance_criteria,
        )
        scoring_review = self._critic.review_scoring(score_card)

        # Step 5: Loop guard evaluation
        if loop_guard is not None:
            if verification_result.status == VerificationStatus.FAILED:
                loop_guard.record_verification_failure(
                    verification_result.failure_reason or "Verification failed"
                )
            loop_guard_decision = loop_guard.evaluate(current_iteration=retry_count + 1)
        else:
            loop_guard_decision = LoopGuardDecision()

        # Step 6: Arbiter decision
        combined_review = CriticReview(
            approved=verifier_review.approved and scoring_review.approved,
            decision=(
                verifier_review.decision
                if not verifier_review.approved
                else scoring_review.decision
            ),
            score_card=score_card,
            passed_command_count=verifier_review.passed_command_count,
            total_command_count=verifier_review.total_command_count,
            passed_smoke_count=verifier_review.passed_smoke_count,
            total_smoke_count=verifier_review.total_smoke_count,
            failed_criteria=(verifier_review.failed_criteria + scoring_review.warnings),
            warnings=verifier_review.warnings + scoring_review.warnings,
        )

        arbiter_decision = self._arbiter.decide(
            critic_review=combined_review,
            loop_guard_decision=loop_guard_decision,
            score_card=score_card,
            retry_count=retry_count,
            critic_rejection_count=critic_rejection_count,
        )

        # Step 7: Determine final status
        all_passed = (
            verification_result.status == VerificationStatus.PASSED
            and combined_review.approved
            and arbiter_decision.action.value == "approve"
        )

        if arbiter_decision.action.value == "approve":
            final_status = TaskStatus.PASSED
        elif arbiter_decision.action.value == "stop":
            final_status = TaskStatus.FAILED
        else:
            final_status = TaskStatus.NEEDS_FIX

        summary_parts = [
            f"gate={arbiter_decision.action.value}",
            f"verification={verification_result.status.value}",
            f"score={score_card.final_weighted_score():.0f}",
        ]

        return QualityGateResult(
            task_id=task.id,
            task_title=task.title,
            verification_plan=plan,
            verification_result=verification_result,
            score_card=score_card,
            critic_reviews=[verifier_review, scoring_review],
            loop_guard_decision=loop_guard_decision,
            arbiter_decision=arbiter_decision,
            final_status=final_status,
            summary=" | ".join(summary_parts),
            all_passed=all_passed,
        )
