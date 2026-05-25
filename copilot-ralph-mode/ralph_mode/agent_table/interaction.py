"""Interaction graph — tracks conversation threads and agent relationships."""

from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple

from .models import AgentMessage


class ConversationThread:
    """A single conversation thread between agents.

    A thread starts with an initial message (the root) and includes
    all replies in the chain.  Threads enable multi-turn dialogue
    where agents can respond, challenge, and negotiate.
    """

    def __init__(self, thread_id: str, root_message: AgentMessage) -> None:
        self.thread_id = thread_id
        self.root = root_message
        self._messages: List[AgentMessage] = [root_message]
        self._by_id: Dict[str, AgentMessage] = {root_message.message_id: root_message}

    def add(self, message: AgentMessage) -> None:
        """Add a message to the thread."""
        self._messages.append(message)
        self._by_id[message.message_id] = message

    def get(self, message_id: str) -> Optional[AgentMessage]:
        """Get a specific message by ID within this thread."""
        return self._by_id.get(message_id)

    @property
    def messages(self) -> List[AgentMessage]:
        """All messages in chronological order."""
        return list(self._messages)

    @property
    def participants(self) -> Set[str]:
        """Set of all agents that participated in this thread."""
        return {m.sender for m in self._messages}

    @property
    def depth(self) -> int:
        """Number of messages in the thread."""
        return len(self._messages)

    @property
    def last_message(self) -> AgentMessage:
        """Most recent message in the thread."""
        return self._messages[-1]

    @property
    def last_sender(self) -> str:
        """Who sent the most recent message."""
        return self._messages[-1].sender

    @property
    def is_resolved(self) -> bool:
        """Whether the thread ended with an agreement.

        Checks if the last message is an approval, acknowledgment,
        or a critique/review with approved=True.
        """
        last = self._messages[-1]
        if last.msg_type in ("approval", "acknowledgment"):
            return True
        if last.msg_type in ("critique", "review"):
            return last.metadata.get("approved", False)
        return False

    @property
    def has_disagreement(self) -> bool:
        """Whether the thread contains opposing views."""
        approvals = set()
        for m in self._messages:
            if "approved" in m.metadata:
                approvals.add(m.metadata["approved"])
        return True in approvals and False in approvals

    def get_reply_chain(self, message_id: str) -> List[AgentMessage]:
        """Get the chain of replies leading to a specific message."""
        chain: List[AgentMessage] = []
        current = self._by_id.get(message_id)
        while current:
            chain.append(current)
            if current.reply_to:
                current = self._by_id.get(current.reply_to)
            else:
                break
        chain.reverse()
        return chain

    def to_text(self) -> str:
        """Render the thread as readable text."""
        lines: List[str] = []
        for msg in self._messages:
            indent = "  → " if msg.is_reply else ""
            lines.append(f"{indent}[{msg.sender}→{msg.recipient}] ({msg.msg_type}): {msg.content[:120]}")
        return "\n".join(lines)


