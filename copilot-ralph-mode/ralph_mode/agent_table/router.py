"""Message router — conditional message routing based on phase, strategy, and content."""

from typing import Any, Callable, Dict, List, Optional, Tuple

from .models import AgentMessage, MessageType, Phase
from .roles import ROLE_ARBITER, ROLE_CRITIC, ROLE_DOER


class RoutingRule:
    """A single routing rule that determines message flow.

    A rule consists of a condition function and a target agent.
    When the condition evaluates to True for a given message and state,
    the router directs the message to the target.
    """

    def __init__(
        self,
        name: str,
        condition: Callable[[AgentMessage, Dict[str, Any]], bool],
        target: str,
        *,
        priority: int = 0,
        description: str = "",
        transform: Optional[Callable[[AgentMessage], AgentMessage]] = None,
    ) -> None:
        self.name = name
        self.condition = condition
        self.target = target
        self.priority = priority
        self.description = description
        self.transform = transform  # Optional message transformation

    def matches(self, message: AgentMessage, state: Dict[str, Any]) -> bool:
        """Evaluate whether this rule applies to the given message."""
        try:
            return self.condition(message, state)
        except Exception:
            return False

    def __repr__(self) -> str:
        return f"<RoutingRule '{self.name}' → {self.target} (pri={self.priority})>"


