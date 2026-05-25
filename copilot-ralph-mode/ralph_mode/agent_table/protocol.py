"""Protocol engine — phase transition logic, validation, and deadlock detection."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from .models import MessageType, Phase

# ---------------------------------------------------------------------------
# Transition rules
# ---------------------------------------------------------------------------

# Default phase transition order
PHASE_ORDER: List[Phase] = [Phase.PLAN, Phase.IMPLEMENT, Phase.RESOLVE, Phase.APPROVE]

# Map of allowed transitions: current → set of valid next phases
ALLOWED_TRANSITIONS: Dict[Phase, List[Phase]] = {
    Phase.PLAN: [Phase.IMPLEMENT, Phase.RESOLVE],
    Phase.IMPLEMENT: [Phase.RESOLVE, Phase.APPROVE],
    Phase.RESOLVE: [Phase.APPROVE, Phase.PLAN],
    Phase.APPROVE: [Phase.PLAN],  # Wraps to next round
}

# Which message types are expected in each phase
PHASE_EXPECTED_MESSAGES: Dict[Phase, List[str]] = {
    Phase.PLAN: [MessageType.PLAN.value, MessageType.CRITIQUE.value],
    Phase.IMPLEMENT: [
        MessageType.IMPLEMENTATION.value,
        MessageType.REVIEW.value,
    ],
    Phase.RESOLVE: [
        MessageType.ESCALATION.value,
        MessageType.DECISION.value,
        MessageType.COUNTER_PROPOSAL.value,
        MessageType.VOTE.value,
    ],
    Phase.APPROVE: [
        MessageType.APPROVAL.value,
        MessageType.REJECTION.value,
    ],
}


# ---------------------------------------------------------------------------
# ProtocolEngine
# ---------------------------------------------------------------------------


class ProtocolEngine:
    """Manages phase transitions, validation rules, and deadlock detection.

    The engine is *stateless* — it operates on a state dict and returns
    an updated copy.  Persistence is handled by the caller.
    """

    def __init__(
        self,
        *,
        deadlock_threshold: int = 3,
        allow_skip_resolve: bool = True,
    ) -> None:
        """
        Args:
            deadlock_threshold: Number of consecutive rejections before
                declaring deadlock.
            allow_skip_resolve: If True, IMPLEMENT can go straight to
                APPROVE (skipping RESOLVE when there's no escalation).
        """
        self.deadlock_threshold = deadlock_threshold
        self.allow_skip_resolve = allow_skip_resolve

    # ------------------------------------------------------------------
    # Phase Advance
    # ------------------------------------------------------------------

    def advance_phase(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Advance to the next phase following default transition rules.

        APPROVE phase stays at APPROVE (caller should call new_round).

        Returns:
            Updated state dict (shallow copy).
        """
        current = state["current_phase"]

        linear = {
            Phase.PLAN.value: Phase.IMPLEMENT.value,
            Phase.IMPLEMENT.value: Phase.RESOLVE.value,
            Phase.RESOLVE.value: Phase.APPROVE.value,
            Phase.APPROVE.value: Phase.PLAN.value,
        }

        next_phase = linear.get(current, Phase.PLAN.value)

        # Don't auto-advance past APPROVE — caller must start a new round
        if next_phase == Phase.PLAN.value and current == Phase.APPROVE.value:
            next_phase = Phase.APPROVE.value

        state["current_phase"] = next_phase
        return state

    def set_phase(self, state: Dict[str, Any], phase: str) -> Dict[str, Any]:
        """Explicitly set the current phase with validation.

        Raises:
            ValueError: If *phase* is not a valid Phase value.
        """
        valid = [p.value for p in Phase]
        if phase not in valid:
            raise ValueError(f"Invalid phase: {phase}. Must be one of {valid}")
        state["current_phase"] = phase
        return state

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def is_valid_transition(self, from_phase: str, to_phase: str) -> bool:
        """Return True if transitioning from *from_phase* to *to_phase* is allowed."""
        try:
            src = Phase(from_phase)
            dst = Phase(to_phase)
        except ValueError:
            return False
        return dst in ALLOWED_TRANSITIONS.get(src, [])

    def is_message_valid_for_phase(self, msg_type: str, phase: str) -> bool:
        """Check whether *msg_type* is expected in the given *phase*."""
        try:
            p = Phase(phase)
        except ValueError:
            return False
        expected = PHASE_EXPECTED_MESSAGES.get(p, [])
        return msg_type in expected

    def validate_sender_role(self, sender: str, msg_type: str) -> Tuple[bool, str]:
        """Validate that *sender* is allowed to send *msg_type*.

        Returns:
            (is_valid, error_message)
        """
        from .roles import ROLE_ARBITER, ROLE_CRITIC, ROLE_DOER

        role_permissions: Dict[str, List[str]] = {
            ROLE_DOER: [
                MessageType.PLAN.value,
                MessageType.IMPLEMENTATION.value,
                MessageType.RESPONSE.value,
                MessageType.ESCALATION.value,
                MessageType.COUNTER_PROPOSAL.value,
            ],
            ROLE_CRITIC: [
                MessageType.CRITIQUE.value,
                MessageType.REVIEW.value,
                MessageType.VOTE.value,
                MessageType.COUNTER_PROPOSAL.value,
            ],
            ROLE_ARBITER: [
                MessageType.DECISION.value,
                MessageType.APPROVAL.value,
                MessageType.REJECTION.value,
                MessageType.VOTE.value,
            ],
        }

        allowed = role_permissions.get(sender, [])
        if msg_type in allowed:
            return True, ""
        return (
            False,
            f"Role '{sender}' is not allowed to send '{msg_type}'. " f"Allowed: {allowed}",
        )

    # ------------------------------------------------------------------
    # Deadlock Detection
    # ------------------------------------------------------------------

    def detect_deadlock(self, state: Dict[str, Any]) -> bool:
        """Return True if the deliberation appears deadlocked.

        A deadlock is declared when the number of consecutive rejections
        meets or exceeds *deadlock_threshold*.
        """
        summaries = state.get("rounds_summary", [])
        if not summaries:
            return False

        consecutive_rejections = 0
        for summary in reversed(summaries):
            if summary.get("outcome") == "rejected":
                consecutive_rejections += 1
            else:
                break

        return consecutive_rejections >= self.deadlock_threshold

    def get_deadlock_info(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Return diagnostic information about a potential deadlock."""
        summaries = state.get("rounds_summary", [])
        consecutive = 0
        rejection_reasons: List[str] = []

        for summary in reversed(summaries):
            if summary.get("outcome") == "rejected":
                consecutive += 1
                if summary.get("reason"):
                    rejection_reasons.append(summary["reason"])
            else:
                break

        return {
            "is_deadlocked": consecutive >= self.deadlock_threshold,
            "consecutive_rejections": consecutive,
            "threshold": self.deadlock_threshold,
            "rejection_reasons": list(reversed(rejection_reasons)),
            "suggestion": (
                "Consider: (1) adjusting task scope, (2) overriding with "
                "arbiter force-approve, or (3) increasing threshold."
                if consecutive >= self.deadlock_threshold
                else "No deadlock detected."
            ),
        }

    # ------------------------------------------------------------------
    # Phase Duration Tracking
    # ------------------------------------------------------------------

    def check_phase_timeout(
        self,
        state: Dict[str, Any],
        *,
        max_seconds: int = 600,
    ) -> bool:
        """Return True if the current phase has exceeded the timeout.

        *max_seconds* defaults to 10 minutes.
        """
        entered = state.get("phase_entered_at")
        if not entered:
            return False
        try:
            entered_dt = datetime.fromisoformat(entered)
            now = datetime.now(timezone.utc)
            if entered_dt.tzinfo is None:
                entered_dt = entered_dt.replace(tzinfo=timezone.utc)
            return (now - entered_dt).total_seconds() > max_seconds
        except (ValueError, TypeError):
            return False