class InteractionGraph:
    """Tracks all agent interactions, conversation threads, and relationships.

    Maintains a directed graph of who communicated with whom and
    organises messages into conversation threads for contextual
    multi-turn dialogue.
    """

    def __init__(self) -> None:
        self._threads: Dict[str, ConversationThread] = {}
        self._message_to_thread: Dict[str, str] = {}
        # Directed edge counts: (sender, recipient) → count
        self._edge_counts: Dict[Tuple[str, str], int] = defaultdict(int)
        # Per-agent message counts
        self._sent_counts: Dict[str, int] = defaultdict(int)
        self._received_counts: Dict[str, int] = defaultdict(int)
        # Track all messages
        self._all_messages: List[AgentMessage] = []

    # ------------------------------------------------------------------
    # Message Registration
    # ------------------------------------------------------------------

    def register_message(self, message: AgentMessage) -> ConversationThread:
        """Register a message in the interaction graph.

        Automatically assigns it to the correct thread (creating a
        new thread if necessary).

        Returns:
            The ConversationThread this message belongs to.
        """
        self._all_messages.append(message)
        self._edge_counts[(message.sender, message.recipient)] += 1
        self._sent_counts[message.sender] += 1
        self._received_counts[message.recipient] += 1

        thread_id = message.thread_id

        if thread_id in self._threads:
            thread = self._threads[thread_id]
            thread.add(message)
        else:
            thread = ConversationThread(thread_id, message)
            self._threads[thread_id] = thread

        self._message_to_thread[message.message_id] = thread_id
        return thread

    # ------------------------------------------------------------------
    # Thread Queries
    # ------------------------------------------------------------------

    def get_thread(self, thread_id: str) -> Optional[ConversationThread]:
        """Get a conversation thread by ID."""
        return self._threads.get(thread_id)

    def get_thread_for_message(self, message_id: str) -> Optional[ConversationThread]:
        """Get the thread that contains a specific message."""
        tid = self._message_to_thread.get(message_id)
        return self._threads.get(tid) if tid else None

    def get_active_threads(self) -> List[ConversationThread]:
        """Get threads that haven't been resolved yet."""
        return [t for t in self._threads.values() if not t.is_resolved]

    def get_disputed_threads(self) -> List[ConversationThread]:
        """Get threads with disagreements."""
        return [t for t in self._threads.values() if t.has_disagreement]

    def get_threads_involving(self, agent: str) -> List[ConversationThread]:
        """Get all threads where an agent participated."""
        return [t for t in self._threads.values() if agent in t.participants]

    def get_threads_between(self, agent_a: str, agent_b: str) -> List[ConversationThread]:
        """Get threads where both agents participated."""
        return [t for t in self._threads.values() if agent_a in t.participants and agent_b in t.participants]

    @property
    def all_threads(self) -> List[ConversationThread]:
        return list(self._threads.values())

    @property
    def thread_count(self) -> int:
        return len(self._threads)

    # ------------------------------------------------------------------
    # Relationship Queries
    # ------------------------------------------------------------------

    def interaction_count(self, sender: str, recipient: str) -> int:
        """How many messages *sender* has sent to *recipient*."""
        return self._edge_counts.get((sender, recipient), 0)

    def total_sent(self, agent: str) -> int:
        """Total messages sent by an agent."""
        return self._sent_counts.get(agent, 0)

    def total_received(self, agent: str) -> int:
        """Total messages received by an agent."""
        return self._received_counts.get(agent, 0)

    def most_active_pair(self) -> Optional[Tuple[str, str]]:
        """Return the sender-recipient pair with most interactions."""
        if not self._edge_counts:
            return None
        return max(self._edge_counts, key=self._edge_counts.get)

    def get_relationship_matrix(self) -> Dict[str, Dict[str, int]]:
        """Return a matrix of interaction counts between all agents."""
        agents = set()
        for s, r in self._edge_counts:
            agents.add(s)
            agents.add(r)

        matrix: Dict[str, Dict[str, int]] = {}
        for a in sorted(agents):
            matrix[a] = {}
            for b in sorted(agents):
                matrix[a][b] = self._edge_counts.get((a, b), 0)
        return matrix

    # ------------------------------------------------------------------
    # Analysis
    # ------------------------------------------------------------------

    def get_conversation_flow(self, round_number: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get the conversation flow as a sequence of interactions.

        Returns a list of dicts with sender, recipient, type, and content preview.
        """
        messages = self._all_messages
        if round_number is not None:
            messages = [m for m in messages if m.round_number == round_number]

        return [
            {
                "sender": m.sender,
                "recipient": m.recipient,
                "type": m.msg_type,
                "thread_id": m.thread_id,
                "is_reply": m.is_reply,
                "content_preview": m.content[:80],
            }
            for m in messages
        ]

    def find_unanswered_messages(self, agent: str) -> List[AgentMessage]:
        """Find messages sent to *agent* that haven't been replied to.

        Useful for detecting when an agent owes a response.
        """
        replied_to_ids: Set[str] = set()
        for msg in self._all_messages:
            if msg.reply_to:
                replied_to_ids.add(msg.reply_to)

        return [
            m
            for m in self._all_messages
            if m.recipient == agent
            and m.message_id not in replied_to_ids
            and m.msg_type not in ("approval", "rejection", "acknowledgment")
        ]

    def detect_circular_arguments(self, max_depth: int = 6) -> List[ConversationThread]:
        """Detect threads where agents keep going back and forth.

        A circular argument is a thread where the same sender-recipient
        pattern repeats more than *max_depth* / 2 times.
        """
        circular: List[ConversationThread] = []
        for thread in self._threads.values():
            if thread.depth < max_depth:
                continue
            # Check for repetitive sender pattern
            senders = [m.sender for m in thread.messages[-max_depth:]]
            unique_senders = set(senders)
            if len(unique_senders) == 2:
                # Two agents alternating = potential circular argument
                pair_count = sum(1 for i in range(len(senders) - 1) if senders[i] != senders[i + 1])
                if pair_count >= max_depth - 1:
                    circular.append(thread)
        return circular

    def summary(self) -> Dict[str, Any]:
        """Return a summary of all interactions."""
        return {
            "total_messages": len(self._all_messages),
            "total_threads": len(self._threads),
            "active_threads": len(self.get_active_threads()),
            "disputed_threads": len(self.get_disputed_threads()),
            "sent_counts": dict(self._sent_counts),
            "received_counts": dict(self._received_counts),
            "edge_counts": {f"{s}→{r}": c for (s, r), c in self._edge_counts.items()},
        }
