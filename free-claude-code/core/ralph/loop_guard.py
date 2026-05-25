"""Deterministic loop guard for Ralph Runtime.

Evaluates iteration progress and decides whether to continue, retry,
debug, escalate, or stop. No AI calls, no subprocesses — only logic.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass


class LoopAction(enum.Enum):
    """Action the loop guard can recommend."""

    CONTINUE = "continue"
    RETRY = "retry"
    DEBUG = "debug"
    ESCALATE = "escalate"
    STOP = "stop"


@dataclass
class LoopGuardDecision:
    """A single decision from the loop guard."""

    action: LoopAction = LoopAction.CONTINUE
    reason: str = ""
    repeated_failure_count: int = 0
    max_iterations_reached: bool = False
    no_progress_detected: bool = False


# Thresholds for loop guard decisions.
_RETRY_THRESHOLD = 3  # consecutive identical errors → escalate
_DEBUG_THRESHOLD = 5  # consecutive failures → debug mode
_PROGRESS_MIN_SUMMARY_LENGTH = 10  # characters; shorter suggests no progress
_CRITIC_REJECTION_LIMIT = 3  # repeated critic rejections → stop


class LoopGuard:
    """Deterministic loop guard that evaluates iteration health.

    The guard examines:
    - Current iteration vs max iterations
    - Repeated error messages (identical strings)
    - Repeated verification failures
    - Empty or trivial progress summaries
    - Repeated critic rejections
    """

    def __init__(self, max_iterations: int = 10) -> None:
        if max_iterations < 1:
            raise ValueError("max_iterations must be >= 1")
        self._max_iterations = max_iterations
        self._error_history: list[str] = []
        self._verification_failures: list[str] = []
        self._progress_summaries: list[str] = []
        self._critic_rejections: int = 0

    # ---- Record keeping ----

    def record_error(self, error: str) -> None:
        """Record an error message from the current iteration."""
        self._error_history.append(error)

    def record_verification_failure(self, detail: str) -> None:
        """Record a verification failure."""
        self._verification_failures.append(detail)

    def record_progress_summary(self, summary: str) -> None:
        """Record the progress summary for the current iteration."""
        self._progress_summaries.append(summary)

    def record_critic_rejection(self) -> None:
        """Record a critic rejection."""
        self._critic_rejections += 1

    # ---- Evaluation ----

    def evaluate(self, current_iteration: int) -> LoopGuardDecision:
        """Evaluate current state and return a decision.

        Rules evaluated in order (first match wins):
        1. If max_iterations reached → STOP
        2. If repeated critic rejections beyond limit → STOP
        3. If repeated identical errors beyond threshold → ESCALATE
        4. If repeated verification failures beyond threshold → DEBUG
        5. If latest progress summary is empty/trivial → RETRY
        6. Otherwise → CONTINUE
        """
        # Rule 1: max iterations
        if current_iteration >= self._max_iterations:
            return LoopGuardDecision(
                action=LoopAction.STOP,
                reason=f"Max iterations ({self._max_iterations}) reached.",
                max_iterations_reached=True,
                repeated_failure_count=len(self._error_history),
            )

        # Rule 2: repeated critic rejection
        if self._critic_rejections >= _CRITIC_REJECTION_LIMIT:
            return LoopGuardDecision(
                action=LoopAction.STOP,
                reason=f"Critic rejected {self._critic_rejections} times (limit {_CRITIC_REJECTION_LIMIT}).",
                repeated_failure_count=self._critic_rejections,
            )

        # Rule 3: repeated identical errors
        repeated_errors = self._count_consecutive_identical_errors()
        if repeated_errors >= _RETRY_THRESHOLD:
            return LoopGuardDecision(
                action=LoopAction.ESCALATE,
                reason=f"Same error repeated {repeated_errors} times. Escalating.",
                repeated_failure_count=repeated_errors,
            )

        # Rule 4: repeated verification failures
        if len(self._verification_failures) >= _DEBUG_THRESHOLD:
            return LoopGuardDecision(
                action=LoopAction.DEBUG,
                reason=f"Verification failed {len(self._verification_failures)} times. Entering debug mode.",
                repeated_failure_count=len(self._verification_failures),
            )

        # Rule 5: no progress detection
        if self._has_no_progress():
            return LoopGuardDecision(
                action=LoopAction.RETRY,
                reason="No meaningful progress detected in last summary.",
                no_progress_detected=True,
                repeated_failure_count=len(self._error_history),
            )

        # Rule 6: continue
        return LoopGuardDecision(
            action=LoopAction.CONTINUE,
            reason="All checks passed. Continuing.",
        )

    # ---- Internal helpers ----

    def _count_consecutive_identical_errors(self) -> int:
        """Count how many consecutive errors at the end of history are identical."""
        if len(self._error_history) < 2:
            return 0
        last = self._error_history[-1]
        count = 1
        for err in reversed(self._error_history[:-1]):
            if err == last:
                count += 1
            else:
                break
        return count

    def _has_no_progress(self) -> bool:
        """Check if the last progress summary indicates no progress."""
        if not self._progress_summaries:
            return False
        last = self._progress_summaries[-1].strip()
        return len(last) < _PROGRESS_MIN_SUMMARY_LENGTH

    # ---- Reset ----

    def reset(self) -> None:
        """Clear all history (e.g., when advancing to a new task)."""
        self._error_history.clear()
        self._verification_failures.clear()
        self._progress_summaries.clear()
        self._critic_rejections = 0
