"""Safe command runner for verification plans.

Phase 3 adds safe, bounded command execution on top of Phase 1's verification
planning. Command execution is DISABLED by default — configure explicitly.
"""

from __future__ import annotations

import shlex
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

from .verification import VerificationPlan, VerificationResult, VerificationStatus
from .verification_policy import (
    VerificationPolicy,
    VerificationPolicyDecision,
)


@dataclass
class CommandExecutionResult:
    """Structured result of executing a single verification command."""

    command: list[str] = field(default_factory=list)
    status: VerificationStatus = VerificationStatus.NOT_RUN
    exit_code: int | None = None
    duration_seconds: float = 0.0
    stdout_summary: str = ""
    stderr_summary: str = ""
    timed_out: bool = False
    skipped: bool = False
    failure_reason: str | None = None
    policy_decision: VerificationPolicyDecision | None = None


@dataclass
class VerificationRunnerConfig:
    """Configuration for the verification runner with safe defaults.

    Command execution is DISABLED by default (allow_command_execution=False).
    You must explicitly enable it and configure allowed prefixes.
    """

    working_directory: str | Path = "."
    timeout_seconds: int = 60
    max_output_chars: int = 2000
    allow_command_execution: bool = False
    allowed_command_prefixes: list[list[str]] = field(default_factory=list)
    policy: VerificationPolicy | None = None


# Default safe config — execution disabled, no allowed commands.
_DEFAULT_SAFE_CONFIG = VerificationRunnerConfig()


