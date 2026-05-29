"""Execution models for Ralph Runtime task execution.

Defines the contract for task execution — what it means to run a task,
what a result looks like, and how execution is configured.

All execution is dry-run by default. Real execution requires explicit
opt-in via ``ExecutionConfig(allow_real_execution=True)``.
"""

from __future__ import annotations

import enum
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


class ExecutionConfigError(Exception):
    """Raised when ExecutionConfig is invalid for the requested operation."""


class ExecutionMode(enum.Enum):
    """Whether execution is real or simulated."""

    DRY_RUN = "dry_run"
    REAL = "real"


class ExecutionStatus(enum.Enum):
    """Outcome status of a single execution."""

    NOT_STARTED = "not_started"
    SKIPPED = "skipped"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"


@dataclass
class ExecutionRequest:
    """Everything needed to execute a task via Claude Code."""

    run_id: str = ""
    task_id: str = ""
    task_title: str = ""
    prompt: str = ""
    workspace_path: str = ""
    mode: ExecutionMode = ExecutionMode.DRY_RUN
    timeout_seconds: int = 300
    allowed_files: list[str] = field(default_factory=list)
    forbidden_files: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionResult:
    """Structured result of a single task execution."""

    run_id: str = ""
    task_id: str = ""
    status: ExecutionStatus = ExecutionStatus.NOT_STARTED
    mode: ExecutionMode = ExecutionMode.DRY_RUN
    command: str = ""
    started_at: str = ""
    finished_at: str = ""
    duration_seconds: float = 0.0
    stdout_summary: str = ""
    stderr_summary: str = ""
    output_summary: str = ""
    changed_files: list[str] = field(default_factory=list)
    exit_code: int = -1
    timed_out: bool = False
    failure_reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable dict."""
        return {
            "run_id": self.run_id,
            "task_id": self.task_id,
            "status": self.status.value,
            "mode": self.mode.value,
            "command": self.command,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_seconds": self.duration_seconds,
            "stdout_summary": self.stdout_summary,
            "stderr_summary": self.stderr_summary,
            "output_summary": self.output_summary,
            "changed_files": list(self.changed_files),
            "exit_code": self.exit_code,
            "timed_out": self.timed_out,
            "failure_reason": self.failure_reason,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def skipped(cls, reason: str = "Dry-run mode") -> ExecutionResult:
        """Return a result indicating execution was skipped."""
        return cls(
            status=ExecutionStatus.SKIPPED,
            mode=ExecutionMode.DRY_RUN,
            failure_reason=reason,
            finished_at=_now_iso(),
        )


@dataclass
class ExecutionConfig:
    """Configuration for task execution.

    Safe defaults: dry-run only, real execution disabled.
    """

    workspace_path: str = ""
    timeout_seconds: int = 300
    max_output_chars: int = 50000
    allow_real_execution: bool = False
    command_allowlist: list[str] = field(
        default_factory=lambda: ["fcc-claude", "fcc-claude.exe", "claude", "claude.exe"]
    )
    dry_run: bool = True
    allow_test_fallback: bool = False
    require_clean_git: bool = True
    allow_dirty_git: bool = False
    allow_repo_root_execution: bool = False
    enforce_allowed_files: bool = True
    # Environment variables to set in the child process (overrides current env).
    # When empty (default), inherits the current process environment.
    child_env: dict[str, str] = field(default_factory=dict)

    def validate_for_execution(self) -> None:
        """Validate config for real execution.

        Raises ``ExecutionConfigError`` if the config is unsafe.
        """
        if self.allow_real_execution and self.allow_test_fallback:
            raise ExecutionConfigError(
                "allow_test_fallback=True is not allowed with "
                "allow_real_execution=True. The echo/testing fallback "
                "would silently substitute for a real Claude Code CLI."
            )

    def validate_for_guard_only(self) -> None:
        """Validate workspace-safety guard fields only.

        Skips execution-mode validation (dry-run vs real) and only checks
        guard config consistency. Called before real execution to ensure
        the guard is properly configured.
        """

    def validate_for_test_fallback(self) -> None:
        """Validate config for test-fallback execution.

        Warns if ``allow_test_fallback`` is True without real execution:
        that's fine for testing, but the test fallback must not be used
        in production with real execution enabled.
        """
        if self.allow_real_execution and self.allow_test_fallback:
            raise ExecutionConfigError(
                "allow_test_fallback=True with allow_real_execution=True "
                "is unsafe. The echo/testing fallback should never be "
                "used for real execution."
            )


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()
