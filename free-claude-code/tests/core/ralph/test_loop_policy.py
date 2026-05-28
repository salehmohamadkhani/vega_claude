"""Tests for loop policy definitions."""

from __future__ import annotations

from core.ralph.loop_policy import LoopPolicy, LoopStopReason


class TestLoopStopReason:
    """LoopStopReason enum values."""

    def test_has_required_values(self) -> None:
        values = {e.value for e in LoopStopReason}
        for expected in (
            "completed",
            "approval_required",
            "max_tasks_reached",
            "max_iterations_reached",
            "retry_required",
            "debug_required",
            "escalation_required",
            "execution_failed",
            "verification_failed",
            "quality_gate_failed",
            "cancelled",
            "error",
        ):
            assert expected in values, f"Missing LoopStopReason: {expected}"


class TestLoopPolicyDefaults:
    """LoopPolicy default values must be safe."""

    def test_dry_run_default(self) -> None:
        assert LoopPolicy().dry_run is True

    def test_real_execution_disabled_by_default(self) -> None:
        assert LoopPolicy().allow_real_execution is False

    def test_strict_task_order_default(self) -> None:
        assert LoopPolicy().strict_task_order is True

    def test_require_approval_default(self) -> None:
        assert LoopPolicy().require_approval is True

    def test_stop_on_debug_default(self) -> None:
        assert LoopPolicy().stop_on_debug is True

    def test_stop_on_escalate_default(self) -> None:
        assert LoopPolicy().stop_on_escalate is True

    def test_stop_on_retry_default(self) -> None:
        assert LoopPolicy().stop_on_retry_required is False

    def test_max_iterations_default_sane(self) -> None:
        assert LoopPolicy().max_iterations_per_task == 3

    def test_max_tasks_default_none(self) -> None:
        assert LoopPolicy().max_tasks is None

    def test_can_enable_real_execution(self) -> None:
        policy = LoopPolicy(dry_run=False, allow_real_execution=True)
        assert policy.dry_run is False
        assert policy.allow_real_execution is True

    def test_can_disable_strict_order(self) -> None:
        policy = LoopPolicy(strict_task_order=False)
        assert policy.strict_task_order is False

    def test_can_disable_stop_on_debug(self) -> None:
        policy = LoopPolicy(stop_on_debug=False)
        assert policy.stop_on_debug is False

    def test_can_disable_stop_on_escalate(self) -> None:
        policy = LoopPolicy(stop_on_escalate=False)
        assert policy.stop_on_escalate is False

    def test_custom_max_iterations(self) -> None:
        policy = LoopPolicy(max_iterations_per_task=5)
        assert policy.max_iterations_per_task == 5

    def test_custom_max_tasks(self) -> None:
        policy = LoopPolicy(max_tasks=2)
        assert policy.max_tasks == 2