class VerificationRunner:
    """Run verification plans safely.

    Usage::

        runner = VerificationRunner(config)
        result = runner.run_plan(plan)
    """

    def __init__(self, config: VerificationRunnerConfig | None = None) -> None:
        self._config = config or _DEFAULT_SAFE_CONFIG

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run_plan(self, plan: VerificationPlan) -> VerificationResult:
        """Execute every command in a verification plan.

        Returns a ``VerificationResult`` with per-command outcomes.
        Smoke and KPI checks are modeled as metadata — execution is
        limited to shell commands.
        """
        if not self._config.allow_command_execution:
            return self._skipped_result(plan, "Command execution is disabled.")

        command_results: dict[str, bool] = {}
        all_passed = True

        for cmd_str in plan.commands:
            cmd_result = self.run_command(cmd_str)
            passed = cmd_result.status == VerificationStatus.PASSED
            command_results[cmd_str] = passed
            if not passed:
                all_passed = False

        if plan.is_empty():
            return VerificationResult(
                status=VerificationStatus.SKIPPED,
                command_results={},
                stdout_summary="Verification plan is empty — nothing to run.",
            )

        overall_status = (
            VerificationStatus.PASSED if all_passed else VerificationStatus.FAILED
        )
        stdout_lines = [
            f"{'PASS' if ok else 'FAIL'}: {cmd}" for cmd, ok in command_results.items()
        ]

        return VerificationResult(
            status=overall_status,
            command_results=command_results,
            smoke_results={},
            kpi_results={},
            stdout_summary="\n".join(stdout_lines),
            failure_reason="" if all_passed else "One or more commands failed.",
        )

    def run_command(self, command: str) -> CommandExecutionResult:
        """Execute a single command string safely.

        Safety checks before execution:
        1. ``allow_command_execution`` must be True → skipped otherwise
        2. If a ``VerificationPolicy`` is configured, classify the command.
           Blocked commands are skipped; REVIEW commands are skipped.
        3. Command prefix must match ``allowed_command_prefixes`` → skipped otherwise
        4. ``shell=False`` enforcement via ``shlex.split``
        """
        if not self._config.allow_command_execution:
            return CommandExecutionResult(
                command=[command],
                status=VerificationStatus.SKIPPED,
                skipped=True,
                failure_reason="Command execution is disabled.",
            )

        try:
            argv = shlex.split(command)
        except ValueError as exc:
            return CommandExecutionResult(
                command=[command],
                status=VerificationStatus.FAILED,
                failure_reason=f"Failed to parse command: {exc}",
            )

        if not argv:
            return CommandExecutionResult(
                command=[],
                status=VerificationStatus.FAILED,
                failure_reason="Empty command.",
            )

        # Policy check (takes precedence over prefix-based check)
        if self._config.policy is not None:
            decision = self._config.policy.classify_command(command)
            if not decision.allowed:
                return CommandExecutionResult(
                    command=argv,
                    status=VerificationStatus.SKIPPED,
                    skipped=True,
                    failure_reason=decision.reason,
                    policy_decision=decision,
                )
        else:
            decision = None

        if not self._is_allowed(argv) and self._config.policy is None:
            return CommandExecutionResult(
                command=argv,
                status=VerificationStatus.SKIPPED,
                skipped=True,
                failure_reason=(f"Command prefix not in allowed list: {argv[:2]}"),
            )
        # If policy is present and command passed policy check, skip
        # the prefix whitelist gate. The policy is the authoritative
        # safety check; the prefix list is a simple allowlist for
        # deployments that don't use a full policy.

        # Safe execution
        result = self._execute(argv)
        result.policy_decision = decision
        return result

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def _execute(self, argv: list[str]) -> CommandExecutionResult:
        """Run a parsed command with timeout and output capture."""
        cwd = str(self._config.working_directory)
        start = time.monotonic()
        timed_out = False
        exit_code: int | None = None
        stdout = ""
        stderr = ""
        failure_reason: str | None = None

        # Clamp timeout by policy max if available
        timeout = self._config.timeout_seconds
        if self._config.policy is not None:
            timeout = min(timeout, self._config.policy.max_timeout_seconds)

        try:
            proc = subprocess.run(
                argv,
                capture_output=True,
                text=True,
                shell=False,
                cwd=cwd,
                timeout=timeout,
            )
            exit_code = proc.returncode
            stdout = proc.stdout or ""
            stderr = proc.stderr or ""
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            stdout = exc.stdout or ""
            stderr = exc.stderr or ""
            failure_reason = f"Command timed out after {timeout}s"
        except FileNotFoundError:
            failure_reason = f"Command not found: {argv[0]}"
        except PermissionError:
            failure_reason = f"Permission denied: {argv[0]}"
        except OSError as exc:
            failure_reason = f"OS error: {exc}"

        duration = time.monotonic() - start

        # Determine status
        if (failure_reason and not timed_out) or timed_out:
            status = VerificationStatus.FAILED
        elif exit_code == 0:
            status = VerificationStatus.PASSED
        else:
            status = VerificationStatus.FAILED

        # Ensure str (subprocess types may include bytes in some stubs)
        stdout = stdout if isinstance(stdout, str) else str(stdout)
        stderr = stderr if isinstance(stderr, str) else str(stderr)

        # Truncate
        stdout = self._truncate(stdout)
        stderr = self._truncate(stderr)

        return CommandExecutionResult(
            command=argv,
            status=status,
            exit_code=exit_code,
            duration_seconds=round(duration, 2),
            stdout_summary=stdout,
            stderr_summary=stderr,
            timed_out=timed_out,
            skipped=False,
            failure_reason=failure_reason,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _is_allowed(self, argv: list[str]) -> bool:
        """Check if the command argv matches any allowed prefix."""
        if not self._config.allowed_command_prefixes:
            return False
        for prefix in self._config.allowed_command_prefixes:
            if len(argv) >= len(prefix) and argv[: len(prefix)] == prefix:
                return True
        return False

    def _truncate(self, text: str) -> str:
        """Truncate text to max_output_chars."""
        max_chars = self._config.max_output_chars
        if len(text) <= max_chars:
            return text
        return text[: max_chars - 3] + "..."

    def _skipped_result(
        self,
        plan: VerificationPlan,
        reason: str,
    ) -> VerificationResult:
        """Build a fully-skipped VerificationResult."""
        return VerificationResult(
            status=VerificationStatus.SKIPPED,
            command_results=dict.fromkeys(plan.commands, False),
            stdout_summary=f"Skipped: {reason}",
            failure_reason=reason,
        )
