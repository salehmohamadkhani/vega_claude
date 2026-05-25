"""Data models for the Agent Table deliberation protocol."""

import json
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class Phase(str, Enum):
    """Phases within a single deliberation round."""

    PLAN = "plan"
    IMPLEMENT = "implement"
    RESOLVE = "resolve"
    APPROVE = "approve"


class MessageType(str, Enum):
    """Types of messages exchanged between agents."""

    PLAN = "plan"
    CRITIQUE = "critique"
    RESPONSE = "response"
    DECISION = "decision"
    IMPLEMENTATION = "implementation"
    REVIEW = "review"
    APPROVAL = "approval"
    REJECTION = "rejection"
    ESCALATION = "escalation"
    VOTE = "vote"
    COUNTER_PROPOSAL = "counter_proposal"
    CLARIFICATION = "clarification"
    CLARIFICATION_RESPONSE = "clarification_response"
    AMENDMENT = "amendment"
    OBJECTION = "objection"
    ACKNOWLEDGMENT = "acknowledgment"


class Severity(str, Enum):
    """Issue severity levels used by the Critic."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class Confidence(str, Enum):
    """Confidence levels for decisions and votes."""

    CERTAIN = "certain"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class InteractionType(str, Enum):
    """Types of interactions between agents."""

    REQUEST = "request"
    RESPONSE = "response"
    CHALLENGE = "challenge"
    CONCESSION = "concession"
    NEGOTIATION = "negotiation"
    INFORMATION = "information"
    DIRECTIVE = "directive"


# ---------------------------------------------------------------------------
# AgentMessage
# ---------------------------------------------------------------------------


def _short_id() -> str:
    """Generate a short unique message ID."""
    return uuid.uuid4().hex[:12]


class AgentMessage:
    """A single message in the agent deliberation.

    Supports conversation threading via ``message_id``, ``reply_to``,
    and ``thread_id`` fields, enabling multi-turn dialogues between agents.

    Attributes:
        sender: The role that sent this message.
        recipient: The role this message is addressed to.
        msg_type: The type of message (plan, critique, decision, etc.).
        content: The text content of the message.
        round_number: The round this message belongs to.
        phase: The phase during which this message was sent.
        metadata: Arbitrary key-value metadata.
        timestamp: ISO-8601 timestamp of when the message was created.
        message_id: Unique identifier for this message.
        reply_to: message_id of the message this replies to (if any).
        thread_id: Groups related messages into a conversation thread.
        interaction_type: Categorizes how this message relates to the
            conversation (request, response, challenge, etc.).
        priority: Message priority (0 = normal, higher = more urgent).
    """

    __slots__ = (
        "sender",
        "recipient",
        "msg_type",
        "content",
        "round_number",
        "phase",
        "metadata",
        "timestamp",
        "message_id",
        "reply_to",
        "thread_id",
        "interaction_type",
        "priority",
    )

    def __init__(
        self,
        sender: str,
        recipient: str,
        msg_type: str,
        content: str,
        *,
        round_number: int = 0,
        phase: str = "",
        metadata: Optional[Dict[str, Any]] = None,
        timestamp: Optional[str] = None,
        message_id: Optional[str] = None,
        reply_to: Optional[str] = None,
        thread_id: Optional[str] = None,
        interaction_type: Optional[str] = None,
        priority: int = 0,
    ) -> None:
        self.sender = sender
        self.recipient = recipient
        self.msg_type = msg_type
        self.content = content
        self.round_number = round_number
        self.phase = phase
        self.metadata = metadata or {}
        self.timestamp = timestamp or datetime.now(timezone.utc).isoformat()
        self.message_id = message_id or _short_id()
        self.reply_to = reply_to
        self.thread_id = thread_id or self.message_id  # First msg = thread root
        self.interaction_type = interaction_type
        self.priority = priority

    # ------------------------------------------------------------------
    # Reply Helper
    # ------------------------------------------------------------------

    def create_reply(
        self,
        sender: str,
        msg_type: str,
        content: str,
        *,
        metadata: Optional[Dict[str, Any]] = None,
        interaction_type: Optional[str] = None,
    ) -> "AgentMessage":
        """Create a reply message in the same thread.

        The reply inherits the round_number, phase, and thread_id
        from this message and sets reply_to to this message's id.
        """
        return AgentMessage(
            sender=sender,
            recipient=self.sender,  # Reply goes back to original sender
            msg_type=msg_type,
            content=content,
            round_number=self.round_number,
            phase=self.phase,
            metadata=metadata,
            reply_to=self.message_id,
            thread_id=self.thread_id,
            interaction_type=interaction_type,
        )

    @property
    def is_reply(self) -> bool:
        """Return True if this message is a reply to another."""
        return self.reply_to is not None

    @property
    def is_thread_root(self) -> bool:
        """Return True if this message starts a new thread."""
        return self.thread_id == self.message_id

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a JSON-compatible dictionary."""
        d = {
            "sender": self.sender,
            "recipient": self.recipient,
            "msg_type": self.msg_type,
            "content": self.content,
            "round_number": self.round_number,
            "phase": self.phase,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
            "message_id": self.message_id,
            "thread_id": self.thread_id,
        }
        if self.reply_to is not None:
            d["reply_to"] = self.reply_to
        if self.interaction_type is not None:
            d["interaction_type"] = self.interaction_type
        if self.priority != 0:
            d["priority"] = self.priority
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentMessage":
        """Deserialize from a dictionary."""
        return cls(
            sender=data["sender"],
            recipient=data["recipient"],
            msg_type=data["msg_type"],
            content=data["content"],
            round_number=data.get("round_number", 0),
            phase=data.get("phase", ""),
            metadata=data.get("metadata", {}),
            timestamp=data.get("timestamp"),
            message_id=data.get("message_id"),
            reply_to=data.get("reply_to"),
            thread_id=data.get("thread_id"),
            interaction_type=data.get("interaction_type"),
            priority=data.get("priority", 0),
        )

    def __repr__(self) -> str:
        reply = f" re:{self.reply_to[:6]}" if self.reply_to else ""
        return f"<AgentMessage {self.sender}→{self.recipient} " f"[{self.msg_type}] round={self.round_number}{reply}>"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, AgentMessage):
            return NotImplemented
        return (
            self.sender == other.sender
            and self.recipient == other.recipient
            and self.msg_type == other.msg_type
            and self.content == other.content
            and self.round_number == other.round_number
        )
