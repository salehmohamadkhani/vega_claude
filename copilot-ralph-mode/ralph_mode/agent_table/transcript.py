"""Transcript store — JSONL-based message log with query capabilities."""

import json
from pathlib import Path
from typing import Dict, List, Optional

from .models import AgentMessage

TRANSCRIPT_FILE = "transcript.jsonl"


class TranscriptStore:
    """Persistent message log stored as newline-delimited JSON.

    Every message exchanged in the Agent Table is appended to a
    single JSONL file for auditability and easy querying.
    """

    def __init__(self, table_dir: Path) -> None:
        self.table_dir = Path(table_dir)
        self.filepath = self.table_dir / TRANSCRIPT_FILE

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def append(self, message: AgentMessage) -> None:
        """Append a message to the transcript."""
        self.table_dir.mkdir(parents=True, exist_ok=True)
        with open(self.filepath, "a", encoding="utf-8") as f:
            f.write(json.dumps(message.to_dict(), ensure_ascii=False) + "\n")

    # ------------------------------------------------------------------
    # Read / Query
    # ------------------------------------------------------------------

    def get_all(self) -> List[AgentMessage]:
        """Return all messages in the transcript."""
        return self._query()

    def get_messages(
        self,
        *,
        round_number: Optional[int] = None,
        sender: Optional[str] = None,
        recipient: Optional[str] = None,
        msg_type: Optional[str] = None,
    ) -> List[AgentMessage]:
        """Retrieve messages with optional filters."""
        return self._query(
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
        messages = self._query(sender=sender, msg_type=msg_type)
        return messages[-1] if messages else None

    def count(self) -> int:
        """Count total messages."""
        return len(self._query())

    def count_by_sender(self) -> Dict[str, int]:
        """Count messages grouped by sender."""
        counts: Dict[str, int] = {}
        for msg in self._query():
            counts[msg.sender] = counts.get(msg.sender, 0) + 1
        return counts

    def get_round_messages(self, round_number: int) -> List[AgentMessage]:
        """Get all messages for a specific round."""
        return self._query(round_number=round_number)

    def get_messages_between(self, sender: str, recipient: str) -> List[AgentMessage]:
        """Get all messages between two specific agents."""
        return self._query(sender=sender, recipient=recipient)

    # ------------------------------------------------------------------
    # Formatted Output
    # ------------------------------------------------------------------

    def to_text(self) -> str:
        """Render the full transcript as human-readable text."""
        messages = self._query()
        if not messages:
            return "No messages yet."

        lines: List[str] = []
        current_round = 0
        for msg in messages:
            if msg.round_number != current_round:
                current_round = msg.round_number
                lines.append(f"\n{'=' * 60}")
                lines.append(f"  ROUND {current_round}")
                lines.append(f"{'=' * 60}\n")
            emoji = _role_emoji(msg.sender)
            lines.append(f"{emoji} [{msg.sender}] → [{msg.recipient}] ({msg.msg_type})")
            preview = msg.content[:200]
            if len(msg.content) > 200:
                preview += "..."
            lines.append(f"   {preview}")
            lines.append("")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Markdown File Writer
    # ------------------------------------------------------------------

    def write_round_file(self, message: AgentMessage, round_dir: Path) -> Path:
        """Write a message to its round directory as Markdown.

        Returns:
            Path to the written file.
        """
        round_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{message.msg_type}.md"
        filepath = round_dir / filename

        mode = "a" if filepath.exists() else "w"
        if mode == "a":
            header = f"\n---\n\n## {message.sender} → " f"{message.recipient} ({message.msg_type})\n\n"
        else:
            header = (
                f"# {message.msg_type.title()}\n\n"
                f"**From:** {message.sender}  \n"
                f"**To:** {message.recipient}  \n"
                f"**Round:** {message.round_number}  \n"
                f"**Phase:** {message.phase}  \n"
                f"**Time:** {message.timestamp}  \n\n---\n\n"
            )
        with open(filepath, mode, encoding="utf-8") as f:
            f.write(header + message.content + "\n")
        return filepath

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _query(
        self,
        *,
        round_number: Optional[int] = None,
        sender: Optional[str] = None,
        recipient: Optional[str] = None,
        msg_type: Optional[str] = None,
    ) -> List[AgentMessage]:
        if not self.filepath.exists():
            return []

        messages: List[AgentMessage] = []
        with open(self.filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    msg = AgentMessage.from_dict(data)
                    if round_number is not None and msg.round_number != round_number:
                        continue
                    if sender is not None and msg.sender != sender:
                        continue
                    if recipient is not None and msg.recipient != recipient:
                        continue
                    if msg_type is not None and msg.msg_type != msg_type:
                        continue
                    messages.append(msg)
                except (json.JSONDecodeError, KeyError):
                    pass
        return messages


def _role_emoji(role: str) -> str:
    return {"doer": "🛠️", "critic": "🔍", "arbiter": "⚖️"}.get(role, "")
