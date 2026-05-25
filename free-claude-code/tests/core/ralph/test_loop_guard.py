"""Tests for core.ralph.loop_guard."""

from __future__ import annotations

import pytest

from core.ralph.loop_guard import LoopAction, LoopGuard


class TestLoopGuardInit:
    def test_default_max_iterations(self) -> None:
        guard = LoopGuard()
        assert guard._max_iterations == 10

    def test_custom_max_iterations(self) -> None:
        guard = LoopGuard(max_iterations=5)
        assert guard._max_iterations == 5

    def test_invalid_max_iterations(self) -> None:
        with pytest.raises(ValueError, match="max_iterations"):
            LoopGuard(max_iterations=0)


class TestLoopGuardContinue:
    def test_continues_under_max_iterations(self) -> None:
        guard = LoopGuard(max_iterations=10)
        decision = guard.evaluate(current_iteration=1)
        assert decision.action == LoopAction.CONTINUE
        assert decision.max_iterations_reached is False

    def test_continues_at_iteration_one(self) -> None:
        guard = LoopGuard(max_iterations=5)
        decision = guard.evaluate(current_iteration=1)
        assert decision.action == LoopAction.CONTINUE

    def test_continues_with_errors_below_threshold(self) -> None:
        guard = LoopGuard(max_iterations=10)
        guard.record_error("first error")
        guard.record_error("second error")
        decision = guard.evaluate(current_iteration=3)
        assert decision.action == LoopAction.CONTINUE


class TestLoopGuardStop:
    def test_stops_when_max_iterations_reached(self) -> None:
        guard = LoopGuard(max_iterations=5)
        decision = guard.evaluate(current_iteration=5)
        assert decision.action == LoopAction.STOP
        assert decision.max_iterations_reached is True

    def test_stops_when_max_iterations_exceeded(self) -> None:
        guard = LoopGuard(max_iterations=3)
        decision = guard.evaluate(current_iteration=10)
        assert decision.action == LoopAction.STOP

    def test_stops_on_repeated_critic_rejection(self) -> None:
        guard = LoopGuard(max_iterations=10)
        guard.record_critic_rejection()
        guard.record_critic_rejection()
        guard.record_critic_rejection()
        decision = guard.evaluate(current_iteration=5)
        assert decision.action == LoopAction.STOP
        assert "Critic rejected" in decision.reason


class TestLoopGuardEscalate:
    def test_escalates_on_repeated_identical_errors(self) -> None:
        guard = LoopGuard(max_iterations=10)
        guard.record_error("Connection refused")
        guard.record_error("Connection refused")
        guard.record_error("Connection refused")
        guard.record_error("Connection refused")
        decision = guard.evaluate(current_iteration=5)
        # 4 consecutive identical errors >= threshold of 3
        assert decision.action == LoopAction.ESCALATE

    def test_continues_with_different_errors(self) -> None:
        guard = LoopGuard(max_iterations=10)
        guard.record_error("Error A")
        guard.record_error("Error B")
        guard.record_error("Error A")  # not consecutive
        decision = guard.evaluate(current_iteration=5)
        assert decision.action == LoopAction.CONTINUE


class TestLoopGuardDebug:
    def test_debugs_on_repeated_verification_failures(self) -> None:
        guard = LoopGuard(max_iterations=10)
        for i in range(6):
            guard.record_verification_failure(f"Failure #{i}")
        decision = guard.evaluate(current_iteration=5)
        assert decision.action == LoopAction.DEBUG


class TestLoopGuardNoProgress:
    def test_detects_no_progress_empty_summary(self) -> None:
        guard = LoopGuard(max_iterations=10)
        guard.record_progress_summary("")
        decision = guard.evaluate(current_iteration=2)
        assert decision.action == LoopAction.RETRY
        assert decision.no_progress_detected is True

    def test_detects_no_progress_short_summary(self) -> None:
        guard = LoopGuard(max_iterations=10)
        guard.record_progress_summary("hi")
        decision = guard.evaluate(current_iteration=2)
        assert decision.action == LoopAction.RETRY

    def test_continues_with_meaningful_summary(self) -> None:
        guard = LoopGuard(max_iterations=10)
        guard.record_progress_summary("Implemented the login flow and added tests")
        decision = guard.evaluate(current_iteration=2)
        assert decision.action == LoopAction.CONTINUE

    def test_no_progress_only_checks_last_summary(self) -> None:
        guard = LoopGuard(max_iterations=10)
        guard.record_progress_summary("Implemented the login flow")
        guard.record_progress_summary("")
        decision = guard.evaluate(current_iteration=3)
        # last summary is empty → RETRY
        assert decision.action == LoopAction.RETRY


class TestLoopGuardReset:
    def test_reset_clears_history(self) -> None:
        guard = LoopGuard(max_iterations=10)
        guard.record_error("Error")
        guard.record_verification_failure("Fail")
        guard.record_critic_rejection()
        guard.record_progress_summary("hi")
        guard.reset()
        decision = guard.evaluate(current_iteration=1)
        assert decision.action == LoopAction.CONTINUE
        assert guard._critic_rejections == 0

    def test_reset_allows_fresh_start(self) -> None:
        guard = LoopGuard(max_iterations=3)
        guard.record_critic_rejection()
        guard.record_critic_rejection()
        guard.record_critic_rejection()
        guard.reset()
        decision = guard.evaluate(current_iteration=1)
        assert decision.action == LoopAction.CONTINUE


class TestLoopGuardEdgeCases:
    def test_single_error_below_threshold(self) -> None:
        guard = LoopGuard(max_iterations=10)
        guard.record_error("Some error")
        decision = guard.evaluate(current_iteration=2)
        assert decision.action == LoopAction.CONTINUE

    def test_single_verification_failure_below_threshold(self) -> None:
        guard = LoopGuard(max_iterations=10)
        guard.record_verification_failure("Fail")
        decision = guard.evaluate(current_iteration=2)
        assert decision.action == LoopAction.CONTINUE

    def test_single_critic_rejection_below_limit(self) -> None:
        guard = LoopGuard(max_iterations=10)
        guard.record_critic_rejection()
        decision = guard.evaluate(current_iteration=2)
        assert decision.action == LoopAction.CONTINUE
