"""Validators — message and state validation rules."""

from typing import Any, Dict, List, Optional, Tuple

from .models import AgentMessage, MessageType, Phase
from .roles import ROLE_ARBITER, ROLE_CRITIC, ROLE_DOER


class ValidationResult:
    """Result of a validation check."""

    def __init__(
        self,
        valid: bool,
        *,
        errors: Optional[List[str]] = None,
        warnings: Optional[List[str]] = None,
    ) -> None:
        self.valid = valid
        self.errors = errors or []
        self.warnings = warnings or []

    def __bool__(self) -> bool:
        return self.valid

    def __repr__(self) -> str:
        return f"<ValidationResult valid={self.valid} " f"errors={len(self.errors)} warnings={len(self.warnings)}>"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "valid": self.valid,
            "errors": self.errors,
            "warnings": self.warnings,
        }


class MessageValidator:
    """Validates messages against protocol rules."""

    # Which roles can send which message types
    ROLE_PERMISSIONS: Dict[str, List[str]] = {
        ROLE_DOER: [
            MessageType.PLAN.value,
            MessageType.IMPLEMENTATION.value,
            MessageType.RESPONSE.value,
            MessageType.ESCALATION.value,
            MessageType.COUNTER_PROPOSAL.value,
            MessageType.CLARIFICATION.value,
            MessageType.CLARIFICATION_RESPONSE.value,
            MessageType.AMENDMENT.value,
            MessageType.ACKNOWLEDGMENT.value,
            MessageType.OBJECTION.value,
        ],
        ROLE_CRITIC: [
            MessageType.CRITIQUE.value,
            MessageType.REVIEW.value,
            MessageType.VOTE.value,
            MessageType.COUNTER_PROPOSAL.value,
            MessageType.CLARIFICATION.value,
            MessageType.CLARIFICATION_RESPONSE.value,
            MessageType.OBJECTION.value,
            MessageType.ACKNOWLEDGMENT.value,
            MessageType.RESPONSE.value,
        ],
        ROLE_ARBITER: [
            MessageType.DECISION.value,
            MessageType.APPROVAL.value,
            MessageType.REJECTION.value,
            MessageType.VOTE.value,
            MessageType.CLARIFICATION.value,
            MessageType.CLARIFICATION_RESPONSE.value,
            MessageType.ACKNOWLEDGMENT.value,
            MessageType.RESPONSE.value,
        ],
    }

    # Expected message types per phase
    PHASE_MESSAGES: Dict[str, List[str]] = {
        Phase.PLAN.value: [
            MessageType.PLAN.value,
            MessageType.CRITIQUE.value,
            MessageType.CLARIFICATION.value,
            MessageType.CLARIFICATION_RESPONSE.value,
            MessageType.COUNTER_PROPOSAL.value,
            MessageType.RESPONSE.value,
            MessageType.OBJECTION.value,
            MessageType.ACKNOWLEDGMENT.value,
            MessageType.ESCALATION.value,
        ],
        Phase.IMPLEMENT.value: [
            MessageType.IMPLEMENTATION.value,
            MessageType.REVIEW.value,
            MessageType.CLARIFICATION.value,
            MessageType.CLARIFICATION_RESPONSE.value,
            MessageType.COUNTER_PROPOSAL.value,
            MessageType.RESPONSE.value,
            MessageType.OBJECTION.value,
            MessageType.ACKNOWLEDGMENT.value,
            MessageType.ESCALATION.value,
        ],
        Phase.RESOLVE.value: [
            MessageType.ESCALATION.value,
            MessageType.DECISION.value,
            MessageType.COUNTER_PROPOSAL.value,
            MessageType.VOTE.value,
            MessageType.CLARIFICATION.value,
            MessageType.CLARIFICATION_RESPONSE.value,
            MessageType.RESPONSE.value,
            MessageType.OBJECTION.value,
            MessageType.ACKNOWLEDGMENT.value,
        ],
        Phase.APPROVE.value: [
            MessageType.APPROVAL.value,
            MessageType.REJECTION.value,
            MessageType.CLARIFICATION.value,
            MessageType.CLARIFICATION_RESPONSE.value,
            MessageType.RESPONSE.value,
            MessageType.ACKNOWLEDGMENT.value,
        ],
    }

    def validate_message(
        self,
        message: AgentMessage,
        state: Dict[str, Any],
        *,
        strict: bool = False,
    ) -> ValidationResult:
        """Validate a message against the current protocol state.

        Args:
            message: The message to validate.
            state: Current table state.
            strict: If True, warnings become errors.

        Returns:
            ValidationResult with errors and warnings.
        """
        errors: List[str] = []
        warnings: List[str] = []

        # Required fields
        if not message.sender:
            errors.append("Message must have a sender.")
        if not message.recipient:
            errors.append("Message must have a recipient.")
        if not message.content:
            errors.append("Message content cannot be empty.")
        if not message.msg_type:
            errors.append("Message must have a type.")

        # Role permissions
        allowed = self.ROLE_PERMISSIONS.get(message.sender, [])
        if message.msg_type and message.msg_type not in allowed:
            msg = f"Role '{message.sender}' cannot send " f"'{message.msg_type}'. Allowed: {allowed}"
            if strict:
                errors.append(msg)
            else:
                warnings.append(msg)

        # Phase check
        current_phase = state.get("current_phase", "")
        expected = self.PHASE_MESSAGES.get(current_phase, [])
        if message.msg_type and expected and message.msg_type not in expected:
            msg = (
                f"Message type '{message.msg_type}' is not expected in "
                f"phase '{current_phase}'. Expected: {expected}"
            )
            if strict:
                errors.append(msg)
            else:
                warnings.append(msg)

        # Table must be active
        if not state.get("active", False):
            errors.append("Agent Table is not active.")

        # Round number
        if message.round_number > state.get("current_round", 0):
            warnings.append(
                f"Message round ({message.round_number}) exceeds " f"current round ({state.get('current_round', 0)})."
            )

        valid = len(errors) == 0
        return ValidationResult(valid, errors=errors, warnings=warnings)

    def validate_sender_recipient(self, sender: str, recipient: str) -> ValidationResult:
        """Validate sender-recipient pair."""
        errors: List[str] = []

        if sender == recipient:
            errors.append("Sender cannot be the same as recipient.")

        return ValidationResult(len(errors) == 0, errors=errors)