class MessageRouter:
    """Routes messages to the correct agent based on protocol rules.

    The default routing follows the deliberation protocol:
    - Doer's plans → Critic
    - Critic's critiques → Doer (or Arbiter if escalation)
    - Doer's implementations → Critic
    - Critic's reviews → Doer (or Arbiter if escalation)
    - Escalations → Arbiter
    - Arbiter's decisions → Doer
    - Arbiter's approvals/rejections → Doer

    Custom rules can be added to override or extend this behavior.
    """

    def __init__(self) -> None:
        self._rules: List[RoutingRule] = []
        self._install_defaults()

    def _install_defaults(self) -> None:
        """Install default routing rules for the standard protocol."""
        defaults = [
            # Doer sends plans to Critic
            RoutingRule(
                "plan_to_critic",
                lambda m, s: m.sender == ROLE_DOER and m.msg_type == MessageType.PLAN.value,
                ROLE_CRITIC,
                priority=0,
                description="Doer's plans go to Critic for review",
            ),
            # Doer sends implementations to Critic
            RoutingRule(
                "implementation_to_critic",
                lambda m, s: m.sender == ROLE_DOER and m.msg_type == MessageType.IMPLEMENTATION.value,
                ROLE_CRITIC,
                priority=0,
                description="Doer's implementations go to Critic for review",
            ),
            # Critic sends critiques to Doer
            RoutingRule(
                "critique_to_doer",
                lambda m, s: (
                    m.sender == ROLE_CRITIC
                    and m.msg_type == MessageType.CRITIQUE.value
                    and m.metadata.get("approved", True)
                ),
                ROLE_DOER,
                priority=0,
                description="Critic's approving critiques go to Doer",
            ),
            # Critic's rejections → Arbiter (when auto-escalate)
            RoutingRule(
                "critique_rejection_to_arbiter",
                lambda m, s: (
                    m.sender == ROLE_CRITIC
                    and m.msg_type == MessageType.CRITIQUE.value
                    and not m.metadata.get("approved", True)
                    and s.get("auto_escalate", False)
                ),
                ROLE_ARBITER,
                priority=10,
                description="Critic's rejections escalate to Arbiter",
            ),
            # Reviews work like critiques
            RoutingRule(
                "review_to_doer",
                lambda m, s: (
                    m.sender == ROLE_CRITIC
                    and m.msg_type == MessageType.REVIEW.value
                    and m.metadata.get("approved", True)
                ),
                ROLE_DOER,
                priority=0,
                description="Critic's approving reviews go to Doer",
            ),
            RoutingRule(
                "review_rejection_to_arbiter",
                lambda m, s: (
                    m.sender == ROLE_CRITIC
                    and m.msg_type == MessageType.REVIEW.value
                    and not m.metadata.get("approved", True)
                    and s.get("auto_escalate", False)
                ),
                ROLE_ARBITER,
                priority=10,
                description="Critic's review rejections escalate to Arbiter",
            ),
            # Escalations always go to Arbiter
            RoutingRule(
                "escalation_to_arbiter",
                lambda m, s: m.msg_type == MessageType.ESCALATION.value,
                ROLE_ARBITER,
                priority=100,
                description="All escalations go to Arbiter",
            ),
            # Arbiter's decisions go to Doer
            RoutingRule(
                "decision_to_doer",
                lambda m, s: (
                    m.sender == ROLE_ARBITER
                    and m.msg_type
                    in (
                        MessageType.DECISION.value,
                        MessageType.APPROVAL.value,
                        MessageType.REJECTION.value,
                    )
                ),
                ROLE_DOER,
                priority=0,
                description="Arbiter's decisions/approvals/rejections go to Doer",
            ),
            # Counter-proposals go back to the original proposer
            RoutingRule(
                "counter_to_proposer",
                lambda m, s: m.msg_type == MessageType.COUNTER_PROPOSAL.value,
                "",  # Dynamic — determined by reply chain
                priority=5,
                description="Counter-proposals go back to the previous proposer",
            ),
            # Clarification requests go to the party that needs to clarify
            RoutingRule(
                "clarification_to_target",
                lambda m, s: m.msg_type == MessageType.CLARIFICATION.value,
                "",  # Dynamic
                priority=5,
                description="Clarification requests go to the relevant party",
            ),
        ]
        self._rules.extend(defaults)

    # ------------------------------------------------------------------
    # Rule Management
    # ------------------------------------------------------------------

    def add_rule(self, rule: RoutingRule) -> None:
        """Add a custom routing rule."""
        self._rules.append(rule)
        self._rules.sort(key=lambda r: r.priority, reverse=True)

    def remove_rule(self, name: str) -> bool:
        """Remove a routing rule by name."""
        before = len(self._rules)
        self._rules = [r for r in self._rules if r.name != name]
        return len(self._rules) < before

    # ------------------------------------------------------------------
    # Routing
    # ------------------------------------------------------------------

    def resolve_recipient(
        self,
        message: AgentMessage,
        state: Dict[str, Any],
    ) -> str:
        """Determine the correct recipient for a message.

        Evaluates rules in priority order (high to low). Returns the
        target of the first matching rule, or the message's existing
        recipient if no rule matches.
        """
        for rule in sorted(self._rules, key=lambda r: r.priority, reverse=True):
            if rule.matches(message, state):
                if rule.target:  # Static target
                    return rule.target
                # Dynamic target — use message's recipient
                return message.recipient

        return message.recipient

    def should_escalate(
        self,
        message: AgentMessage,
        state: Dict[str, Any],
    ) -> bool:
        """Determine whether a message should trigger escalation.

        Returns True if any escalation-related rule matches.
        """
        for rule in self._rules:
            if "escalat" in rule.name.lower() or "arbiter" in rule.name.lower():
                if rule.matches(message, state):
                    return True
        return False

    def get_next_expected_action(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Determine what action is expected next based on current phase.

        Returns:
            Dict with 'agent', 'expected_type', and 'description'.
        """
        phase = state.get("current_phase", "")

        expectations = {
            Phase.PLAN.value: {
                "agent": ROLE_DOER,
                "expected_types": [MessageType.PLAN.value],
                "description": "Doer should submit a plan",
                "then": {
                    "agent": ROLE_CRITIC,
                    "expected_types": [MessageType.CRITIQUE.value],
                    "description": "Critic should review the plan",
                },
            },
            Phase.IMPLEMENT.value: {
                "agent": ROLE_DOER,
                "expected_types": [MessageType.IMPLEMENTATION.value],
                "description": "Doer should implement the plan",
                "then": {
                    "agent": ROLE_CRITIC,
                    "expected_types": [MessageType.REVIEW.value],
                    "description": "Critic should review the implementation",
                },
            },
            Phase.RESOLVE.value: {
                "agent": ROLE_ARBITER,
                "expected_types": [MessageType.DECISION.value],
                "description": "Arbiter should make a decision",
            },
            Phase.APPROVE.value: {
                "agent": ROLE_ARBITER,
                "expected_types": [
                    MessageType.APPROVAL.value,
                    MessageType.REJECTION.value,
                ],
                "description": "Arbiter should approve or reject",
            },
        }

        return expectations.get(
            phase,
            {
                "agent": ROLE_DOER,
                "expected_types": [],
                "description": "Unknown phase",
            },
        )

    def list_rules(self) -> List[Dict[str, Any]]:
        """List all routing rules."""
        return [
            {
                "name": r.name,
                "target": r.target,
                "priority": r.priority,
                "description": r.description,
            }
            for r in sorted(self._rules, key=lambda r: r.priority, reverse=True)
        ]
