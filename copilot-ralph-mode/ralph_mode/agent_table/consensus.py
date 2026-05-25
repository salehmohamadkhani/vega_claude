"""Consensus engine — voting, quorum, weighted scoring, and confidence."""

from typing import Any, Dict, List, Optional, Tuple

from .models import AgentMessage, Confidence, MessageType

# ---------------------------------------------------------------------------
# Vote
# ---------------------------------------------------------------------------


class Vote:
    """A single agent's vote on a proposal."""

    def __init__(
        self,
        voter: str,
        approved: bool,
        *,
        confidence: str = Confidence.MEDIUM.value,
        weight: float = 1.0,
        reason: str = "",
    ) -> None:
        self.voter = voter
        self.approved = approved
        self.confidence = confidence
        self.weight = weight
        self.reason = reason

    @property
    def weighted_score(self) -> float:
        """+weight for approve, -weight for reject, multiplied by confidence."""
        conf_multiplier = {
            Confidence.LOW.value: 0.5,
            Confidence.MEDIUM.value: 1.0,
            Confidence.HIGH.value: 1.5,
            Confidence.CERTAIN.value: 2.0,
        }.get(self.confidence, 1.0)
        return (1.0 if self.approved else -1.0) * self.weight * conf_multiplier

    def to_dict(self) -> Dict[str, Any]:
        return {
            "voter": self.voter,
            "approved": self.approved,
            "confidence": self.confidence,
            "weight": self.weight,
            "reason": self.reason,
            "weighted_score": self.weighted_score,
        }


# ---------------------------------------------------------------------------
# ConsensusEngine
# ---------------------------------------------------------------------------


class ConsensusEngine:
    """Evaluates votes and determines consensus for a proposal.

    Supports multiple quorum modes:

    - **simple_majority**: > 50 % of votes approve
    - **supermajority**: ≥ ⅔ of votes approve
    - **unanimous**: All votes approve
    - **weighted**: Uses weighted scores (confidence × trust weight)
    """

    def __init__(
        self,
        *,
        quorum_mode: str = "simple_majority",
        min_voters: int = 2,
        arbiter_weight: float = 1.5,
    ) -> None:
        self.quorum_mode = quorum_mode
        self.min_voters = min_voters
        self.arbiter_weight = arbiter_weight
        self._votes: List[Vote] = []

    # ------------------------------------------------------------------
    # Vote Collection
    # ------------------------------------------------------------------

    def add_vote(self, vote: Vote) -> None:
        """Record a vote, replacing any previous vote from the same voter."""
        self._votes = [v for v in self._votes if v.voter != vote.voter]
        self._votes.append(vote)

    def add_vote_from_message(self, message: AgentMessage) -> Vote:
        """Extract a vote from an AgentMessage and record it."""
        from .roles import ROLE_ARBITER

        approved = message.metadata.get("approved", False)
        confidence = message.metadata.get("confidence", Confidence.MEDIUM.value)
        weight = self.arbiter_weight if message.sender == ROLE_ARBITER else 1.0
        vote = Vote(
            voter=message.sender,
            approved=approved,
            confidence=confidence,
            weight=weight,
            reason=message.content[:200],
        )
        self.add_vote(vote)
        return vote

    def clear_votes(self) -> None:
        """Reset all votes for a new round of voting."""
        self._votes.clear()

    @property
    def votes(self) -> List[Vote]:
        return list(self._votes)

    # ------------------------------------------------------------------
    # Quorum Check
    # ------------------------------------------------------------------

    def has_quorum(self) -> bool:
        """Return True if enough voters have participated."""
        return len(self._votes) >= self.min_voters

    # ------------------------------------------------------------------
    # Consensus Evaluation
    # ------------------------------------------------------------------

    def evaluate(self) -> Dict[str, Any]:
        """Evaluate the current votes and determine consensus.

        Returns:
            A dict with keys:
                - approved (bool): Overall consensus result
                - method (str): The quorum mode used
                - details: Mode-specific breakdown
                - has_quorum (bool): Whether quorum was reached
                - votes: List of vote dicts
        """
        if not self.has_quorum():
            return {
                "approved": False,
                "method": self.quorum_mode,
                "has_quorum": False,
                "reason": (f"Quorum not reached: {len(self._votes)}/{self.min_voters}"),
                "votes": [v.to_dict() for v in self._votes],
            }

        method = self.quorum_mode
        if method == "simple_majority":
            result = self._simple_majority()
        elif method == "supermajority":
            result = self._supermajority()
        elif method == "unanimous":
            result = self._unanimous()
        elif method == "weighted":
            result = self._weighted()
        else:
            result = self._simple_majority()

        result["method"] = method
        result["has_quorum"] = True
        result["votes"] = [v.to_dict() for v in self._votes]
        return result

    # ------------------------------------------------------------------
    # Quorum Modes
    # ------------------------------------------------------------------

    def _simple_majority(self) -> Dict[str, Any]:
        approvals = sum(1 for v in self._votes if v.approved)
        total = len(self._votes)
        approved = approvals > (total / 2)
        return {
            "approved": approved,
            "approvals": approvals,
            "rejections": total - approvals,
            "total": total,
            "ratio": approvals / total if total else 0,
        }

    def _supermajority(self) -> Dict[str, Any]:
        approvals = sum(1 for v in self._votes if v.approved)
        total = len(self._votes)
        approved = approvals >= (total * 2 / 3)
        return {
            "approved": approved,
            "approvals": approvals,
            "rejections": total - approvals,
            "total": total,
            "ratio": approvals / total if total else 0,
            "threshold": "2/3",
        }

    def _unanimous(self) -> Dict[str, Any]:
        approvals = sum(1 for v in self._votes if v.approved)
        total = len(self._votes)
        approved = approvals == total
        return {
            "approved": approved,
            "approvals": approvals,
            "rejections": total - approvals,
            "total": total,
            "dissent": [v.voter for v in self._votes if not v.approved],
        }

    def _weighted(self) -> Dict[str, Any]:
        total_score = sum(v.weighted_score for v in self._votes)
        max_possible = sum(abs(v.weighted_score) for v in self._votes)
        approved = total_score > 0
        return {
            "approved": approved,
            "weighted_score": round(total_score, 3),
            "max_possible_score": round(max_possible, 3),
            "normalized": (round(total_score / max_possible, 3) if max_possible else 0),
            "score_breakdown": {v.voter: round(v.weighted_score, 3) for v in self._votes},
        }

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def summary_line(self) -> str:
        """One-line summary of current consensus state."""
        result = self.evaluate()
        if not result["has_quorum"]:
            return f"⏳ Waiting for quorum ({len(self._votes)}/{self.min_voters})"
        status = "✅ Approved" if result["approved"] else "❌ Rejected"
        return f"{status} ({self.quorum_mode})"
