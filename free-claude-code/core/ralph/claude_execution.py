"""Claude Code execution adapter for Ralph Runtime.

Builds commands and executes Claude Code as a subprocess through
FCC's ``fcc-claude`` CLI or the raw ``claude`` CLI.

Real execution is opt-in and disabled by default. Never uses
``shell=True``. Never calls provider APIs directly.
"""

from __future__ import annotations

import re
import shlex
import shutil
import subprocess
import time
from datetime import UTC, datetime

from .execution import (
    ExecutionConfig,
    ExecutionConfigError,
    ExecutionMode,
    ExecutionRequest,
    ExecutionResult,
    ExecutionStatus,
)


class CommandBuilderError(Exception):
    """Raised when a command cannot be built."""


class ExecutionAdapterError(Exception):
    """Raised when execution fails before the subprocess starts."""


class ClaudeCodeCommandBuilder:
    """Builds a Claude Code CLI command from an ExecutionRequest.

    Discovers the available CLI (fcc-claude > claude > echo fallback)
    and constructs the argv list.
    """

    @staticmethod
    def build_command(
        request: ExecutionRequest,
        allow_fallback: bool = False,
    ) -> list[str]:
        """Build the argv list for running Claude Code.

        Resolution order:
        1. ``fcc-claude`` (FCC's Claude Code launcher)
        2. ``claude`` (raw Claude Code CLI)
        3. ``echo`` (testing fallback — only when ``allow_fallback=True``)

        Raises ``CommandBuilderError`` if no CLI is found and
        fallback is not allowed.
        """
        fcc_claude = shutil.which("fcc-claude")
        if fcc_claude is not None:
            return [fcc_claude, "--print", request.prompt]

        claude = shutil.which("claude")
        if claude is not None:
            return [claude, "--print", request.prompt]

        if allow_fallback:
            return ["echo", "claude", "--print", request.prompt]

        raise CommandBuilderError(
            "No Claude Code CLI found (tried fcc-claude, claude). "
            "Install Claude Code or set allow_fallback=True for testing."
        )


class ClaudeCodeExecutionAdapter:
    """Adapter that executes tasks via Claude Code CLI.

    Default configuration is dry-run only — no real execution occurs
    unless ``allow_real_execution=True`` and mode is ``REAL``.
    """

    def __init__(self, config: ExecutionConfig | None = None) -> None:
        self._config = config or ExecutionConfig()

    @property
    def config(self) -> ExecutionConfig:
        return self._config

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        """Execute a task request.

        Returns an ``ExecutionResult``. In dry-run mode or when real
        execution is disabled, returns a SKIPPED result immediately
        without running any subprocess.
        """
        # Safety check: dry-run or real execution disabled
        if request.mode == ExecutionMode.DRY_RUN:
            return ExecutionResult.skipped("Dry-run mode — no execution.")

        if not self._config.allow_real_execution:
            return ExecutionResult(
                status=ExecutionStatus.SKIPPED,
                mode=request.mode,
                failure_reason=(
                    "Real execution disabled. Set allow_real_execution=True to enable."
                ),
            )

        # Validate config for real execution
        try:
            self._config.validate_for_execution()
        except ExecutionConfigError as exc:
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                mode=request.mode,
                failure_reason=str(exc),
            )

        # Build command
        try:
            command = ClaudeCodeCommandBuilder.build_command(
                request,
                allow_fallback=self._config.allow_test_fallback,
            )
        except CommandBuilderError as exc:
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                mode=request.mode,
                failure_reason=str(exc),
            )

        command_str = shlex.join(command)

        # Validate command against allowlist
        if not self._is_command_allowed(command):
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                mode=request.mode,
                failure_reason=(
                    f"Command not in allowlist: {command[0]}. "
                    f"Allowed: {self._config.command_allowlist}"
                ),
            )

        # Execute
        started_at = _now_iso()
        start_time = time.monotonic()

        try:
            proc = subprocess.run(
                command,
                capture_output=True,
                text=True,
                shell=False,
                cwd=request.workspace_path or None,
                timeout=request.timeout_seconds or self._config.timeout_seconds,
            )
            duration = time.monotonic() - start_time
            exit_code = proc.returncode
            stdout = proc.stdout or ""
            stderr = proc.stderr or ""
            timed_out = False

        except subprocess.TimeoutExpired:
            duration = time.monotonic() - start_time
            exit_code = -1
            stdout = ""
            stderr = "Process timed out."
            timed_out = True

        except FileNotFoundError as exc:
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                mode=request.mode,
                command=command_str,
                failure_reason=f"Executable not found: {exc}",
                started_at=started_at,
                finished_at=_now_iso(),
            )

        # Truncate output
        max_chars = self._config.max_output_chars
        stdout_summary = stdout[:max_chars]
        stderr_summary = stderr[:max_chars]

        # Parse changed files from output
        changed_files = _parse_changed_files(stdout)

        # Determine status
        if timed_out:
            status = ExecutionStatus.TIMED_OUT
        elif exit_code == 0:
            status = ExecutionStatus.SUCCEEDED
        else:
            status = ExecutionStatus.FAILED

        return ExecutionResult(
            run_id=request.run_id,
            task_id=request.task_id,
            status=status,
            mode=request.mode,
            command=command_str,
            started_at=started_at,
            finished_at=_now_iso(),
            duration_seconds=round(duration, 2),
            stdout_summary=stdout_summary,
            stderr_summary=stderr_summary,
            output_summary=_build_output_summary(stdout, stderr),
            changed_files=changed_files,
            exit_code=exit_code,
            timed_out=timed_out,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _is_command_allowed(self, command: list[str]) -> bool:
        """Check if the command's executable is in the allowlist.

        Extracts the basename from the first element of the argv list,
        handling both Unix and Windows paths. Avoids shell-style parsing
        (``shlex.split``) which mishandles backslashes in Windows paths.
        """
        if not command:
            return False
        executable = command[0]
        exec_name = executable.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
        return any(exec_name == allowed for allowed in self._config.command_allowlist)


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _parse_changed_files(output: str) -> list[str]:
    """Parse a list of changed file paths from Claude Code output.

    Looks for lines matching ``Changed: path/to/file`` in the output.
    """
    files: list[str] = []
    for line in output.split("\n"):
        line = line.strip()
        match = re.match(r"^Changed:\s+(.+)$", line)
        if match:
            file_path = match.group(1).strip()
            if file_path not in files:
                files.append(file_path)
    return files


def _build_output_summary(stdout: str, stderr: str) -> str:
    """Build a concise output summary from stdout and stderr."""
    parts: list[str] = []
    stdout_lines = [line for line in stdout.split("\n") if line.strip()]
    if stdout_lines:
        parts.append(f"stdout: {len(stdout_lines)} lines")
    if stderr.strip():
        stderr_lines = len([line for line in stderr.split("\n") if line.strip()])
        parts.append(f"stderr: {stderr_lines} lines")
    return " | ".join(parts) if parts else "no output"


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()
