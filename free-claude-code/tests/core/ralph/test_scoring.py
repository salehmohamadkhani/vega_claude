"""Tests for core.ralph.scoring."""

from __future__ import annotations

import pytest

from core.ralph.scoring import HallucinationRisk, ScoreCard


class TestScoreCardValidation:
    def test_valid_scores_pass(self) -> None:
        card = ScoreCard(
            implementation_score=85,
            test_score=70,
            kpi_score=90,
            risk_score=20,
            confidence_score=75,
        )
        assert card.implementation_score == 85
        assert card.test_score == 70
        assert card.kpi_score == 90

    def test_out_of_range_implementation_raises(self) -> None:
        with pytest.raises(ValueError, match="implementation_score"):
            ScoreCard(implementation_score=150)

    def test_out_of_range_test_raises(self) -> None:
        with pytest.raises(ValueError, match="test_score"):
            ScoreCard(test_score=-1)

    def test_out_of_range_kpi_raises(self) -> None:
        with pytest.raises(ValueError, match="kpi_score"):
            ScoreCard(kpi_score=101)

    def test_negative_risk_raises(self) -> None:
        with pytest.raises(ValueError, match="risk_score"):
            ScoreCard(risk_score=-5)

    def test_non_int_type_raises(self) -> None:
        with pytest.raises(TypeError, match="implementation_score"):
            ScoreCard(implementation_score=85.5)  # type: ignore[arg-type]


class TestScoreCardWeights:
    def test_final_weighted_score_default_weights(self) -> None:
        card = ScoreCard(
            implementation_score=100,
            test_score=100,
            kpi_score=100,
            risk_score=0,
            confidence_score=100,
        )
        assert card.final_weighted_score() == 100.0

    def test_final_weighted_score_mixed(self) -> None:
        card = ScoreCard(
            implementation_score=80,
            test_score=60,
            kpi_score=70,
            risk_score=10,
            confidence_score=90,
        )
        # raw = 80*0.3 + 60*0.2 + 70*0.25 + 90*0.25 = 24+12+17.5+22.5 = 76.0
        # penalty = 10*0.0 (LOW) = 0
        assert card.final_weighted_score() == 76.0

    def test_custom_weights(self) -> None:
        card = ScoreCard(
            implementation_score=100,
            test_score=0,
            kpi_score=0,
            risk_score=0,
            confidence_score=0,
        )
        result = card.final_weighted_score({"implementation": 1.0})
        assert result == 100.0


class TestScoreCardRisk:
    def test_high_risk_reduces_score(self) -> None:
        card_low = ScoreCard(
            implementation_score=80,
            test_score=80,
            kpi_score=80,
            risk_score=50,
            confidence_score=80,
            hallucination_risk=HallucinationRisk.LOW,
        )
        card_high = ScoreCard(
            implementation_score=80,
            test_score=80,
            kpi_score=80,
            risk_score=50,
            confidence_score=80,
            hallucination_risk=HallucinationRisk.HIGH,
        )
        assert card_high.final_weighted_score() < card_low.final_weighted_score()

    def test_medium_risk_penalty(self) -> None:
        card = ScoreCard(
            implementation_score=100,
            test_score=100,
            kpi_score=100,
            risk_score=40,
            confidence_score=100,
            hallucination_risk=HallucinationRisk.MEDIUM,
        )
        # raw = 100, penalty = 40 * 0.15 = 6.0
        assert card.final_weighted_score() == 94.0


class TestScoreCardPassing:
    def test_passing_at_default_threshold(self) -> None:
        card = ScoreCard(
            implementation_score=90,
            test_score=90,
            kpi_score=90,
            risk_score=5,
            confidence_score=90,
        )
        assert card.is_passing() is True

    def test_failing_below_threshold(self) -> None:
        card = ScoreCard(
            implementation_score=30,
            test_score=30,
            kpi_score=30,
            risk_score=50,
            confidence_score=30,
        )
        assert card.is_passing() is False

    def test_passing_at_custom_threshold(self) -> None:
        card = ScoreCard(
            implementation_score=60,
            test_score=60,
            kpi_score=60,
            risk_score=5,
            confidence_score=60,
        )
        assert card.is_passing(threshold=50) is True
        assert card.is_passing(threshold=70) is False

    def test_high_hallucination_risk_prevents_passing(self) -> None:
        card = ScoreCard(
            implementation_score=100,
            test_score=100,
            kpi_score=100,
            risk_score=0,
            confidence_score=100,
            hallucination_risk=HallucinationRisk.HIGH,
        )
        assert card.is_passing() is False

    def test_high_hallucination_override_via_notes(self) -> None:
        card = ScoreCard(
            implementation_score=100,
            test_score=100,
            kpi_score=100,
            risk_score=0,
            confidence_score=100,
            hallucination_risk=HallucinationRisk.HIGH,
            notes=["OVERRIDE: reviewed manually"],
        )
        assert card.is_passing() is True
