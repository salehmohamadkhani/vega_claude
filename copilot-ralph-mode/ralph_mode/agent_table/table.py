"""AgentTable orchestrator — multi-agent deliberation controller.

This is the primary entry-point class that unifies all sub-modules.
It preserves full backward-compatibility with the original monolithic
AgentTable while exposing new capabilities (strategies, consensus,
trust scoring, hooks, validation, negotiation, interaction tracking,
message routing, and FSM-based state transitions).
"""

import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .consensus import ConsensusEngine
from .context import ContextBuilder
from .fsm import FiniteStateMachine, build_protocol_fsm
from .hooks import (
    EVENT_APPROVAL,
    EVENT_CONSENSUS_REACHED,
    EVENT_CRITIQUE_SUBMITTED,
    EVENT_DEADLOCK_DETECTED,
    EVENT_DECISION,
    EVENT_ESCALATION,
    EVENT_IMPLEMENTATION_SUBMITTED,
    EVENT_MESSAGE_SENT,
    EVENT_PHASE_CHANGE,
    EVENT_PLAN_SUBMITTED,
    EVENT_REJECTION,
    EVENT_REVIEW_SUBMITTED,
    EVENT_ROUND_END,
    EVENT_ROUND_START,
    EVENT_TABLE_FINALIZED,
    EVENT_TABLE_INITIALIZED,
    EVENT_TABLE_RESET,
    EVENT_VOTE_CAST,
    HookManager,
)
from .interaction import InteractionGraph
from .models import AgentMessage, InteractionType, MessageType, Phase
from .negotiation import NegotiationManager, NegotiationStatus
from .protocol import ProtocolEngine
from .roles import ROLE_ARBITER, ROLE_CRITIC, ROLE_DOER
from .router import MessageRouter
from .scoring import TrustScoring
from .state import TABLE_STATE_FILE, TableState
from .strategies import DefaultStrategy, DeliberationStrategy, get_strategy
from .transcript import TranscriptStore
from .validators import MessageValidator, StateValidator


