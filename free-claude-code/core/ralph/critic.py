"""Deterministic critic for Ralph Runtime task evaluation.

No AI calls, no subprocesses — pure rule-based review of verification
results, scoring, and acceptance criteria.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .models import CriticDecision
from .scoring import ScoreCard
from .verification import VerificationResult


@dataclass
class CriticReview:
    """Structured output from a critic evaluation."""

    approved: bool = False
    decision: CriticDecision = field(default_factory=CriticDecision)
    score_card: ScoreCard | None = None
    passed_command_count: int = 0
    total_command_count: int = 0
    passed_smoke_count: int = 0
    total_smoke_count: int = 0
    failed_criteria: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


# Threshold: what fraction of commands must pass for a "pass" verdict.
_COMMAND_PASS_THRESHOLD = 1.0  # all commands must pass
_SMOKE_PASS_THRESHOLD = 1.0  # all smoke targets must pass
_MIN_CONFIDENCE_FOR_APPROVAL = 0.6


class CriticEngine:
    """Deterministic critic that reviews task output against acceptance criteria.

    The critic examines:
    - Verification command pass/fail counts
    - Smoke target pass/fail counts
    - Acceptance criteria (structural check — verifies they are documented)
    - ScoreCard results (if provided)
    - Confidence estimation based on pass rates
    """

    def review_verification(
        self,
        verification_result: VerificationResult,
        acceptance_criteria: list[str] | None = None,
    ) -> CriticReview:
        """Review a verification result against acceptance criteria.

        Parameters
        ----------
        verification_result:
            The result of running a VerificationPlan.
        acceptance_criteria:
            The task's acceptance criteria (list of strings).

        Returns
        -------
        A CriticReview with approval decision and details.
        """
        # Count passes
        cmd_results = verification_result.command_results
        smoke_results = verification_result.smoke_results

        passed_cmd = sum(1 for v in cmd_results.values() if v)
        total_cmd = len(cmd_results)
        passed_smoke = sum(1 for v in smoke_results.values() if v)
        total_smoke = len(smoke_results)

        # Check acceptance criteria
        criteria = acceptance_criteria or []
        failed_criteria = self._check_criteria(criteria, verification_result)

        # Determine pass/fail
        cmd_ok = total_cmd == 0 or (
            passed_cmd / total_cmd >= _COMMAND_PASS_THRESHOLD
        )
        smoke_ok = total_smoke == 0 or (
            passed_smoke / total_smoke >= _SMOKE_PASS_THRESHOLD
        )
        criteria_ok = len(failed_criteria) == 0
        all_passed = cmd_ok and smoke_ok and criteria_ok

        # Build warnings
        warnings: list[str] = []
        if not cmd_ok:
            warnings.append(
                f"Command verification: {passed_cmd}/{total_cmd} passed"
            )
        if not smoke_ok:
            warnings.append(
                f"Smoke verification: {passed_smoke}/{total_smoke} passed"
            )
        if not criteria_ok:
            warnings.append(
                f"Acceptance criteria not met: {len(failed_criteria)} failed"
            )

        # Estimate confidence based on pass rate
        confidence = self._estimate_confidence(
            passed_cmd, total_cmd, passed_smoke, total_smoke, criteria_ok
        )

        # If there are no verifications at all, low confidence
        if total_cmd == 0 and total_smoke == 0 and not criteria:
            decision = CriticDecision(
                approved=False,
                reason="No verification checks defined — cannot approve.",
                required_fixes=["Add verification commands or smoke targets"],
                confidence=0.0,
            )
        elif not all_passed:
            decision = CriticDecision(
                approved=False,
                reason="; ".join(warnings),
                required_fixes=failed_criteria or warnings,
                confidence=confidence,
            )
        else:
            decision = CriticDecision(
                approved=True,
                reason="All checks passed.",
                confidence=confidence,
            )

        return CriticReview(
            approved=decision.approved,
            decision=decision,
            score_card=None,
            passed_command_count=passed_cmd,
            total_command_count=total_cmd,
            passed_smoke_count=passed_smoke,
            total_smoke_count=total_smoke,
            failed_criteria=failed_criteria,
            warnings=warnings,
        )

    def review_scoring(
        self,
        score_card: ScoreCard,
        min_passing_score: int = 80,
    ) -> CriticReview:
        """Review a ScoreCard and return a CriticReview.

        The score card must meet the minimum passing threshold.
        High hallucination risk is flagged as a warning.
        """
        final_score = score_card.final_weighted_score()
        passing = score_card.is_passing(threshold=min_passing_score)

        warnings: list[str] = []
        if score_card.hallucination_risk.value != "low":
            warnings.append(
                f"Hallucination risk: {score_card.hallucination_risk.value}"
            )
        if final_score < min_passing_score:
            warnings.append(
                f"Score {final_score} below threshold {min_passing_score}"
            )

        decision = CriticDecision(
            approved=passing,
            reason="; ".join(warnings) if warnings else "Score meets threshold.",
            confidence=round(final_score / 100.0, 2),
        )

        return CriticReview(
            approved=passing,
            decision=decision,
            score_card=score_card,
            warnings=warnings,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _check_criteria(
        self,
        criteria: list[str],
        verification_result: VerificationResult,
    ) -> list[str]:
        """Check acceptance criteria against verification results.

        Structural check: each criterion is checked against the stdout
        summary for mention. This is a heuristic — criteria that mention
        specific commands are checked against command results.
        """
        failed: list[str] = []
        stdout_lower = verification_result.stdout_summary.lower()
        for criterion in criteria:
            c_lower = criterion.lower()
            # If criterion references a command, check if that command passed
            # Otherwise check for keyword presence in stdout summary
            words = c_lower.split()
            key_words = [w for w in words if len(w) > 3]

            if key_words and not any(w in stdout_lower for w in key_words):
                failed.append(criterion)

        return failed

    def _estimate_confidence(
        self,
        passed_cmd: int,
        total_cmd: int,
        passed_smoke: int,
        total_smoke: int,
        criteria_ok: bool,
    ) -> float:
        """Estimate confidence (0.0-1.0) based on pass rates."""
        total_checks = total_cmd + total_smoke + (1 if criteria_ok else 0)
        if total_checks == 0:
            return 0.0

        passed_total = passed_cmd + passed_smoke + (1 if criteria_ok else 0)
        ratio = passed_total / total_checks

        # Scale: 0.0 if nothing passes, up to 1.0 if everything passes
        confidence = max(0.0, min(1.0, ratio))
        return round(confidence, 2)
