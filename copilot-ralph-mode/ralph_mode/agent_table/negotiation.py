"""Negotiation manager — multi-turn dialogue, counter-proposals, and resolutions."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from .models import AgentMessage, InteractionType, MessageType
from .roles import ROLE_ARBITER, ROLE_CRITIC, ROLE_DOER


class NegotiationStatus(str, Enum):
    """Status of an ongoing negotiation."""

    OPEN = "open"
    AWAITING_RESPONSE = "awaiting_response"
    COUNTER_PROPOSED = "counter_proposed"
    CLARIFICATION_NEEDED = "clarification_needed"
    DEADLOCKED = "deadlocked"
    RESOLVED_ACCEPTED = "resolved_accepted"
    RESOLVED_REJECTED = "resolved_rejected"
    ESCALATED = "escalated"


@dataclass
class NegotiationRound:
    """A single exchange within a negotiation."""

    proposal: AgentMessage
    response: Optional[AgentMessage] = None
    counter: Optional[AgentMessage] = None
    clarifications: List[AgentMessage] = field(default_factory=list)
    status: str = NegotiationStatus.OPEN.value
    opened_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    resolved_at: Optional[str] = None

    @property
    def is_resolved(self) -> bool:
        return self.status in (
            NegotiationStatus.RESOLVED_ACCEPTED.value,
            NegotiationStatus.RESOLVED_REJECTED.value,
            NegotiationStatus.ESCALATED.value,
        )

    @property
    def turn_count(self) -> int:
        """Number of messages exchanged in this round."""
        count = 1  # proposal
        if self.response:
            count += 1
        if self.counter:
            count += 1
        count += len(self.clarifications)
        return count


@dataclass
class Negotiation:
    """A complete negotiation between agents on a specific issue.

    A negotiation consists of one or more rounds of proposal →
    critique → counter-proposal until resolution or escalation.
    """

    negotiation_id: str
    thread_id: str
    initiator: str
    respondent: str
    subject: str
    rounds: List[NegotiationRound] = field(default_factory=list)
    status: str = NegotiationStatus.OPEN.value
    max_rounds: int = 5
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    resolved_at: Optional[str] = None
    resolution: Optional[str] = None

    @property
    def current_round(self) -> Optional[NegotiationRound]:
        return self.rounds[-1] if self.rounds else None

    @property
    def round_count(self) -> int:
        return len(self.rounds)

    @property
    def is_stale(self) -> bool:
        """Whether negotiation has exceeded max rounds without resolution."""
        return self.round_count >= self.max_rounds and self.status == NegotiationStatus.OPEN.value

    @property
    def total_exchanges(self) -> int:
        return sum(r.turn_count for r in self.rounds)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "negotiation_id": self.negotiation_id,
            "thread_id": self.thread_id,
            "initiator": self.initiator,
            "respondent": self.respondent,
            "subject": self.subject,
            "status": self.status,
            "round_count": self.round_count,
            "max_rounds": self.max_rounds,
            "total_exchanges": self.total_exchanges,
            "created_at": self.created_at,
            "resolved_at": self.resolved_at,
            "resolution": self.resolution,
        }


class NegotiationManager:
    """Manages multi-turn negotiations between agents.

    A negotiation follows this flow:

    1. **Agent A proposes** (plan, implementation, counter-proposal)
    2. **Agent B responds** with one of:
       - **Accept** — negotiation resolved
       - **Reject** — can optionally counter-propose
       - **Request clarification** — needs more info before deciding
       - **Counter-propose** — alternative approach
       - **Object** — fundamental disagreement, may escalate
    3. **Agent A** can then respond to the counter or provide clarification
    4. Repeat until resolved, deadlocked, or escalated to Arbiter

    The manager prevents infinite loops by tracking round counts
    and detecting deadlock patterns.
    """

    def __init__(self, *, max_negotiation_rounds: int = 5) -> None:
        self._negotiations: Dict[str, Negotiation] = {}
        self._thread_to_negotiation: Dict[str, str] = {}
        self.max_negotiation_rounds = max_negotiation_rounds

        # Callbacks
        self._on_deadlock: Optional[Callable] = None
        self._on_resolve: Optional[Callable] = None
        self._on_escalate: Optional[Callable] = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start_negotiation(
        self,
        proposal: AgentMessage,
        subject: str = "",
    ) -> Negotiation:
        """Start a new negotiation based on an initial proposal.

        Args:
            proposal: The opening message (plan, implementation, etc.).
            subject: Human-readable description of what's being negotiated.

        Returns:
            The new Negotiation object.
        """
        neg = Negotiation(
            negotiation_id=proposal.thread_id,
            thread_id=proposal.thread_id,
            initiator=proposal.sender,
            respondent=proposal.recipient,
            subject=subject or f"Negotiation on {proposal.msg_type}",
            max_rounds=self.max_negotiation_rounds,
        )
        neg.rounds.append(
            NegotiationRound(
                proposal=proposal,
                status=NegotiationStatus.AWAITING_RESPONSE.value,
            )
        )
        neg.status = NegotiationStatus.AWAITING_RESPONSE.value

        self._negotiations[neg.negotiation_id] = neg
        self._thread_to_negotiation[proposal.thread_id] = neg.negotiation_id
        return neg

    def process_response(self, message: AgentMessage) -> Optional[Negotiation]:
        """Process a response within an existing negotiation.

        The message type determines the effect:
        - critique/review with approved=True → resolve as accepted
        - critique/review with approved=False → mark as counter needed
        - counter_proposal → start new negotiation round
        - clarification → add to current round
        - clarification_response → add to current round
        - objection → mark as needing escalation
        - acknowledgment → resolve as accepted
        - approval → resolve as accepted
        - rejection → resolve as rejected

        Returns:
            Updated Negotiation, or None if message doesn't belong to one.
        """
        neg = self.get_for_thread(message.thread_id)
        if not neg or not neg.current_round:
            return None

        current = neg.current_round
        msg_type = message.msg_type

        # --- Accept / Approve ---
        if msg_type in (MessageType.APPROVAL.value, MessageType.ACKNOWLEDGMENT.value):
            current.response = message
            current.status = NegotiationStatus.RESOLVED_ACCEPTED.value
            current.resolved_at = datetime.now(timezone.utc).isoformat()
            neg.status = NegotiationStatus.RESOLVED_ACCEPTED.value
            neg.resolved_at = current.resolved_at
            neg.resolution = "accepted"
            if self._on_resolve:
                self._on_resolve(neg)
            return neg

        # --- Rejection ---
        if msg_type == MessageType.REJECTION.value:
            current.response = message
            current.status = NegotiationStatus.RESOLVED_REJECTED.value
            current.resolved_at = datetime.now(timezone.utc).isoformat()
            neg.status = NegotiationStatus.RESOLVED_REJECTED.value
            neg.resolved_at = current.resolved_at
            neg.resolution = "rejected"
            return neg

        # --- Critique / Review (dual: can accept or trigger counter) ---
        if msg_type in (MessageType.CRITIQUE.value, MessageType.REVIEW.value):
            approved = message.metadata.get("approved", False)
            current.response = message
            if approved:
                current.status = NegotiationStatus.RESOLVED_ACCEPTED.value
                current.resolved_at = datetime.now(timezone.utc).isoformat()
                neg.status = NegotiationStatus.RESOLVED_ACCEPTED.value
                neg.resolved_at = current.resolved_at
                neg.resolution = "accepted_by_critic"
            else:
                current.status = NegotiationStatus.COUNTER_PROPOSED.value
                neg.status = NegotiationStatus.AWAITING_RESPONSE.value
                # Check deadlock
                if neg.round_count >= neg.max_rounds:
                    neg.status = NegotiationStatus.DEADLOCKED.value
                    if self._on_deadlock:
                        self._on_deadlock(neg)
            return neg

        # --- Counter-proposal ---
        if msg_type == MessageType.COUNTER_PROPOSAL.value:
            current.counter = message
            current.status = NegotiationStatus.COUNTER_PROPOSED.value
            # Start a new negotiation round
            new_round = NegotiationRound(
                proposal=message,
                status=NegotiationStatus.AWAITING_RESPONSE.value,
            )
            neg.rounds.append(new_round)
            neg.status = NegotiationStatus.AWAITING_RESPONSE.value
            # Check deadlock
            if neg.round_count >= neg.max_rounds:
                neg.status = NegotiationStatus.DEADLOCKED.value
                if self._on_deadlock:
                    self._on_deadlock(neg)
            return neg

        # --- Clarification request ---
        if msg_type == MessageType.CLARIFICATION.value:
            current.clarifications.append(message)
            current.status = NegotiationStatus.CLARIFICATION_NEEDED.value
            neg.status = NegotiationStatus.CLARIFICATION_NEEDED.value
            return neg

        # --- Clarification response ---
        if msg_type == MessageType.CLARIFICATION_RESPONSE.value:
            current.clarifications.append(message)
            current.status = NegotiationStatus.AWAITING_RESPONSE.value
            neg.status = NegotiationStatus.AWAITING_RESPONSE.value
            return neg

        # --- Objection ---
        if msg_type == MessageType.OBJECTION.value:
            current.response = message
            current.status = NegotiationStatus.ESCALATED.value
            neg.status = NegotiationStatus.ESCALATED.value
            if self._on_escalate:
                self._on_escalate(neg)
            return neg

        # --- Response (generic) ---
        if msg_type == MessageType.RESPONSE.value:
            current.response = message
            current.status = NegotiationStatus.AWAITING_RESPONSE.value
            return neg

        # Unknown type — just record it
        current.clarifications.append(message)
        return neg

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get(self, negotiation_id: str) -> Optional[Negotiation]:
        """Get a negotiation by ID."""
        return self._negotiations.get(negotiation_id)

    def get_for_thread(self, thread_id: str) -> Optional[Negotiation]:
        """Get the negotiation associated with a thread."""
        nid = self._thread_to_negotiation.get(thread_id)
        return self._negotiations.get(nid) if nid else None

    def get_active(self) -> List[Negotiation]:
        """Get all active (unresolved) negotiations."""
        return [
            n
            for n in self._negotiations.values()
            if n.status
            not in (
                NegotiationStatus.RESOLVED_ACCEPTED.value,
                NegotiationStatus.RESOLVED_REJECTED.value,
            )
        ]

    def get_deadlocked(self) -> List[Negotiation]:
        """Get negotiations that are deadlocked."""
        return [n for n in self._negotiations.values() if n.status == NegotiationStatus.DEADLOCKED.value]

    def get_awaiting_response_from(self, agent: str) -> List[Negotiation]:
        """Get negotiations waiting for a response from a specific agent."""
        result: List[Negotiation] = []
        for neg in self._negotiations.values():
            if neg.status != NegotiationStatus.AWAITING_RESPONSE.value:
                continue
            current = neg.current_round
            if current and current.proposal.recipient == agent and not current.response:
                result.append(neg)
        return result

    def get_by_participants(self, agent_a: str, agent_b: str) -> List[Negotiation]:
        """Get negotiations between two specific agents."""
        return [n for n in self._negotiations.values() if {n.initiator, n.respondent} == {agent_a, agent_b}]

    @property
    def all_negotiations(self) -> List[Negotiation]:
        return list(self._negotiations.values())

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def on_deadlock(self, callback: Callable) -> None:
        """Register a callback for deadlock detection."""
        self._on_deadlock = callback

    def on_resolve(self, callback: Callable) -> None:
        """Register a callback for resolution."""
        self._on_resolve = callback

    def on_escalate(self, callback: Callable) -> None:
        """Register a callback for escalation."""
        self._on_escalate = callback

    # ------------------------------------------------------------------
    # Analysis
    # ------------------------------------------------------------------

    def summary(self) -> Dict[str, Any]:
        """Summary statistics of all negotiations."""
        total = len(self._negotiations)
        resolved = sum(
            1
            for n in self._negotiations.values()
            if n.status
            in (
                NegotiationStatus.RESOLVED_ACCEPTED.value,
                NegotiationStatus.RESOLVED_REJECTED.value,
            )
        )
        deadlocked = sum(1 for n in self._negotiations.values() if n.status == NegotiationStatus.DEADLOCKED.value)
        escalated = sum(1 for n in self._negotiations.values() if n.status == NegotiationStatus.ESCALATED.value)
        return {
            "total": total,
            "active": total - resolved - deadlocked - escalated,
            "resolved": resolved,
            "deadlocked": deadlocked,
            "escalated": escalated,
            "avg_rounds": (sum(n.round_count for n in self._negotiations.values()) / total if total else 0),
        }
