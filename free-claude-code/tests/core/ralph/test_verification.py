"""Tests for core.ralph.verification."""

from __future__ import annotations

from core.ralph.models import RalphTask
from core.ralph.verification import (
    VerificationPlan,
    VerificationResult,
    VerificationStatus,
    build_verification_plan_for_task,
)


class TestVerificationPlan:
    def test_empty_plan(self) -> None:
        plan = VerificationPlan()
        assert plan.is_empty() is True

    def test_plan_with_commands(self) -> None:
        plan = VerificationPlan(commands=["pytest", "ruff check"])
        assert plan.is_empty() is False
        assert len(plan.commands) == 2

    def test_plan_with_smoke_targets(self) -> None:
        plan = VerificationPlan(smoke_targets=["smoke/test_auth"])
        assert plan.is_empty() is False
        assert "smoke/test_auth" in plan.smoke_targets

    def test_plan_with_kpis(self) -> None:
        plan = VerificationPlan(kpi_descriptions=["100% coverage"])
        assert plan.is_empty() is False


class TestBuildVerificationPlan:
    def test_build_plan_from_task_commands(self) -> None:
        task = RalphTask(
            title="Test task",
            verification_commands=["pytest tests/unit", "ruff check"],
        )
        plan = build_verification_plan_for_task(task)
        assert len(plan.commands) == 2
        assert "pytest tests/unit" in plan.commands

    def test_build_plan_from_smoke_targets(self) -> None:
        task = RalphTask(
            title="Smoke task",
            smoke_targets=["smoke/test_api"],
        )
        plan = build_verification_plan_for_task(task)
        assert len(plan.smoke_targets) == 1
        assert plan.requires_live_provider is True

    def test_build_plan_from_kpis(self) -> None:
        task = RalphTask(
            title="KPI task",
            kpis=["p95 latency < 200ms", "zero regressions"],
        )
        plan = build_verification_plan_for_task(task)
        assert len(plan.kpi_descriptions) == 2

    def test_build_plan_all_fields(self) -> None:
        task = RalphTask(
            title="Full",
            verification_commands=["pytest"],
            smoke_targets=["smoke/auth", "browser/login"],
            kpis=["coverage >= 80%"],
        )
        plan = build_verification_plan_for_task(task)
        assert len(plan.commands) == 1
        assert len(plan.smoke_targets) == 2
        assert len(plan.kpi_descriptions) == 1
        assert plan.requires_live_provider is True
        assert plan.requires_browser is True  # "browser" keyword in smoke target

    def test_build_plan_empty_task(self) -> None:
        task = RalphTask(title="Empty")
        plan = build_verification_plan_for_task(task)
        assert plan.is_empty() is True
        assert plan.requires_live_provider is False


class TestVerificationResult:
    def test_default_status_not_run(self) -> None:
        result = VerificationResult()
        assert result.status == VerificationStatus.NOT_RUN

    def test_all_passed_true(self) -> None:
        result = VerificationResult(
            status=VerificationStatus.PASSED,
            command_results={"pytest": True, "ruff": True},
            smoke_results={"smoke/auth": True},
            kpi_results={"coverage": True},
        )
        assert result.all_passed() is True

    def test_all_passed_false_when_command_fails(self) -> None:
        result = VerificationResult(
            status=VerificationStatus.FAILED,
            command_results={"pytest": False},
        )
        assert result.all_passed() is False

    def test_all_passed_with_empty_results(self) -> None:
        """No results means no failures — vacuously true."""
        result = VerificationResult()
        assert result.all_passed() is True

    def test_skipped_status(self) -> None:
        result = VerificationResult(status=VerificationStatus.SKIPPED)
        assert result.status == VerificationStatus.SKIPPED

    def test_summary_line_pass(self) -> None:
        result = VerificationResult(
            status=VerificationStatus.PASSED,
            command_results={"pytest": True, "ruff": True},
            smoke_results={"smoke/auth": True},
        )
        summary = result.summary_line()
        assert "[PASS]" in summary
        assert "commands: 2/2" in summary
        assert "smoke: 1/1" in summary

    def test_summary_line_fail(self) -> None:
        result = VerificationResult(
            status=VerificationStatus.FAILED,
            command_results={"pytest": False},
        )
        summary = result.summary_line()
        assert "[FAIL]" in summary
        assert "commands: 0/1" in summary

    def test_summary_line_empty(self) -> None:
        result = VerificationResult()
        summary = result.summary_line()
        assert "[NOT_RUN]" in summary

    def test_failure_reason(self) -> None:
        result = VerificationResult(
            status=VerificationStatus.FAILED,
            failure_reason="Timeout waiting for service",
        )
        assert result.failure_reason == "Timeout waiting for service"
