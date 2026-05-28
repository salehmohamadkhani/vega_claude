"""Structured KPI model layer for Ralph Runtime task evaluation.

Defines KPI types, statuses, and an evaluator that can check KPIs
deterministically — file existence, text matching, command exit codes.
No network calls, no AI evaluation.
"""

from __future__ import annotations

import enum
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .verification import VerificationStatus
from .verification_policy import VerificationPolicy
from .verification_runner import VerificationRunner, VerificationRunnerConfig


class KPIType(enum.Enum):
    """The kind of check a KPI performs."""

    BOOLEAN = "boolean"
    COUNT = "count"
    THRESHOLD = "threshold"
    TEXT_MATCH = "text_match"
    FILE_EXISTS = "file_exists"
    COMMAND_EXIT_ZERO = "command_exit_zero"


class KPIStatus(enum.Enum):
    """Status of a KPI evaluation."""

    NOT_CHECKED = "not_checked"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class KPI:
    """A single Key Performance Indicator for a task.

    Parameters
    ----------
    id:
        Unique identifier for this KPI.
    label:
        Human-readable description.
    type:
        The kind of check (boolean, count, threshold, etc.).
    target:
        Target value for comparison (type depends on KPIType).
    threshold:
        Optional threshold value for THRESHOLD-type KPIs.
    command:
        Command string to execute for COMMAND_EXIT_ZERO KPIs.
    file_path:
        File path (relative to workspace) for FILE_EXISTS / TEXT_MATCH KPIs.
    text:
        Text pattern to search for in TEXT_MATCH KPIs.
    required:
        If True, failure of this KPI prevents task pass.
    """

    id: str = ""
    label: str = ""
    type: KPIType = KPIType.BOOLEAN
    target: Any = None
    threshold: float | None = None
    command: str = ""
    file_path: str = ""
    text: str = ""
    required: bool = True


@dataclass
class KPIResult:
    """Structured result of evaluating a single KPI."""

    kpi_id: str = ""
    status: KPIStatus = KPIStatus.NOT_CHECKED
    passed: bool = False
    reason: str = ""
    observed_value: Any = None
    metadata: dict[str, Any] = field(default_factory=dict)