class AgentTable:
    """Orchestrates multi-agent deliberation for a task.

    Directory layout under ``.ralph-mode/table/``::

        table-state.json     – Current table state
        transcript.jsonl     – Full log of all messages
        trust-scores.json    – Per-agent trust data
        rounds/
            round-001/
                plan.md          – Doer's plan
                critique.md      – Critic's review
                decision.md      – Arbiter's decision (if escalated)
                implementation.md – Doer's implementation notes
                review.md        – Critic's review of implementation
                approval.md      – Arbiter's final approval

    Interaction model:

    - **Threading**: Every message gets a ``message_id``. Replies link
      via ``reply_to`` and ``thread_id`` to form conversation chains.
    - **Negotiation**: Multi-turn dialogues are tracked in
      ``NegotiationManager`` — counter-proposals, clarifications,
      objections, and acknowledgments are all first-class.
    - **Routing**: ``MessageRouter`` determines the correct recipient
      based on phase, strategy, and message type.
    - **FSM**: Protocol phase transitions use a real finite state
      machine with guards and side-effects.
    - **Strategy**: Pluggable ``DeliberationStrategy`` controls when
      to escalate, auto-approve, or require consensus.
    - **Consensus**: ``ConsensusEngine`` with trust-weighted voting.
    - **Trust**: ``TrustScoring`` tracks agent reliability and feeds
      weights into consensus decisions.
    - **Validation**: Messages are validated before recording.
    """

    def __init__(self, ralph_dir: Optional[Path] = None) -> None:
        if ralph_dir is None:
            ralph_dir = Path.cwd() / ".ralph-mode"
        self.ralph_dir = Path(ralph_dir)

        # --- Core persistence ---
        self._state_mgr = TableState(self.ralph_dir)
        self._transcript = TranscriptStore(self._state_mgr.table_dir)

        # --- Protocol logic ---
        self._protocol = ProtocolEngine()
        self._fsm = build_protocol_fsm()

        # --- Interaction tracking ---
        self._interaction = InteractionGraph()
        self._negotiation = NegotiationManager()
        self._router = MessageRouter()

        # --- Quality & trust ---
        self._validator = MessageValidator()
        self._state_validator = StateValidator()
        self._scoring = TrustScoring(self._state_mgr.table_dir)
        self._consensus = ConsensusEngine()

        # --- Strategy & hooks ---
        self._strategy: DeliberationStrategy = DefaultStrategy()
        self._hooks = HookManager()

        # --- Context builder (wired to our getters) ---
        self._context = ContextBuilder(
            get_state=self.get_state,
            get_last_message=self.get_last_message,
            get_messages=self.get_messages,
            get_trust_weight=lambda agent: self._scoring.get_weight(agent),
            get_active_negotiations=lambda: [n.to_dict() for n in self._negotiation.get_active()],
            get_active_threads=lambda: self._interaction.get_active_threads(),
            get_relationship_matrix=lambda: self._interaction.get_relationship_matrix(),
        )

        # --- Convenience aliases ---
        self.table_dir = self._state_mgr.table_dir
        self.rounds_dir = self._state_mgr.rounds_dir
        self.transcript_file = self._transcript.filepath
        self.state_file = self._state_mgr.state_file

        # Wire negotiation callbacks
        self._negotiation.on_deadlock(self._on_negotiation_deadlock)
        self._negotiation.on_escalate(self._on_negotiation_escalate)

    # ------------------------------------------------------------------
    # Sub-module Access
    # ------------------------------------------------------------------

    @property
    def hooks(self) -> HookManager:
        """Access the hook manager for event registration."""
        return self._hooks

    @property
    def consensus(self) -> ConsensusEngine:
        """Access the consensus engine."""
        return self._consensus

    @property
    def trust(self) -> TrustScoring:
        """Access the trust scoring system."""
        return self._scoring

    @property
    def interaction(self) -> InteractionGraph:
        """Access the interaction graph for thread and relationship tracking."""
        return self._interaction

    @property
    def negotiation(self) -> NegotiationManager:
        """Access the negotiation manager for multi-turn dialogues."""
        return self._negotiation

    @property
    def router(self) -> MessageRouter:
        """Access the message router."""
        return self._router

    @property
    def fsm(self) -> FiniteStateMachine:
        """Access the protocol finite state machine."""
        return self._fsm

    @property
    def strategy(self) -> DeliberationStrategy:
        """Current deliberation strategy."""
        return self._strategy

    @strategy.setter
    def strategy(self, value: DeliberationStrategy) -> None:
        self._strategy = value

    def set_strategy(self, name: str) -> None:
        """Set strategy by name (default, strict, lenient, democratic, autocratic)."""
        self._strategy = get_strategy(name)

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------

    def initialize(
        self,
        task_description: str,
        *,
        max_rounds: int = 10,
        require_unanimous: bool = False,
        auto_escalate: bool = True,
    ) -> Dict[str, Any]:
        """Initialize a new Agent Table session.

        Args:
            task_description: The task to be deliberated on.
            max_rounds: Maximum deliberation rounds before forced decision.
            require_unanimous: If True, Critic must approve before Arbiter.
            auto_escalate: If True, automatically escalate on disagreement.

        Returns:
            The initial table state dict.
        """
        state = self._state_mgr.initialize(
            task_description,
            max_rounds=max_rounds,
            require_unanimous=require_unanimous,
            auto_escalate=auto_escalate,
        )
        self._hooks.emit(EVENT_TABLE_INITIALIZED, state=state)
        return state

    # ------------------------------------------------------------------
    # State Management
    # ------------------------------------------------------------------

    def is_active(self) -> bool:
        """Check if an Agent Table session is active."""
        return self._state_mgr.is_active()

    def get_state(self) -> Optional[Dict[str, Any]]:
        """Get current table state."""
        return self._state_mgr.get_state()

    def _save_state(self, state: Dict[str, Any]) -> None:
        self._state_mgr._save_state(state)

    # ------------------------------------------------------------------
    # Round Management
    # ------------------------------------------------------------------

    def new_round(self) -> Dict[str, Any]:
        """Start a new deliberation round.

        Returns:
            Updated state with new round number.

        Raises:
            ValueError: If table is not active or max rounds reached.
        """
        state = self._state_mgr.new_round()

        # Reset per-round consensus
        self._consensus.clear_votes()

        self._hooks.emit(EVENT_ROUND_START, state=state)

        # Deadlock check
        if self._protocol.detect_deadlock(state):
            self._hooks.emit(EVENT_DEADLOCK_DETECTED, state=state)

        return state

    def _round_dir(self, round_number: int) -> Path:
        return self._state_mgr._round_dir(round_number)

    def get_round_dir(self, round_number: Optional[int] = None) -> Path:
        """Get the directory for a specific round (or current)."""
        if round_number is None:
            state = self.get_state()
            round_number = state["current_round"] if state else 1
        return self._round_dir(round_number)

    # ------------------------------------------------------------------
    # Message Handling
    # ------------------------------------------------------------------

    def send_message(self, message: AgentMessage) -> AgentMessage:
        """Record a message in the transcript and round directory.

        Validates the message, registers it in the interaction graph,
        processes it through the negotiation manager, and routes it
        if the recipient isn't explicitly set.

        Args:
            message: The AgentMessage to record.

        Returns:
            The same message (with timestamp filled in).

        Raises:
            ValueError: If the table is not active or validation fails.
        """
        state = self.get_state()
        if not state or not state.get("active"):
            raise ValueError("Agent Table is not active.")

        # Ensure round number is set
        if message.round_number == 0:
            message.round_number = state["current_round"]

        # --- Validation (non-strict: warnings don't block) ---
        validation = self._validator.validate_message(message, state)
        if not validation.valid:
            raise ValueError(f"Message validation failed: {'; '.join(validation.errors)}")

        # --- Routing: fill in recipient if empty ---
        if not message.recipient:
            resolved = self._router.resolve_recipient(message, state)
            if resolved:
                message.recipient = resolved

        # --- Persist ---
        self._transcript.append(message)

        # Write per-round markdown file
        round_dir = self._round_dir(message.round_number)
        self._transcript.write_round_file(message, round_dir)

        # --- Interaction graph ---
        self._interaction.register_message(message)

        # --- Negotiation tracking ---
        self._negotiation.process_response(message)

        # Update state counters
        state["total_messages"] = state.get("total_messages", 0) + 1
        self._save_state(state)

        # Fire hook
        self._hooks.emit(EVENT_MESSAGE_SENT, message=message, state=state)

        return message

    def get_messages(
        self,
        *,
        round_number: Optional[int] = None,
        sender: Optional[str] = None,
        recipient: Optional[str] = None,
        msg_type: Optional[str] = None,
    ) -> List[AgentMessage]:
        """Retrieve messages from transcript with optional filters."""
        return self._transcript.get_messages(
            round_number=round_number,
            sender=sender,
            recipient=recipient,
            msg_type=msg_type,
        )

    def get_last_message(
        self,
        *,
        sender: Optional[str] = None,
        msg_type: Optional[str] = None,
    ) -> Optional[AgentMessage]:
        """Get the most recent message matching the filters."""
        return self._transcript.get_last_message(sender=sender, msg_type=msg_type)

    # ------------------------------------------------------------------
    # Phase Transitions
    # ------------------------------------------------------------------

    def advance_phase(self) -> Dict[str, Any]:
        """Advance to the next phase.

        Phase order: plan → implement → resolve → approve (stays at approve).

        Returns:
            Updated state.
        """
        state = self.get_state()
        if not state or not state.get("active"):
            raise ValueError("Agent Table is not active.")

        old_phase = state["current_phase"]
        state = self._protocol.advance_phase(state)
        self._save_state(state)

        if state["current_phase"] != old_phase:
            self._hooks.emit(
                EVENT_PHASE_CHANGE,
                old_phase=old_phase,
                new_phase=state["current_phase"],
                state=state,
            )
        return state

    def set_phase(self, phase: str) -> Dict[str, Any]:
        """Explicitly set the current phase."""
        state = self.get_state()
        if not state or not state.get("active"):
            raise ValueError("Agent Table is not active.")

        old_phase = state["current_phase"]
        state = self._protocol.set_phase(state, phase)
        self._save_state(state)

        if phase != old_phase:
            self._hooks.emit(
                EVENT_PHASE_CHANGE,
                old_phase=old_phase,
                new_phase=phase,
                state=state,
            )
        return state

    # ------------------------------------------------------------------
    # High-Level Protocol Methods
    # ------------------------------------------------------------------

    def submit_plan(self, plan_content: str) -> AgentMessage:
        """Doer submits an implementation plan for Critic review.

        Also starts a negotiation thread — the Critic's critique will
        be processed as the first response in the negotiation.
        """
        state = self.get_state()
        if not state or not state.get("active"):
            raise ValueError("Agent Table is not active.")

        msg = AgentMessage(
            sender=ROLE_DOER,
            recipient=ROLE_CRITIC,
            msg_type=MessageType.PLAN.value,
            content=plan_content,
            round_number=state["current_round"],
            phase=Phase.PLAN.value,
            interaction_type=InteractionType.REQUEST.value,
        )
        self.send_message(msg)

        # Start a negotiation for this plan
        self._negotiation.start_negotiation(msg, subject=f"Round {state['current_round']} plan")

        self._hooks.emit(EVENT_PLAN_SUBMITTED, message=msg, state=state)
        return msg

    def submit_critique(self, critique_content: str, *, approved: bool = False) -> AgentMessage:
        """Critic submits a critique of the Doer's plan or implementation.

        Uses the strategy to decide whether to escalate when not approved,
        instead of relying solely on the ``auto_escalate`` flag.

        Args:
            critique_content: The critique text.
            approved: Whether the Critic approves the current work.
        """
        state = self.get_state()
        if not state or not state.get("active"):
            raise ValueError("Agent Table is not active.")

        # Link to the last plan/implementation as a reply
        last_doer = self.get_last_message(sender=ROLE_DOER)
        reply_to = last_doer.message_id if last_doer else None
        thread_id = last_doer.thread_id if last_doer else None

        msg = AgentMessage(
            sender=ROLE_CRITIC,
            recipient=ROLE_DOER,
            msg_type=MessageType.CRITIQUE.value,
            content=critique_content,
            round_number=state["current_round"],
            phase=state["current_phase"],
            metadata={"approved": approved},
            reply_to=reply_to,
            thread_id=thread_id,
            interaction_type=(InteractionType.CONCESSION.value if approved else InteractionType.CHALLENGE.value),
        )
        self.send_message(msg)

        # Record trust event
        self._scoring.record_event(
            ROLE_CRITIC,
            "critique",
            aligned_with_outcome=approved,
            details=critique_content[:200],
        )

        self._hooks.emit(EVENT_CRITIQUE_SUBMITTED, message=msg, state=state)

        # Strategy-based escalation instead of hardcoded auto_escalate
        if self._strategy.should_escalate(state, approved):
            reason = self._strategy.get_escalation_reason(state, approved)
            self.escalate(reason=reason)

        return msg

    def submit_implementation(self, implementation_notes: str) -> AgentMessage:
        """Doer submits implementation notes after making changes.

        Starts a new negotiation thread for the implementation review cycle.
        """
        state = self.get_state()
        if not state or not state.get("active"):
            raise ValueError("Agent Table is not active.")

        msg = AgentMessage(
            sender=ROLE_DOER,
            recipient=ROLE_CRITIC,
            msg_type=MessageType.IMPLEMENTATION.value,
            content=implementation_notes,
            round_number=state["current_round"],
            phase=Phase.IMPLEMENT.value,
            interaction_type=InteractionType.REQUEST.value,
        )
        self.send_message(msg)

        # Start a negotiation for the implementation review
        self._negotiation.start_negotiation(msg, subject=f"Round {state['current_round']} implementation review")

        # Advance to implement phase
        state = self.get_state()
        state["current_phase"] = Phase.IMPLEMENT.value
        self._save_state(state)

        self._hooks.emit(EVENT_IMPLEMENTATION_SUBMITTED, message=msg, state=state)
        return msg

    def submit_review(self, review_content: str, *, approved: bool = False) -> AgentMessage:
        """Critic submits a review of the Doer's implementation.

        Uses the strategy to decide whether to escalate, mirroring
        the logic in ``submit_critique``.
        """
        state = self.get_state()
        if not state or not state.get("active"):
            raise ValueError("Agent Table is not active.")

        # Link as a reply to the last implementation
        last_impl = self.get_last_message(sender=ROLE_DOER, msg_type=MessageType.IMPLEMENTATION.value)
        reply_to = last_impl.message_id if last_impl else None
        thread_id = last_impl.thread_id if last_impl else None

        msg = AgentMessage(
            sender=ROLE_CRITIC,
            recipient=ROLE_DOER,
            msg_type=MessageType.REVIEW.value,
            content=review_content,
            round_number=state["current_round"],
            phase=Phase.IMPLEMENT.value,
            metadata={"approved": approved},
            reply_to=reply_to,
            thread_id=thread_id,
            interaction_type=(InteractionType.CONCESSION.value if approved else InteractionType.CHALLENGE.value),
        )
        self.send_message(msg)

        # Record trust event
        self._scoring.record_event(
            ROLE_CRITIC,
            "review",
            aligned_with_outcome=approved,
            details=review_content[:200],
        )

        self._hooks.emit(EVENT_REVIEW_SUBMITTED, message=msg, state=state)

        # Strategy-based escalation
        if self._strategy.should_escalate(state, approved):
            reason = self._strategy.get_escalation_reason(state, approved)
            self.escalate(reason=reason)

        return msg

    def escalate(self, reason: str = "") -> AgentMessage:
        """Escalate to the Arbiter for a final decision."""
        state = self.get_state()
        if not state or not state.get("active"):
            raise ValueError("Agent Table is not active.")

        state["escalation_count"] = state.get("escalation_count", 0) + 1
        state["current_phase"] = Phase.RESOLVE.value
        self._save_state(state)

        msg = AgentMessage(
            sender=ROLE_DOER,
            recipient=ROLE_ARBITER,
            msg_type=MessageType.ESCALATION.value,
            content=reason,
            round_number=state["current_round"],
            phase=Phase.RESOLVE.value,
        )
        result = self.send_message(msg)

        # Record trust event
        self._scoring.record_event(ROLE_CRITIC, "escalation", details=reason)
        self._hooks.emit(EVENT_ESCALATION, message=msg, state=state)

        return result

    def submit_decision(self, decision_content: str, *, side_with: str = "") -> AgentMessage:
        """Arbiter submits a decision resolving a disagreement."""
        state = self.get_state()
        if not state or not state.get("active"):
            raise ValueError("Agent Table is not active.")

        msg = AgentMessage(
            sender=ROLE_ARBITER,
            recipient=ROLE_DOER,
            msg_type=MessageType.DECISION.value,
            content=decision_content,
            round_number=state["current_round"],
            phase=Phase.RESOLVE.value,
            metadata={"side_with": side_with},
        )
        self.send_message(msg)

        # Move to approve phase
        state = self.get_state()
        state["current_phase"] = Phase.APPROVE.value
        self._save_state(state)

        # Track trust — if arbiter overrides critic
        if side_with == ROLE_DOER:
            self._scoring.record_event(
                ROLE_CRITIC,
                "decision",
                aligned_with_outcome=False,
                details="Arbiter sided with doer",
            )
        elif side_with == ROLE_CRITIC:
            self._scoring.record_event(
                ROLE_DOER,
                "decision",
                aligned_with_outcome=False,
                details="Arbiter sided with critic",
            )

        self._hooks.emit(EVENT_DECISION, message=msg, state=state)
        return msg

    def submit_approval(self, notes: str = "") -> AgentMessage:
        """Arbiter gives final approval for the round."""
        state = self.get_state()
        if not state or not state.get("active"):
            raise ValueError("Agent Table is not active.")

        msg = AgentMessage(
            sender=ROLE_ARBITER,
            recipient=ROLE_DOER,
            msg_type=MessageType.APPROVAL.value,
            content=notes or "Approved. Proceed with implementation.",
            round_number=state["current_round"],
            phase=Phase.APPROVE.value,
            metadata={"approved": True},
        )
        self.send_message(msg)

        # Record round summary
        state = self.get_state()
        summary = {
            "round": state["current_round"],
            "outcome": "approved",
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
        state.setdefault("rounds_summary", []).append(summary)
        self._save_state(state)

        # Trust
        self._scoring.record_event(ROLE_ARBITER, "approval")
        self._hooks.emit(EVENT_APPROVAL, message=msg, state=state)
        self._hooks.emit(EVENT_ROUND_END, state=state)

        return msg

    def submit_rejection(self, reason: str) -> AgentMessage:
        """Arbiter rejects the current approach and requests rework."""
        state = self.get_state()
        if not state or not state.get("active"):
            raise ValueError("Agent Table is not active.")

        msg = AgentMessage(
            sender=ROLE_ARBITER,
            recipient=ROLE_DOER,
            msg_type=MessageType.REJECTION.value,
            content=reason,
            round_number=state["current_round"],
            phase=Phase.APPROVE.value,
            metadata={"approved": False},
        )
        self.send_message(msg)

        # Record round summary
        state = self.get_state()
        summary = {
            "round": state["current_round"],
            "outcome": "rejected",
            "reason": reason,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
        state.setdefault("rounds_summary", []).append(summary)
        self._save_state(state)

        # Trust
        self._scoring.record_event(ROLE_ARBITER, "rejection")
        self._hooks.emit(EVENT_REJECTION, message=msg, state=state)
        self._hooks.emit(EVENT_ROUND_END, state=state)

        return msg

    # ------------------------------------------------------------------
    # Interactive Response Methods
    # ------------------------------------------------------------------

    def submit_response(
        self,
        sender: str,
        content: str,
        *,
        in_reply_to: Optional[AgentMessage] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AgentMessage:
        """Submit a generic response within the conversation.

        Use this when an agent responds to a message in a way that
        doesn't neatly fit into plan/critique/review/decision buckets.

        Args:
            sender: The agent sending the response.
            content: The response text.
            in_reply_to: The message being replied to (for threading).
            metadata: Extra key-value data.

        Returns:
            The recorded AgentMessage.
        """
        state = self.get_state()
        if not state or not state.get("active"):
            raise ValueError("Agent Table is not active.")

        if in_reply_to:
            msg = in_reply_to.create_reply(
                sender=sender,
                msg_type=MessageType.RESPONSE.value,
                content=content,
                metadata=metadata,
                interaction_type=InteractionType.RESPONSE.value,
            )
        else:
            msg = AgentMessage(
                sender=sender,
                recipient=self._infer_recipient(sender),
                msg_type=MessageType.RESPONSE.value,
                content=content,
                round_number=state["current_round"],
                phase=state["current_phase"],
                metadata=metadata,
                interaction_type=InteractionType.RESPONSE.value,
            )

        return self.send_message(msg)

    def request_clarification(
        self,
        sender: str,
        question: str,
        *,
        in_reply_to: Optional[AgentMessage] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AgentMessage:
        """Request clarification from another agent.

        Creates a CLARIFICATION message in the thread, flagging
        the negotiation as needing more info before proceeding.

        Args:
            sender: Who is asking for clarification.
            question: The clarification question.
            in_reply_to: The message that prompted the question.
            metadata: Extra data.

        Returns:
            The recorded AgentMessage.
        """
        state = self.get_state()
        if not state or not state.get("active"):
            raise ValueError("Agent Table is not active.")

        if in_reply_to:
            msg = in_reply_to.create_reply(
                sender=sender,
                msg_type=MessageType.CLARIFICATION.value,
                content=question,
                metadata=metadata,
                interaction_type=InteractionType.REQUEST.value,
            )
        else:
            msg = AgentMessage(
                sender=sender,
                recipient=self._infer_recipient(sender),
                msg_type=MessageType.CLARIFICATION.value,
                content=question,
                round_number=state["current_round"],
                phase=state["current_phase"],
                metadata=metadata,
                interaction_type=InteractionType.REQUEST.value,
            )

        return self.send_message(msg)

    def submit_clarification_response(
        self,
        sender: str,
        answer: str,
        *,
        in_reply_to: Optional[AgentMessage] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AgentMessage:
        """Respond to a clarification request.

        Args:
            sender: Who is providing the clarification.
            answer: The clarification answer.
            in_reply_to: The clarification question being answered.
            metadata: Extra data.

        Returns:
            The recorded AgentMessage.
        """
        state = self.get_state()
        if not state or not state.get("active"):
            raise ValueError("Agent Table is not active.")

        if in_reply_to:
            msg = in_reply_to.create_reply(
                sender=sender,
                msg_type=MessageType.CLARIFICATION_RESPONSE.value,
                content=answer,
                metadata=metadata,
                interaction_type=InteractionType.RESPONSE.value,
            )
        else:
            msg = AgentMessage(
                sender=sender,
                recipient=self._infer_recipient(sender),
                msg_type=MessageType.CLARIFICATION_RESPONSE.value,
                content=answer,
                round_number=state["current_round"],
                phase=state["current_phase"],
                metadata=metadata,
                interaction_type=InteractionType.RESPONSE.value,
            )

        return self.send_message(msg)

    def submit_counter_proposal(
        self,
        sender: str,
        proposal: str,
        *,
        in_reply_to: Optional[AgentMessage] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AgentMessage:
        """Submit a counter-proposal as an alternative approach.

        Starts a new negotiation round and records the counter as
        an alternative to what was previously proposed or critiqued.

        Args:
            sender: Who is counter-proposing.
            proposal: The counter-proposal text.
            in_reply_to: The message being countered.
            metadata: Extra data.

        Returns:
            The recorded AgentMessage.
        """
        state = self.get_state()
        if not state or not state.get("active"):
            raise ValueError("Agent Table is not active.")

        if in_reply_to:
            msg = in_reply_to.create_reply(
                sender=sender,
                msg_type=MessageType.COUNTER_PROPOSAL.value,
                content=proposal,
                metadata=metadata,
                interaction_type=InteractionType.NEGOTIATION.value,
            )
        else:
            msg = AgentMessage(
                sender=sender,
                recipient=self._infer_recipient(sender),
                msg_type=MessageType.COUNTER_PROPOSAL.value,
                content=proposal,
                round_number=state["current_round"],
                phase=state["current_phase"],
                metadata=metadata,
                interaction_type=InteractionType.NEGOTIATION.value,
            )

        return self.send_message(msg)

    def submit_objection(
        self,
        sender: str,
        reason: str,
        *,
        in_reply_to: Optional[AgentMessage] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AgentMessage:
        """Submit a formal objection to the current approach.

        Objections trigger escalation to the Arbiter via the
        negotiation manager's escalation callback.

        Args:
            sender: Who is objecting.
            reason: The reason for the objection.
            in_reply_to: The message being objected to.
            metadata: Extra data.

        Returns:
            The recorded AgentMessage.
        """
        state = self.get_state()
        if not state or not state.get("active"):
            raise ValueError("Agent Table is not active.")

        if in_reply_to:
            msg = in_reply_to.create_reply(
                sender=sender,
                msg_type=MessageType.OBJECTION.value,
                content=reason,
                metadata=metadata,
                interaction_type=InteractionType.CHALLENGE.value,
            )
        else:
            msg = AgentMessage(
                sender=sender,
                recipient=self._infer_recipient(sender),
                msg_type=MessageType.OBJECTION.value,
                content=reason,
                round_number=state["current_round"],
                phase=state["current_phase"],
                metadata=metadata,
                interaction_type=InteractionType.CHALLENGE.value,
            )

        return self.send_message(msg)

    def submit_acknowledgment(
        self,
        sender: str,
        notes: str = "",
        *,
        in_reply_to: Optional[AgentMessage] = None,
    ) -> AgentMessage:
        """Acknowledge a message — signal agreement without full approval.

        Args:
            sender: Who is acknowledging.
            notes: Optional acknowledgment notes.
            in_reply_to: The message being acknowledged.

        Returns:
            The recorded AgentMessage.
        """
        state = self.get_state()
        if not state or not state.get("active"):
            raise ValueError("Agent Table is not active.")

        if in_reply_to:
            msg = in_reply_to.create_reply(
                sender=sender,
                msg_type=MessageType.ACKNOWLEDGMENT.value,
                content=notes or "Acknowledged.",
                interaction_type=InteractionType.CONCESSION.value,
            )
        else:
            msg = AgentMessage(
                sender=sender,
                recipient=self._infer_recipient(sender),
                msg_type=MessageType.ACKNOWLEDGMENT.value,
                content=notes or "Acknowledged.",
                round_number=state["current_round"],
                phase=state["current_phase"],
                interaction_type=InteractionType.CONCESSION.value,
            )

        return self.send_message(msg)

    # ------------------------------------------------------------------
    # Internal Helpers
    # ------------------------------------------------------------------

    def _infer_recipient(self, sender: str) -> str:
        """Infer the default recipient based on the sender's role."""
        if sender == ROLE_DOER:
            return ROLE_CRITIC
        elif sender == ROLE_CRITIC:
            return ROLE_DOER
        else:
            return ROLE_DOER  # Arbiter defaults to Doer

    def _on_negotiation_deadlock(self, neg) -> None:
        """Called by NegotiationManager when a negotiation deadlocks."""
        state = self.get_state()
        if state and state.get("active"):
            self._hooks.emit(EVENT_DEADLOCK_DETECTED, state=state, negotiation=neg)
            # Auto-escalate deadlocked negotiations
            self.escalate(reason=f"Negotiation deadlocked after {neg.round_count} rounds: {neg.subject}")

    def _on_negotiation_escalate(self, neg) -> None:
        """Called by NegotiationManager when an objection triggers escalation."""
        state = self.get_state()
        if state and state.get("active"):
            self.escalate(reason=f"Objection raised in negotiation: {neg.subject}")

    # ------------------------------------------------------------------
    # Finalization
    # ------------------------------------------------------------------

    def finalize(self, outcome: str = "approved") -> Dict[str, Any]:
        """Finalize the Agent Table session."""
        state = self.get_state()
        if not state:
            raise ValueError("No active Agent Table session.")

        state["active"] = False
        state["completed_at"] = datetime.now(timezone.utc).isoformat()
        state["outcome"] = outcome
        self._save_state(state)

        self._hooks.emit(EVENT_TABLE_FINALIZED, state=state, outcome=outcome)
        return state

    def reset(self) -> None:
        """Remove all Agent Table data."""
        if self.table_dir.exists():
            shutil.rmtree(self.table_dir)
        self._hooks.emit(EVENT_TABLE_RESET)

    # ------------------------------------------------------------------
    # Context Building
    # ------------------------------------------------------------------

    def build_doer_context(self) -> str:
        return self._context.build_doer_context()

    def build_critic_context(self) -> str:
        return self._context.build_critic_context()

    def build_arbiter_context(self) -> str:
        return self._context.build_arbiter_context()

    # ------------------------------------------------------------------
    # Full Protocol Round
    # ------------------------------------------------------------------

    def run_protocol_round(
        self,
        plan: str,
        critique: str,
        critique_approved: bool,
        implementation: str = "",
        review: str = "",
        review_approved: bool = False,
        arbiter_decision: str = "",
        arbiter_side_with: str = "",
        arbiter_approves: bool = True,
    ) -> Dict[str, Any]:
        """Run a complete deliberation round programmatically.

        Useful for testing and automated workflows.
        """
        self.new_round()

        # Phase 1: Plan
        self.submit_plan(plan)
        self.submit_critique(critique, approved=critique_approved)

        # If critic approved, proceed to implementation
        if critique_approved and implementation:
            self.submit_implementation(implementation)

            if review:
                self.submit_review(review, approved=review_approved)

        # Arbiter decision (if there was an escalation or at the end)
        if arbiter_decision:
            self.submit_decision(arbiter_decision, side_with=arbiter_side_with)

        # Final approval or rejection
        if arbiter_approves:
            self.submit_approval()
        else:
            self.submit_rejection(arbiter_decision or "Rejected by Arbiter.")

        return self.get_state()

    # ------------------------------------------------------------------
    # Status & Summary
    # ------------------------------------------------------------------

    def status(self) -> Optional[Dict[str, Any]]:
        """Get a human-readable status summary."""
        state = self.get_state()
        if not state:
            return None

        msg_by_sender = self._transcript.count_by_sender()
        neg_summary = self._negotiation.summary()
        active_threads = self._interaction.get_active_threads()
        disputed_threads = self._interaction.get_disputed_threads()

        return {
            "active": state.get("active", False),
            "task": state.get("task", ""),
            "current_round": state.get("current_round", 0),
            "max_rounds": state.get("max_rounds", 10),
            "current_phase": state.get("current_phase", ""),
            "outcome": state.get("outcome"),
            "total_messages": state.get("total_messages", 0),
            "escalation_count": state.get("escalation_count", 0),
            "messages_by_agent": msg_by_sender,
            "rounds_summary": state.get("rounds_summary", []),
            "started_at": state.get("started_at"),
            "completed_at": state.get("completed_at"),
            "strategy": self._strategy.name,
            "negotiations": neg_summary,
            "threads": {
                "total": self._interaction.thread_count,
                "active": len(active_threads),
                "disputed": len(disputed_threads),
            },
            "fsm_state": self._fsm.current_state,
        }

    def get_transcript_text(self) -> str:
        """Get the full transcript as readable text."""
        return self._transcript.to_text()
