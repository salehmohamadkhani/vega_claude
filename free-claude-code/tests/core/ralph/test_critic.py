"""Tests for core.ralph.critic."""

from __future__ import annotations

from core.ralph.critic import CriticEngine
from core.ralph.scoring import HallucinationRisk, ScoreCard
from core.ralph.verification import VerificationResult, VerificationStatus


class TestCriticEngine:
    def make_engine(self) -> CriticEngine:
        return CriticEngine()

    def test_review_verification_all_pass(self) -> None:
        engine = self.make_engine()
        result = VerificationResult(
            status=VerificationStatus.PASSED,
            command_results={"echo ok": True, "echo done": True},
        )
        review = engine.review_verification(result)
        assert review.approved is True
        assert review.passed_command_count == 2
        assert review.total_command_count == 2

    def test_review_verification_some_fail(self) -> None:
        engine = self.make_engine()
        result = VerificationResult(
            status=VerificationStatus.FAILED,
            command_results={"pass": True, "fail": False},
        )
        review = engine.review_verification(result)
        assert review.approved is False
        assert review.passed_command_count == 1
        assert review.total_command_count == 2

    def test_review_verification_with_acceptance_criteria(self) -> None:
        engine = self.make_engine()
        result = VerificationResult(
            status=VerificationStatus.PASSED,
            command_results={"echo ok": True},
            stdout_summary="all tests pass",
        )
        review = engine.review_verification(
            result,
            acceptance_criteria=["all tests pass"],
        )
        assert review.approved is True
        assert len(review.failed_criteria) == 0

    def test_review_verification_no_checks_defined(self) -> None:
        engine = self.make_engine()
        result = VerificationResult(status=VerificationStatus.NOT_RUN)
        review = engine.review_verification(result)
        assert review.approved is False
        assert "no verification" in review.decision.reason.lower()

    def test_review_scoring_passing(self) -> None:
        engine = self.make_engine()
        score = ScoreCard(
            implementation_score=90,
            test_score=85,
            kpi_score=80,
            risk_score=10,
            confidence_score=90,
        )
        review = engine.review_scoring(score, min_passing_score=80)
        assert review.approved is True

    def test_review_scoring_failing(self) -> None:
        engine = self.make_engine()
        score = ScoreCard(
            implementation_score=30,
            test_score=20,
            kpi_score=10,
            risk_score=80,
            confidence_score=20,
        )
        review = engine.review_scoring(score, min_passing_score=80)
        assert review.approved is False

    def test_review_scoring_high_hallucination_risk(self) -> None:
        engine = self.make_engine()
        score = ScoreCard(
            implementation_score=90,
            test_score=85,
            kpi_score=80,
            risk_score=10,
            confidence_score=90,
            hallucination_risk=HallucinationRisk.HIGH,
        )
        review = engine.review_scoring(score)
        assert review.approved is False
        assert any("hallucination" in w.lower() for w in review.warnings)

    def test_confidence_high_when_all_pass(self) -> None:
        engine = self.make_engine()
        result = VerificationResult(
            status=VerificationStatus.PASSED,
            command_results={"a": True, "b": True},
        )
        review = engine.review_verification(result)
        assert review.decision.confidence >= 0.8

    def test_confidence_low_when_none_pass(self) -> None:
        engine = self.make_engine()
        result = VerificationResult(
            status=VerificationStatus.FAILED,
            command_results={"a": False, "b": False},
        )
        review = engine.review_verification(result)
        assert review.decision.confidence < 0.5

    def test_smoke_results_counted(self) -> None:
        engine = self.make_engine()
        result = VerificationResult(
            status=VerificationStatus.PASSED,
            smoke_results={"api": True, "cli": False},
        )
        review = engine.review_verification(result)
        assert review.passed_smoke_count == 1
        assert review.total_smoke_count == 2

    def test_no_criteria_fails_silently(self) -> None:
        engine = self.make_engine()
        result = VerificationResult(
            status=VerificationStatus.PASSED,
            command_results={"echo ok": True},
        )
        review = engine.review_verification(result, acceptance_criteria=[])
        assert review.approved is True
        assert len(review.failed_criteria) == 0

    def test_criteria_mention_in_stdout(self) -> None:
        engine = self.make_engine()
        result = VerificationResult(
            status=VerificationStatus.PASSED,
            command_results={"echo ok": True},
            stdout_summary="provider integration works",
        )
        review = engine.review_verification(
            result,
            acceptance_criteria=["provider integration works"],
        )
        assert review.approved is True