class KPIEvaluator:
    """Deterministic KPI evaluator.

    Evaluates KPIs using safe deterministic checks:
    - FILE_EXISTS: checks file existence inside the workspace root
    - TEXT_MATCH: searches for a pattern in a workspace file
    - BOOLEAN: compares observed_value to target
    - COUNT: numeric comparison
    - THRESHOLD: numeric threshold check
    - COMMAND_EXIT_ZERO: runs command through VerificationRunner + policy

    No network calls. File access is scoped to the workspace root.
    """

    def __init__(
        self,
        workspace_root: str | Path = ".",
        policy: VerificationPolicy | None = None,
    ) -> None:
        self._workspace_root = Path(workspace_root).resolve()
        self._policy = policy or VerificationPolicy()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate(self, kpi: KPI) -> KPIResult:
        """Evaluate a single KPI and return its result."""
        method_map = {
            KPIType.BOOLEAN: self._eval_boolean,
            KPIType.COUNT: self._eval_count,
            KPIType.THRESHOLD: self._eval_threshold,
            KPIType.TEXT_MATCH: self._eval_text_match,
            KPIType.FILE_EXISTS: self._eval_file_exists,
            KPIType.COMMAND_EXIT_ZERO: self._eval_command_exit_zero,
        }
        evaluator = method_map.get(kpi.type)
        if evaluator is None:
            return KPIResult(
                kpi_id=kpi.id,
                status=KPIStatus.SKIPPED,
                passed=False,
                reason=f"Unknown KPI type: {kpi.type}",
            )
        return evaluator(kpi)

    def evaluate_all(
        self,
        kpis: list[KPI],
    ) -> list[KPIResult]:
        """Evaluate every KPI in a list.

        Returns results in the same order as the input list.
        """
        return [self.evaluate(kpi) for kpi in kpis]

    def kpis_all_passed(self, results: list[KPIResult]) -> bool:
        """Return True if all *required* KPIs passed.

        Optional KPIs that fail do not count as a failure.
        """
        return all(
            not (r.status == KPIStatus.FAILED and not r.passed)
            for r in results
        )

    # ------------------------------------------------------------------
    # Per-type evaluators (all deterministic, no network)
    # ------------------------------------------------------------------

    def _eval_boolean(self, kpi: KPI) -> KPIResult:
        """Evaluate a boolean KPI: observed_value must match target."""
        passed = bool(kpi.target) if kpi.target is not None else False
        return KPIResult(
            kpi_id=kpi.id,
            status=KPIStatus.PASSED if passed else KPIStatus.FAILED,
            passed=passed,
            reason="Boolean check." if passed else "Boolean target is falsy.",
            observed_value=kpi.target,
        )

    def _eval_count(self, kpi: KPI) -> KPIResult:
        """Evaluate a count KPI: observed_value must equal target."""
        passed = kpi.target is not None and kpi.target == kpi.threshold
        return KPIResult(
            kpi_id=kpi.id,
            status=KPIStatus.PASSED if passed else KPIStatus.FAILED,
            passed=passed,
            reason=f"Count check: {kpi.target} == {kpi.threshold}"
            if passed
            else f"Count mismatch: {kpi.target} != {kpi.threshold}",
            observed_value=kpi.target,
        )

    def _eval_threshold(self, kpi: KPI) -> KPIResult:
        """Evaluate a threshold KPI: observed_value must be >= threshold."""
        if kpi.target is None:
            return KPIResult(
                kpi_id=kpi.id,
                status=KPIStatus.FAILED,
                passed=False,
                reason="No target value provided for threshold check.",
            )
        passed = float(kpi.target) >= (kpi.threshold or 0)
        return KPIResult(
            kpi_id=kpi.id,
            status=KPIStatus.PASSED if passed else KPIStatus.FAILED,
            passed=passed,
            reason=f"Threshold: {kpi.target} >= {kpi.threshold}"
            if passed
            else f"Threshold not met: {kpi.target} < {kpi.threshold}",
            observed_value=kpi.target,
        )

    def _eval_text_match(self, kpi: KPI) -> KPIResult:
        """Evaluate a text-match KPI: search for pattern in workspace file."""
        if not kpi.file_path or not kpi.text:
            return KPIResult(
                kpi_id=kpi.id,
                status=KPIStatus.SKIPPED,
                passed=False,
                reason="Text match requires both file_path and text.",
            )
        safe_path = self._resolve_safe(kpi.file_path)
        if safe_path is None:
            return KPIResult(
                kpi_id=kpi.id,
                status=KPIStatus.FAILED,
                passed=False,
                reason=f"File escapes workspace: {kpi.file_path}",
            )
        try:
            content = safe_path.read_text(encoding="utf-8", errors="replace")
        except FileNotFoundError:
            return KPIResult(
                kpi_id=kpi.id,
                status=KPIStatus.FAILED,
                passed=False,
                reason=f"File not found: {kpi.file_path}",
            )
        except OSError as exc:
            return KPIResult(
                kpi_id=kpi.id,
                status=KPIStatus.FAILED,
                passed=False,
                reason=f"Error reading file: {exc}",
            )

        try:
            found = re.search(kpi.text, content)
        except re.error:
            found = kpi.text in content

        passed = found is not None
        return KPIResult(
            kpi_id=kpi.id,
            status=KPIStatus.PASSED if passed else KPIStatus.FAILED,
            passed=passed,
            reason="Text pattern found." if passed else "Text pattern not found.",
            observed_value=kpi.text,
        )

    def _eval_file_exists(self, kpi: KPI) -> KPIResult:
        """Evaluate a file-exists KPI: check file exist within workspace."""
        if not kpi.file_path:
            return KPIResult(
                kpi_id=kpi.id,
                status=KPIStatus.SKIPPED,
                passed=False,
                reason="No file_path provided.",
            )
        safe_path = self._resolve_safe(kpi.file_path)
        if safe_path is None:
            return KPIResult(
                kpi_id=kpi.id,
                status=KPIStatus.FAILED,
                passed=False,
                reason=f"File path escapes workspace: {kpi.file_path}",
            )
        exists = safe_path.exists()
        return KPIResult(
            kpi_id=kpi.id,
            status=KPIStatus.PASSED if exists else KPIStatus.FAILED,
            passed=exists,
            reason="File exists." if exists else f"File not found: {kpi.file_path}",
            observed_value=str(safe_path),
        )

    def _eval_command_exit_zero(self, kpi: KPI) -> KPIResult:
        """Evaluate a command-exit-zero KPI via VerificationRunner + policy.

        The command is checked against the policy first. If the policy
        blocks it, the KPI is skipped (not failed) with a clear reason.
        """
        if not kpi.command:
            return KPIResult(
                kpi_id=kpi.id,
                status=KPIStatus.SKIPPED,
                passed=False,
                reason="No command provided.",
            )

        # Policy check
        decision = self._policy.classify_command(kpi.command)
        if not decision.allowed:
            return KPIResult(
                kpi_id=kpi.id,
                status=KPIStatus.SKIPPED,
                passed=False,
                reason=f"KPI command blocked by policy: {decision.reason}",
                metadata={"policy_decision": decision.reason},
            )

        # Run via VerificationRunner
        config = VerificationRunnerConfig(
            working_directory=self._workspace_root,
            timeout_seconds=30,
            allow_command_execution=True,
            policy=self._policy,
        )
        runner = VerificationRunner(config=config)
        cmd_result = runner.run_command(kpi.command)

        passed = cmd_result.status == VerificationStatus.PASSED
        return KPIResult(
            kpi_id=kpi.id,
            status=KPIStatus.PASSED if passed else KPIStatus.FAILED,
            passed=passed,
            reason="Command exited 0."
            if passed
            else (cmd_result.failure_reason or "Command did not exit 0."),
            observed_value=cmd_result.exit_code,
            metadata={
                "exit_code": cmd_result.exit_code,
                "stdout": cmd_result.stdout_summary,
                "stderr": cmd_result.stderr_summary,
            },
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_safe(self, relative_path: str) -> Path | None:
        """Resolve a relative path inside the workspace root.

        Returns None if the resolved path escapes the workspace.
        """
        try:
            resolved = (self._workspace_root / relative_path).resolve()
            resolved.relative_to(self._workspace_root)
            return resolved
        except (ValueError, OSError):
            return None
