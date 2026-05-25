"""Verification planning models for Ralph Runtime.

Phase 1 models verification plans and results only — no commands
are executed.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field

from .models import RalphTask


class VerificationStatus(enum.Enum):
    """Status of a verification check."""

    NOT_RUN = "not_run"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class VerificationPlan:
    """A structured plan for verifying a task's output.

    The plan is built from the task's verification_commands, smoke_targets,
    and kpis. Phase 1 does not execute the plan — it only represents it.
    """

    commands: list[str] = field(default_factory=list)
    smoke_targets: list[str] = field(default_factory=list)
    kpi_descriptions: list[str] = field(default_factory=list)
    requires_live_provider: bool = False
    requires_browser: bool = False
    timeout_seconds: int = 120

    def is_empty(self) -> bool:
        """Return True if the plan has no verification steps at all."""
        return (
            not self.commands
            and not self.smoke_targets
            and not self.kpi_descriptions
        )


@dataclass
class VerificationResult:
    """The (deterministic) outcome of executing a VerificationPlan.

    Phase 1 populates this from plan data without actually running commands.
    """

    status: VerificationStatus = VerificationStatus.NOT_RUN
    command_results: dict[str, bool] = field(default_factory=dict)
    smoke_results: dict[str, bool] = field(default_factory=dict)
    kpi_results: dict[str, bool] = field(default_factory=dict)
    stdout_summary: str = ""
    stderr_summary: str = ""
    failure_reason: str = ""

    def all_passed(self) -> bool:
        """Return True if every recorded result passed."""
        all_cmd = all(self.command_results.values()) if self.command_results else True
        all_smoke = all(self.smoke_results.values()) if self.smoke_results else True
        all_kpi = all(self.kpi_results.values()) if self.kpi_results else True
        return all_cmd and all_smoke and all_kpi

    def summary_line(self) -> str:
        """Return a single-line summary of the result."""
        parts = []
        total_cmd = len(self.command_results)
        passed_cmd = sum(1 for v in self.command_results.values() if v)
        if total_cmd:
            parts.append(f"commands: {passed_cmd}/{total_cmd}")
        total_smoke = len(self.smoke_results)
        passed_smoke = sum(1 for v in self.smoke_results.values() if v)
        if total_smoke:
            parts.append(f"smoke: {passed_smoke}/{total_smoke}")
        total_kpi = len(self.kpi_results)
        passed_kpi = sum(1 for v in self.kpi_results.values() if v)
        if total_kpi:
            parts.append(f"kpis: {passed_kpi}/{total_kpi}")
        status = "PASS" if self.all_passed() else "FAIL"
        return f"[{status}] {' | '.join(parts)}" if parts else f"[{self.status.value.upper()}]"


# ---- Plan builder ----


def build_verification_plan_for_task(task: RalphTask) -> VerificationPlan:
    """Convert a task's verification metadata into a structured plan.

    Phase 1: no commands are executed. This simply models the plan
    for inspection and future execution.

    Parameters
    ----------
    task:
        A RalphTask with verification_commands, smoke_targets, and kpis.

    Returns
    -------
    VerificationPlan populated from the task fields.
    """
    requires_live = bool(task.smoke_targets)
    requires_browser = any(
        "browser" in target.lower() or "playwright" in target.lower()
        for target in task.smoke_targets
    )

    return VerificationPlan(
        commands=list(task.verification_commands),
        smoke_targets=list(task.smoke_targets),
        kpi_descriptions=list(task.kpis),
        requires_live_provider=requires_live,
        requires_browser=requires_browser,
        timeout_seconds=120,
    )
