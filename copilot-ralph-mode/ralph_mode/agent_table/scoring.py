"""Trust scoring — per-agent reliability tracking across sessions."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


class AgentTrustRecord:
    """Tracks trust metrics for a single agent."""

    def __init__(self, agent: str) -> None:
        self.agent = agent
        self.total_votes: int = 0
        self.accurate_votes: int = 0
        self.total_decisions: int = 0
        self.overridden_decisions: int = 0
        self.escalations_caused: int = 0
        self.approvals_given: int = 0
        self.rejections_given: int = 0
        self.trust_score: float = 1.0  # 0.0 – 2.0 range
        self.history: List[Dict[str, Any]] = []

    @property
    def accuracy(self) -> float:
        """Ratio of votes that aligned with the final outcome."""
        if self.total_votes == 0:
            return 1.0
        return self.accurate_votes / self.total_votes

    @property
    def override_rate(self) -> float:
        """Ratio of decisions overridden by higher authority."""
        if self.total_decisions == 0:
            return 0.0
        return self.overridden_decisions / self.total_decisions

    def record_event(
        self,
        event_type: str,
        *,
        aligned_with_outcome: bool = True,
        details: str = "",
    ) -> None:
        """Record a trust-affecting event.

        Args:
            event_type: "vote", "decision", "escalation", "approval", "rejection"
            aligned_with_outcome: Whether the agent's action aligned with final result
            details: Optional description
        """
        self.history.append(
            {
                "type": event_type,
                "aligned": aligned_with_outcome,
                "details": details,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

        if event_type == "vote":
            self.total_votes += 1
            if aligned_with_outcome:
                self.accurate_votes += 1
        elif event_type == "decision":
            self.total_decisions += 1
            if not aligned_with_outcome:
                self.overridden_decisions += 1
        elif event_type == "escalation":
            self.escalations_caused += 1
        elif event_type == "approval":
            self.approvals_given += 1
        elif event_type == "rejection":
            self.rejections_given += 1

        self._recalculate_trust()

    def _recalculate_trust(self) -> None:
        """Update trust score based on history."""
        # Base score
        score = 1.0

        # Accuracy bonus/penalty
        if self.total_votes >= 3:
            score += (self.accuracy - 0.5) * 0.5  # ±0.25

        # Override penalty
        score -= self.override_rate * 0.3

        # Escalation pattern
        if self.total_decisions > 0:
            esc_ratio = self.escalations_caused / max(self.total_decisions, 1)
            if esc_ratio > 0.5:
                score -= 0.2  # Too many escalations

        # Clamp to [0.1, 2.0]
        self.trust_score = max(0.1, min(2.0, score))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent": self.agent,
            "trust_score": round(self.trust_score, 3),
            "accuracy": round(self.accuracy, 3),
            "override_rate": round(self.override_rate, 3),
            "total_votes": self.total_votes,
            "accurate_votes": self.accurate_votes,
            "total_decisions": self.total_decisions,
            "overridden_decisions": self.overridden_decisions,
            "escalations_caused": self.escalations_caused,
            "approvals_given": self.approvals_given,
            "rejections_given": self.rejections_given,
            "history_count": len(self.history),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentTrustRecord":
        record = cls(data["agent"])
        record.trust_score = data.get("trust_score", 1.0)
        record.total_votes = data.get("total_votes", 0)
        record.accurate_votes = data.get("accurate_votes", 0)
        record.total_decisions = data.get("total_decisions", 0)
        record.overridden_decisions = data.get("overridden_decisions", 0)
        record.escalations_caused = data.get("escalations_caused", 0)
        record.approvals_given = data.get("approvals_given", 0)
        record.rejections_given = data.get("rejections_given", 0)
        record.history = data.get("history", [])
        return record


# ---------------------------------------------------------------------------
# TrustScoring
# ---------------------------------------------------------------------------


class TrustScoring:
    """Manages trust records for all agents across sessions.

    Trust data is persisted to ``trust-scores.json`` inside the table
    directory, surviving across multiple Agent Table sessions.
    """

    TRUST_FILE = "trust-scores.json"

    def __init__(self, table_dir: Path) -> None:
        self.table_dir = Path(table_dir)
        self.filepath = self.table_dir / self.TRUST_FILE
        self._records: Dict[str, AgentTrustRecord] = {}
        self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_trust(self, agent: str) -> float:
        """Return the trust score for an agent (default 1.0)."""
        return self._get_or_create(agent).trust_score

    def get_weight(self, agent: str) -> float:
        """Return a consensus weight for the agent based on trust."""
        return max(0.1, self.get_trust(agent))

    def record_event(
        self,
        agent: str,
        event_type: str,
        *,
        aligned_with_outcome: bool = True,
        details: str = "",
    ) -> None:
        """Record a trust-affecting event for *agent*."""
        record = self._get_or_create(agent)
        record.record_event(
            event_type,
            aligned_with_outcome=aligned_with_outcome,
            details=details,
        )
        self._save()

    def get_record(self, agent: str) -> AgentTrustRecord:
        """Return the full trust record for an agent."""
        return self._get_or_create(agent)

    def get_all_records(self) -> Dict[str, AgentTrustRecord]:
        """Return all trust records."""
        return dict(self._records)

    def summary(self) -> Dict[str, Dict[str, Any]]:
        """Return a summary of all trust records."""
        return {name: record.to_dict() for name, record in self._records.items()}

    def reset(self) -> None:
        """Clear all trust data."""
        self._records.clear()
        if self.filepath.exists():
            self.filepath.unlink()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> None:
        if not self.filepath.exists():
            return
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            for name, record_data in data.items():
                self._records[name] = AgentTrustRecord.from_dict(record_data)
        except (json.JSONDecodeError, IOError):
            pass

    def _save(self) -> None:
        self.table_dir.mkdir(parents=True, exist_ok=True)
        data = {}
        for name, record in self._records.items():
            d = record.to_dict()
            d["history"] = record.history
            data[name] = d
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _get_or_create(self, agent: str) -> AgentTrustRecord:
        if agent not in self._records:
            self._records[agent] = AgentTrustRecord(agent)
        return self._records[agent]
