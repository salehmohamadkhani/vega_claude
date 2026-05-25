"""Context builder — generates per-agent markdown context prompts.

Enhanced with:
- Conversation thread awareness (full reply-chain context)
- Trust score visibility so agents know their credibility
- Active negotiation status (what's pending, deadlocked, etc.)
- Relationship matrix showing communication patterns
"""

from typing import Any, Callable, Dict, List, Optional

from .models import AgentMessage, MessageType
from .roles import ROLE_ARBITER, ROLE_CRITIC, ROLE_DOER


class ContextBuilder:
    """Builds rich context prompts for each agent role.

    The context includes task description, latest messages, history,
    conversation threads, trust data, negotiation status,
    and role-specific instructions.
    """

    def __init__(
        self,
        *,
        get_state: Callable,
        get_last_message: Callable,
        get_messages: Callable,
        get_trust_weight: Optional[Callable] = None,
        get_active_negotiations: Optional[Callable] = None,
        get_active_threads: Optional[Callable] = None,
        get_relationship_matrix: Optional[Callable] = None,
    ) -> None:
        """
        Args:
            get_state: Callable returning current state dict or None.
            get_last_message: Callable(sender, msg_type) → AgentMessage | None
            get_messages: Callable(**filters) → List[AgentMessage]
            get_trust_weight: Callable(agent_role) → float (0.0-1.0)
            get_active_negotiations: Callable() → list of negotiation dicts
            get_active_threads: Callable() → list of ConversationThread
            get_relationship_matrix: Callable() → dict
        """
        self._get_state = get_state
        self._get_last_message = get_last_message
        self._get_messages = get_messages
        self._get_trust_weight = get_trust_weight
        self._get_active_negotiations = get_active_negotiations
        self._get_active_threads = get_active_threads
        self._get_relationship_matrix = get_relationship_matrix

    # ------------------------------------------------------------------
    # Shared Helpers
    # ------------------------------------------------------------------

    def _trust_section(self, agent: str) -> str:
        """Generate a trust/credibility section for an agent."""
        if not self._get_trust_weight:
            return ""
        try:
            weight = self._get_trust_weight(agent)
            bar = "█" * int(weight * 10) + "░" * (10 - int(weight * 10))
            return (
                f"\n## Trust Score\n\n"
                f"Your current trust weight: **{weight:.2f}** [{bar}]\n"
                f"*(Higher trust = more influence in consensus decisions)*\n"
            )
        except Exception:
            return ""

    def _negotiations_section(self) -> str:
        """Generate a section summarizing active negotiations."""
        if not self._get_active_negotiations:
            return ""
        try:
            negotiations = self._get_active_negotiations()
            if not negotiations:
                return ""
            parts: List[str] = ["\n## Active Negotiations\n"]
            for neg in negotiations[:5]:  # Cap at 5
                status = neg.get("status", "unknown")
                subj = neg.get("subject", "N/A")
                rounds = neg.get("round_count", 0)
                parts.append(f"- **{subj}** — status: `{status}`, rounds: {rounds}")
            return "\n".join(parts) + "\n"
        except Exception:
            return ""

    def _threads_section(self, agent: str) -> str:
        """Generate a section showing active conversation threads involving this agent."""
        if not self._get_active_threads:
            return ""
        try:
            threads = self._get_active_threads()
            if not threads:
                return ""
            # Filter to threads involving this agent
            relevant = [t for t in threads if agent in t.participants]
            if not relevant:
                return ""
            parts: List[str] = ["\n## Open Conversation Threads\n"]
            for thread in relevant[:5]:  # Cap at 5
                last = thread.last_message
                parts.append(
                    f"- Thread `{thread.thread_id[:8]}` "
                    f"({thread.depth} msgs, last: {last.sender}→{last.recipient}): "
                    f"{last.content[:60]}..."
                )
            return "\n".join(parts) + "\n"
        except Exception:
            return ""

    def _conversation_history(self, round_number: int, max_messages: int = 15) -> str:
        """Render the recent conversation for the current round."""
        round_messages = self._get_messages(round_number=round_number)
        if not round_messages:
            return ""

        # Take only the most recent messages to keep context manageable
        recent = round_messages[-max_messages:]

        parts: List[str] = ["\n## Conversation History\n"]
        for msg in recent:
            role_emoji = {
                "doer": "🛠️",
                "critic": "🔍",
                "arbiter": "⚖️",
            }.get(msg.sender, "")
            indent = "  > " if msg.is_reply else ""
            parts.append(
                f"{indent}{role_emoji} **{msg.sender}** → {msg.recipient} "
                f"({msg.msg_type})\n{indent}{msg.content[:300]}\n"
            )
        return "\n".join(parts) + "\n"

    # ------------------------------------------------------------------
    # Doer Context
    # ------------------------------------------------------------------

    def build_doer_context(self) -> str:
        """Build context prompt for the Doer agent.

        Includes: task, latest critique, latest arbiter decision,
        trust score, active negotiations, conversation history.
        """
        state = self._get_state()
        if not state:
            return ""

        parts: List[str] = []
        parts.append(f"# Agent Table — Doer Context (Round {state['current_round']})\n")
        parts.append(f"## Task\n\n{state['task']}\n")
        parts.append(f"## Current Phase: {state['current_phase']}\n")

        # Trust
        parts.append(self._trust_section(ROLE_DOER))

        # Latest critique
        critique = self._get_last_message(sender=ROLE_CRITIC, msg_type=MessageType.CRITIQUE.value)
        if critique:
            parts.append(f"## Latest Critique from Critic\n\n{critique.content}\n")
            parts.append(f"**Approved:** {critique.metadata.get('approved', False)}\n")

        # Latest review
        review = self._get_last_message(sender=ROLE_CRITIC, msg_type=MessageType.REVIEW.value)
        if review:
            parts.append(f"## Latest Review from Critic\n\n{review.content}\n")
            parts.append(f"**Approved:** {review.metadata.get('approved', False)}\n")

        # Latest arbiter decision
        decision = self._get_last_message(sender=ROLE_ARBITER, msg_type=MessageType.DECISION.value)
        if decision:
            parts.append(f"## Arbiter's Decision\n\n{decision.content}\n")
            parts.append(f"**Sides with:** {decision.metadata.get('side_with', 'N/A')}\n")

        # Approval / rejection
        approval = self._get_last_message(sender=ROLE_ARBITER, msg_type=MessageType.APPROVAL.value)
        rejection = self._get_last_message(sender=ROLE_ARBITER, msg_type=MessageType.REJECTION.value)
        if approval:
            parts.append(f"## ✅ Arbiter Approval\n\n{approval.content}\n")
        if rejection:
            parts.append(f"## ❌ Arbiter Rejection\n\n{rejection.content}\n")

        # Active negotiations
        parts.append(self._negotiations_section())

        # Thread awareness
        parts.append(self._threads_section(ROLE_DOER))

        # Recent conversation
        parts.append(self._conversation_history(state["current_round"]))

        return "\n".join(parts)

    # ------------------------------------------------------------------
    # Critic Context
    # ------------------------------------------------------------------

    def build_critic_context(self) -> str:
        """Build context prompt for the Critic agent.

        Includes: task, Doer's latest plan/implementation,
        trust score, active negotiations, conversation history.
        """
        state = self._get_state()
        if not state:
            return ""

        parts: List[str] = []
        parts.append(f"# Agent Table — Critic Context (Round {state['current_round']})\n")
        parts.append(f"## Task\n\n{state['task']}\n")
        parts.append(f"## Current Phase: {state['current_phase']}\n")

        # Trust
        parts.append(self._trust_section(ROLE_CRITIC))

        # Latest plan from Doer
        plan = self._get_last_message(sender=ROLE_DOER, msg_type=MessageType.PLAN.value)
        if plan:
            parts.append(f"## Doer's Plan\n\n{plan.content}\n")

        # Latest implementation from Doer
        impl = self._get_last_message(sender=ROLE_DOER, msg_type=MessageType.IMPLEMENTATION.value)
        if impl:
            parts.append(f"## Doer's Implementation\n\n{impl.content}\n")

        # Arbiter's latest decision (for context)
        decision = self._get_last_message(sender=ROLE_ARBITER, msg_type=MessageType.DECISION.value)
        if decision:
            parts.append(f"## Arbiter's Previous Decision\n\n{decision.content}\n")

        # Active negotiations
        parts.append(self._negotiations_section())

        # Thread awareness
        parts.append(self._threads_section(ROLE_CRITIC))

        # Recent conversation
        parts.append(self._conversation_history(state["current_round"]))

        parts.append(
            "\n## Your Role\n\n"
            "You are the **Critic**. Review the Doer's work critically.\n"
            "- Identify bugs, logic errors, security issues\n"
            "- Suggest improvements\n"
            "- State clearly if you APPROVE or REJECT\n"
            "- If you reject, explain exactly what needs to change\n"
            "- You can REQUEST CLARIFICATION if something is unclear\n"
            "- You can COUNTER-PROPOSE an alternative approach\n"
        )

        return "\n".join(parts)

    # ------------------------------------------------------------------
    # Arbiter Context
    # ------------------------------------------------------------------

    def build_arbiter_context(self) -> str:
        """Build context prompt for the Arbiter agent.

        Includes: task, full conversation between Doer and Critic this round,
        trust scores for all agents, negotiation status, relationship matrix.
        """
        state = self._get_state()
        if not state:
            return ""

        parts: List[str] = []
        parts.append(f"# Agent Table — Arbiter Context (Round {state['current_round']})\n")
        parts.append(f"## Task\n\n{state['task']}\n")
        parts.append(f"## Escalation #{state.get('escalation_count', 0)}\n")

        # Trust overview — Arbiter sees all trust scores
        if self._get_trust_weight:
            try:
                doer_w = self._get_trust_weight(ROLE_DOER)
                critic_w = self._get_trust_weight(ROLE_CRITIC)
                parts.append(
                    f"\n## Agent Trust Scores\n\n"
                    f"- Doer trust: **{doer_w:.2f}**\n"
                    f"- Critic trust: **{critic_w:.2f}**\n"
                )
            except Exception:
                pass

        # Active negotiations
        parts.append(self._negotiations_section())

        # All messages this round
        round_messages = self._get_messages(round_number=state["current_round"])
        if round_messages:
            parts.append("## Full Conversation This Round\n")
            for msg in round_messages:
                role_emoji = {
                    "doer": "🛠️",
                    "critic": "🔍",
                    "arbiter": "⚖️",
                }.get(msg.sender, "")
                indent = "  > " if msg.is_reply else ""
                parts.append(f"### {indent}{role_emoji} {msg.sender} → " f"{msg.recipient} ({msg.msg_type})\n")
                parts.append(f"{msg.content}\n")

        parts.append(
            "\n## Your Role\n\n"
            "You are the **Arbiter**. You have final authority.\n"
            "- Read both the Doer's work and the Critic's feedback\n"
            "- Consider each agent's trust score when weighing their arguments\n"
            "- Make a fair, well-reasoned decision\n"
            "- State which approach is correct and why\n"
            "- Your decision is final — the Doer must follow it\n"
        )

        return "\n".join(parts)
