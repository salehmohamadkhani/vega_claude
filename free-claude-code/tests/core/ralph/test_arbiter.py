"""Tests for core.ralph.arbiter."""

from __future__ import annotations

from core.ralph.arbiter import ArbiterAction, ArbiterEngine
from core.ralph.critic import CriticReview
from core.ralph.loop_guard import LoopGuardDecision
from core.ralph.models import CriticDecision
from core.ralph.scoring import ScoreCard


class TestArbiterEngine:
    def make_engine(self) -> ArbiterEngine:
        return ArbiterEngine()

    def make_approving_review(self) -> CriticReview:
        return CriticReview(
            approved=True,
            decision=CriticDecision(
                approved=True, reason="All good", confidence=0.95
            ),
        )

    def make_rejecting_review(self, confidence: float = 0.65) -> CriticReview:
        return CriticReview(
            approved=False,
            decision=CriticDecision(
                approved=False,
                reason="Tests failed",
                confidence=confidence,
                required_fixes=["fix tests"],
            ),
        )

    def test_approve_when_critic_approves(self) -> None:
        engine = self.make_engine()
        review = self.make_approving_review()
        decision = engine.decide(critic_review=review)
        assert decision.action == ArbiterAction.APPROVE

    def test_retry_when_critic_rejects(self) -> None:
        engine = self.make_engine()
        review = self.make_rejecting_review()
        decision = engine.decide(critic_review=review)
        assert decision.action == ArbiterAction.RETRY

    def test_stop_when_loop_guard_stops(self) -> None:
        engine = self.make_engine()
        loop_guard = LoopGuardDecision(action="stop")  # string to check compat
        # Use dataclass properly
        from dataclasses import replace
        loop_guard = replace(
            LoopGuardDecision(),
            action=__import__(
                "core.ralph.loop_guard", fromlist=["LoopAction"]
            ).LoopAction.STOP,
            reason="Max iterations reached.",
        )
        from core.ralph.loop_guard import LoopAction
        loop_guard = LoopGuardDecision(
            action=LoopAction.STOP, reason="Max iterations reached."
        )
        decision = engine.decide(
            critic_review=self.make_rejecting_review(),
            loop_guard_decision=loop_guard,
        )
        assert decision.action == ArbiterAction.STOP

    def test_escalate_when_loop_guard_escalates(self) -> None:
        engine = self.make_engine()
        from core.ralph.loop_guard import LoopAction

        loop_guard = LoopGuardDecision(
            action=LoopAction.ESCALATE, reason="Repeated errors."
        )
        decision = engine.decide(
            critic_review=self.make_rejecting_review(),
            loop_guard_decision=loop_guard,
        )
        assert decision.action == ArbiterAction.ESCALATE

    def test_debug_when_loop_guard_debugs(self) -> None:
        engine = self.make_engine()
        from core.ralph.loop_guard import LoopAction

        loop_guard = LoopGuardDecision(
            action=LoopAction.DEBUG, reason="Too many failures."
        )
        decision = engine.decide(
            critic_review=self.make_rejecting_review(),
            loop_guard_decision=loop_guard,
        )
        assert decision.action == ArbiterAction.DEBUG

    def test_stop_after_too_many_critic_rejections(self) -> None:
        engine = ArbiterEngine(max_critic_rejections_before_stop=2)
        review = self.make_rejecting_review()
        decision = engine.decide(
            critic_review=review, critic_rejection_count=2
        )
        assert decision.action == ArbiterAction.STOP
        assert "rejected" in decision.reason.lower()

    def test_escalate_after_too_many_retries(self) -> None:
        engine = ArbiterEngine(max_retries_before_escalate=3)
        review = self.make_rejecting_review()
        decision = engine.decide(critic_review=review, retry_count=3)
        assert decision.action == ArbiterAction.ESCALATE

    def test_debug_after_moderate_retries(self) -> None:
        engine = ArbiterEngine(
            max_retries_before_debug=2, max_retries_before_escalate=10
        )
        review = self.make_rejecting_review()
        decision = engine.decide(critic_review=review, retry_count=2)
        assert decision.action == ArbiterAction.DEBUG

    def test_low_score_blocks_approval(self) -> None:
        engine = self.make_engine()
        review = self.make_approving_review()
        score = ScoreCard(
            implementation_score=30,
            test_score=20,
            kpi_score=10,
            risk_score=90,
            confidence_score=20,
        )
        decision = engine.decide(
            critic_review=review, score_card=score
        )
        # Score below threshold → retry even though critic approved
        assert decision.action != ArbiterAction.APPROVE

    def test_debug_on_very_low_critic_confidence(self) -> None:
        engine = self.make_engine()
        review = self.make_rejecting_review(confidence=0.3)
        decision = engine.decide(critic_review=review)
        assert decision.action == ArbiterAction.DEBUG

    def test_suggested_fixes_included(self) -> None:
        engine = self.make_engine()
        review = self.make_rejecting_review()
        decision = engine.decide(critic_review=review)
        assert len(decision.suggested_fixes) > 0
        assert "fix tests" in decision.suggested_fixes[0]

    def test_arbiter_action_enum_values(self) -> None:
        assert ArbiterAction.APPROVE.value == "approve"
        assert ArbiterAction.RETRY.value == "retry"
        assert ArbiterAction.DEBUG.value == "debug"
        assert ArbiterAction.ESCALATE.value == "escalate"
        assert ArbiterAction.STOP.value == "stop"
