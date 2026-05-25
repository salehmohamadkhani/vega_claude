"""Deliberation strategies — pluggable policies for how agents collaborate."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from .models import AgentMessage, MessageType, Phase


class DeliberationStrategy(ABC):
    """Base class for deliberation strategies.

    A strategy controls how the protocol progresses:
    - When to escalate
    - When to auto-approve
    - How many review rounds before forced decision
    - Whether to require unanimous consent
    """

    name: str = "base"
    description: str = ""

    @abstractmethod
    def should_escalate(
        self,
        state: Dict[str, Any],
        critique_approved: bool,
    ) -> bool:
        """Decide whether to escalate to the Arbiter."""

    @abstractmethod
    def should_auto_approve(
        self,
        state: Dict[str, Any],
        messages: List[AgentMessage],
    ) -> bool:
        """Decide whether to automatically approve without Arbiter."""

    @abstractmethod
    def max_critique_rounds(self) -> int:
        """Maximum back-and-forth between Doer and Critic before forced escalation."""

    def can_skip_resolve(self, state: Dict[str, Any]) -> bool:
        """Whether RESOLVE phase can be skipped when not needed."""
        return True

    def get_escalation_reason(self, state: Dict[str, Any], critique_approved: bool) -> str:
        """Generate the escalation reason message."""
        if not critique_approved:
            return "Critic did not approve. Escalating to Arbiter for decision."
        return "Automatic escalation per strategy rules."

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "max_critique_rounds": self.max_critique_rounds(),
        }


# ---------------------------------------------------------------------------
# Built-in Strategies
# ---------------------------------------------------------------------------


class DefaultStrategy(DeliberationStrategy):
    """Default strategy — matches the original monolith behavior.

    - Escalate whenever critic does not approve (if auto_escalate is on)
    - No auto-approval
    - 1 critique round before escalation
    """

    name = "default"
    description = "Standard protocol: escalate on first rejection."

    def should_escalate(self, state: Dict[str, Any], critique_approved: bool) -> bool:
        return not critique_approved and state.get("auto_escalate", True)

    def should_auto_approve(self, state: Dict[str, Any], messages: List[AgentMessage]) -> bool:
        return False

    def max_critique_rounds(self) -> int:
        return 1


class StrictStrategy(DeliberationStrategy):
    """Strict strategy — always escalate, never auto-approve.

    - Every action goes through the full flow (plan → critique → escalate → decide → approve)
    - Arbiter must always weigh in
    - No shortcuts allowed
    """

    name = "strict"
    description = "Maximum oversight: every action requires Arbiter review."

    def should_escalate(self, state: Dict[str, Any], critique_approved: bool) -> bool:
        # Always escalate regardless of approval
        return True

    def should_auto_approve(self, state: Dict[str, Any], messages: List[AgentMessage]) -> bool:
        return False

    def max_critique_rounds(self) -> int:
        return 1

    def can_skip_resolve(self, state: Dict[str, Any]) -> bool:
        return False  # Always go through RESOLVE


class LenientStrategy(DeliberationStrategy):
    """Lenient strategy — auto-approve when critic approves.

    - If critic approves, skip Arbiter entirely
    - Only escalate when critic explicitly rejects
    - Allows multiple critique rounds before escalation
    """

    name = "lenient"
    description = "Minimal friction: critic approval is sufficient, " "Arbiter only for disputes."

    def should_escalate(self, state: Dict[str, Any], critique_approved: bool) -> bool:
        if critique_approved:
            return False
        # Count critique rejections; escalate after 2
        rejections = state.get("_critique_rejections", 0)
        return rejections >= 2

    def should_auto_approve(self, state: Dict[str, Any], messages: List[AgentMessage]) -> bool:
        # Auto-approve if critic says yes
        for msg in reversed(messages):
            if msg.msg_type == MessageType.CRITIQUE.value or msg.msg_type == MessageType.REVIEW.value:
                return msg.metadata.get("approved", False)
        return False

    def max_critique_rounds(self) -> int:
        return 3


class DemocraticStrategy(DeliberationStrategy):
    """Democratic strategy — all agents vote on outcomes.

    - After Doer submits and Critic reviews, all agents vote
    - Majority (including Arbiter) decides the outcome
    - Arbiter's vote counts as tie-breaker only
    """

    name = "democratic"
    description = "All agents vote on decisions; Arbiter breaks ties."

    def should_escalate(self, state: Dict[str, Any], critique_approved: bool) -> bool:
        # In democratic mode, always proceed to voting (resolve phase)
        return True

    def should_auto_approve(self, state: Dict[str, Any], messages: List[AgentMessage]) -> bool:
        # Count votes
        votes = self._count_votes(messages)
        approvals = sum(1 for v in votes.values() if v)
        return approvals >= 2  # Majority of 3 agents

    def max_critique_rounds(self) -> int:
        return 1

    def can_skip_resolve(self, state: Dict[str, Any]) -> bool:
        return False  # Always need to gather votes

    def _count_votes(self, messages: List[AgentMessage]) -> Dict[str, bool]:
        """Extract votes from messages."""
        votes: Dict[str, bool] = {}
        for msg in messages:
            if msg.msg_type == MessageType.VOTE.value:
                votes[msg.sender] = msg.metadata.get("approved", False)
        return votes


class AutocraticStrategy(DeliberationStrategy):
    """Autocratic strategy — Arbiter decides everything.

    - Critic review is advisory only
    - Arbiter always makes the final call
    - No voting, no consensus needed
    """

    name = "autocratic"
    description = "Arbiter has absolute authority; reviews are advisory only."

    def should_escalate(self, state: Dict[str, Any], critique_approved: bool) -> bool:
        # Always escalate to Arbiter
        return True

    def should_auto_approve(self, state: Dict[str, Any], messages: List[AgentMessage]) -> bool:
        return False

    def max_critique_rounds(self) -> int:
        return 1

    def can_skip_resolve(self, state: Dict[str, Any]) -> bool:
        return False


# ---------------------------------------------------------------------------
# Strategy Registry
# ---------------------------------------------------------------------------

_REGISTRY: Dict[str, DeliberationStrategy] = {
    "default": DefaultStrategy(),
    "strict": StrictStrategy(),
    "lenient": LenientStrategy(),
    "democratic": DemocraticStrategy(),
    "autocratic": AutocraticStrategy(),
}


def get_strategy(name: str) -> DeliberationStrategy:
    """Look up a strategy by name.

    Raises:
        KeyError: If *name* is not registered.
    """
    if name not in _REGISTRY:
        raise KeyError(f"Unknown strategy '{name}'. " f"Available: {list(_REGISTRY.keys())}")
    return _REGISTRY[name]


def register_strategy(strategy: DeliberationStrategy) -> None:
    """Register a custom strategy."""
    _REGISTRY[strategy.name] = strategy


def list_strategies() -> List[str]:
    """Return names of all registered strategies."""
    return list(_REGISTRY.keys())
