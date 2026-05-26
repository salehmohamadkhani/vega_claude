"""Deterministic arbiter for Ralph Runtime multi-agent disputes.

Resolves disagreements between the Doer and the Critic using
rule-based logic. No AI calls, no subprocesses.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field

from .critic import CriticReview
from .loop_guard import LoopAction, LoopGuardDecision
from .scoring import ScoreCard


class ArbiterAction(enum.Enum):
    """Action the arbiter can recommend after dispute resolution."""

    APPROVE = "approve"
    RETRY = "retry"
    DEBUG = "debug"
    ESCALATE = "escalate"
    STOP = "stop"


@dataclass
class ArbiterDecision:
    """A single decision from the arbiter."""

    action: ArbiterAction = ArbiterAction.RETRY
    reason: str = ""
    summary: str = ""
    suggested_fixes: list[str] = field(default_factory=list)


# Thresholds for arbiter heuristics.
_MAX_RETRIES_BEFORE_DEBUG = 3  # consecutive retries → DEBUG
_MAX_RETRIES_BEFORE_ESCALATE = 5  # too many retries → ESCALATE
_MIN_SCORE_FOR_APPROVAL = 80  # ScoreCard must meet this threshold
_MAX_CRITIC_REJECTIONS_BEFORE_STOP = 3  # critic keeps rejecting → STOP
_LOW_CONFIDENCE_DEBUG_THRESHOLD = 0.4  # confidence below this → DEBUG mode


class ArbiterEngine:
    """Deterministic arbiter that resolves Doer↔Critic disputes.

    The arbiter examines:
    - Critic review (approved/rejected + confidence)
    - Loop guard decision (continue/retry/debug/escalate/stop)
    - ScoreCard (if available)
    - Retry count (how many times this task has been retried)
    """

    def __init__(
        self,
        max_retries_before_debug: int = _MAX_RETRIES_BEFORE_DEBUG,
        max_retries_before_escalate: int = _MAX_RETRIES_BEFORE_ESCALATE,
        max_critic_rejections_before_stop: int = _MAX_CRITIC_REJECTIONS_BEFORE_STOP,
    ) -> None:
        self._max_retries_debug = max_retries_before_debug
        self._max_retries_escalate = max_retries_before_escalate
        self._max_critic_stop = max_critic_rejections_before_stop

    def decide(
        self,
        critic_review: CriticReview,
        loop_guard_decision: LoopGuardDecision | None = None,
        score_card: ScoreCard | None = None,
        retry_count: int = 0,
        critic_rejection_count: int = 0,
    ) -> ArbiterDecision:
        """Evaluate all signals and return a final arbiter decision.

        Rules evaluated in priority order (first match wins):

        1. If loop guard says STOP → STOP
        2. If loop guard says ESCALATE → ESCALATE
        3. If loop guard says DEBUG → DEBUG
        4. If critic approves and score is acceptable → APPROVE
        5. If critic rejects but confidence is very low → DEBUG (needs investigation)
        6. If too many critic rejections → STOP
        7. If too many retries → ESCALATE
        8. If moderate retries → DEBUG
        9. Otherwise → RETRY
        """
        # Rule 1: loop guard STOP
        if loop_guard_decision is not None:
            if loop_guard_decision.action == LoopAction.STOP:
                return ArbiterDecision(
                    action=ArbiterAction.STOP,
                    reason=f"Loop guard: {loop_guard_decision.reason}",
                    summary="Stopped by loop guard.",
                )
            # Rule 2: loop guard ESCALATE
            if loop_guard_decision.action == LoopAction.ESCALATE:
                return ArbiterDecision(
                    action=ArbiterAction.ESCALATE,
                    reason=f"Loop guard: {loop_guard_decision.reason}",
                    summary="Escalated by loop guard.",
                )
            # Rule 3: loop guard DEBUG
            if loop_guard_decision.action == LoopAction.DEBUG:
                return ArbiterDecision(
                    action=ArbiterAction.DEBUG,
                    reason=f"Loop guard: {loop_guard_decision.reason}",
                    summary="Debug mode requested by loop guard.",
                )

        # Rule 4: critic approves + score acceptable
        if critic_review.approved:
            if score_card is not None and not score_card.is_passing(
                threshold=_MIN_SCORE_FOR_APPROVAL
            ):
                # Score is too low even though critic approved
                return ArbiterDecision(
                    action=ArbiterAction.RETRY,
                    reason=(
                        f"Critic approved but score "
                        f"{score_card.final_weighted_score()} is below "
                        f"threshold {_MIN_SCORE_FOR_APPROVAL}."
                    ),
                    summary="Retrying due to low score despite critic approval.",
                )
            return ArbiterDecision(
                action=ArbiterAction.APPROVE,
                reason="Critic approved all checks.",
                summary="Task approved.",
            )

        # Rule 5: critic rejected with very low confidence → needs investigation
        if critic_review.decision.confidence < _LOW_CONFIDENCE_DEBUG_THRESHOLD:
            return ArbiterDecision(
                action=ArbiterAction.DEBUG,
                reason=(
                    f"Critic rejected with low confidence "
                    f"({critic_review.decision.confidence}). "
                    f"Reason: {critic_review.decision.reason}"
                ),
                summary="Debugging due to low critic confidence.",
                suggested_fixes=critic_review.decision.required_fixes,
            )

        # Rule 6: too many critic rejections
        if critic_rejection_count >= self._max_critic_stop:
            return ArbiterDecision(
                action=ArbiterAction.STOP,
                reason=(
                    f"Critic rejected {critic_rejection_count} times "
                    f"(limit {self._max_critic_stop})."
                ),
                summary="Stopping due to repeated critic rejections.",
                suggested_fixes=critic_review.decision.required_fixes,
            )

        # Rule 7: too many retries → ESCALATE
        if retry_count >= self._max_retries_escalate:
            return ArbiterDecision(
                action=ArbiterAction.ESCALATE,
                reason=f"Task retried {retry_count} times without approval.",
                summary=f"Escalating after {retry_count} retries.",
                suggested_fixes=critic_review.decision.required_fixes,
            )

        # Rule 8: moderate retries → DEBUG
        if retry_count >= self._max_retries_debug:
            return ArbiterDecision(
                action=ArbiterAction.DEBUG,
                reason=f"Task retried {retry_count} times. Switching to debug.",
                summary="Debug mode after multiple retries.",
                suggested_fixes=critic_review.decision.required_fixes,
            )

        # Rule 9: default → RETRY
        return ArbiterDecision(
            action=ArbiterAction.RETRY,
            reason=critic_review.decision.reason or "Critic did not approve.",
            summary="Retrying task.",
            suggested_fixes=critic_review.decision.required_fixes,
        )
