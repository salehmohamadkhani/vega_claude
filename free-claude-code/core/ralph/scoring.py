"""Deterministic scoring model for Ralph Runtime task evaluation.

All scores are 0-100 integers. No AI or network calls — pure arithmetic.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field


class HallucinationRisk(enum.Enum):
    """Estimated risk of hallucination or incorrect output."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


_HALLUCINATION_RISK_PENALTY: dict[HallucinationRisk, float] = {
    HallucinationRisk.LOW: 0.0,
    HallucinationRisk.MEDIUM: 0.15,
    HallucinationRisk.HIGH: 0.35,
}

_DEFAULT_WEIGHTS = {
    "implementation": 0.30,
    "test": 0.20,
    "kpi": 0.25,
    "confidence": 0.25,
}


@dataclass
class ScoreCard:
    """A scored evaluation of a task iteration.

    All raw scores must be 0-100. The final weighted score combines
    them with penalties for risk.
    """

    implementation_score: int = 0
    test_score: int = 0
    kpi_score: int = 0
    risk_score: int = 0
    confidence_score: int = 0
    hallucination_risk: HallucinationRisk = HallucinationRisk.LOW
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self._validate_ranges()

    # ---- Validation ----

    def _validate_ranges(self) -> None:
        _check_range(self.implementation_score, "implementation_score")
        _check_range(self.test_score, "test_score")
        _check_range(self.kpi_score, "kpi_score")
        _check_range(self.risk_score, "risk_score")
        _check_range(self.confidence_score, "confidence_score")

    # ---- Weighted computation ----

    def final_weighted_score(
        self,
        weights: dict[str, float] | None = None,
    ) -> float:
        """Calculate the weighted final score (0-100), penalised by risk.

        Parameters
        ----------
        weights:
            Optional dict with keys implementation/test/kpi/confidence.
            Defaults to equal weighting (0.25 each).

        Returns
        -------
        Float in 0-100 range.
        """
        w = weights or _DEFAULT_WEIGHTS
        raw = (
            self.implementation_score * w.get("implementation", 0.25)
            + self.test_score * w.get("test", 0.25)
            + self.kpi_score * w.get("kpi", 0.25)
            + self.confidence_score * w.get("confidence", 0.25)
        )
        penalty = _HALLUCINATION_RISK_PENALTY[self.hallucination_risk]
        risk_penalty = self.risk_score * penalty
        return max(0.0, round(raw - risk_penalty, 1))

    def is_passing(self, threshold: int = 80) -> bool:
        """Return True if the final weighted score meets the threshold.

        High hallucination risk prevents passing unless overridden
        via notes (any note containing 'OVERRIDE' bypasses this check).
        """
        if self.hallucination_risk == HallucinationRisk.HIGH:
            has_override = any("OVERRIDE" in n for n in self.notes)
            if not has_override:
                return False
        return self.final_weighted_score() >= threshold


# ---- Internal helpers ----


def _check_range(value: int, name: str) -> None:
    if not isinstance(value, int):
        raise TypeError(f"{name} must be an int, got {type(value).__name__}")
    if not 0 <= value <= 100:
        raise ValueError(f"{name} must be between 0 and 100, got {value}")


def _default_score_weight(name: str) -> float:
    return _DEFAULT_WEIGHTS.get(name, 0.25)