class StateValidator:
    """Validates table state consistency."""

    def validate_state(self, state: Dict[str, Any]) -> ValidationResult:
        """Validate a table state dict for internal consistency.

        Checks:
        - Required keys exist
        - Round numbers are non-negative
        - Phase is valid
        - Max rounds > 0
        """
        errors: List[str] = []
        warnings: List[str] = []

        required_keys = [
            "active",
            "task",
            "current_round",
            "current_phase",
            "max_rounds",
        ]
        for key in required_keys:
            if key not in state:
                errors.append(f"Missing required key: '{key}'")

        # Round
        current_round = state.get("current_round", 0)
        if isinstance(current_round, int) and current_round < 0:
            errors.append(f"current_round cannot be negative: {current_round}")

        # Phase
        phase = state.get("current_phase", "")
        valid_phases = [p.value for p in Phase]
        if phase and phase not in valid_phases:
            errors.append(f"Invalid phase: '{phase}'. Valid: {valid_phases}")

        # Max rounds
        max_rounds = state.get("max_rounds", 10)
        if isinstance(max_rounds, int) and max_rounds <= 0:
            warnings.append(f"max_rounds should be positive: {max_rounds}")

        # Escalation count
        esc = state.get("escalation_count", 0)
        if isinstance(esc, int) and esc < 0:
            errors.append(f"escalation_count cannot be negative: {esc}")

        # Rounds summary
        summaries = state.get("rounds_summary", [])
        if not isinstance(summaries, list):
            errors.append("rounds_summary must be a list.")

        valid = len(errors) == 0
        return ValidationResult(valid, errors=errors, warnings=warnings)
