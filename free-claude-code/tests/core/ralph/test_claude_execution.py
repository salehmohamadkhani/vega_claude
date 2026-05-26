"""Tests for Claude Code execution adapter — dry-run safety,
command building, allowlist enforcement, output handling."""

from __future__ import annotations

import os
import subprocess
import sys
from unittest.mock import patch

from core.ralph.claude_execution import (
    ClaudeCodeCommandBuilder,
    ClaudeCodeExecutionAdapter,
)
from core.ralph.execution import (
    ExecutionConfig,
    ExecutionMode,
    ExecutionRequest,
    ExecutionStatus,
)

# A command that works on any platform (Python itself).
_PYTHON_CMD = [sys.executable, "-c", "print('ok')"]
_PYTHON_EXE = os.path.basename(sys.executable)


def _make_request(**overrides: object) -> ExecutionRequest:
    params: dict = {
        "run_id": "run-1",
        "task_id": "task-1",
        "task_title": "Test",
        "prompt": "Do the thing",
        "workspace_path": "/tmp",
        "mode": ExecutionMode.DRY_RUN,
    }
    params.update(overrides)
    return ExecutionRequest(**params)


class TestClaudeCodeCommandBuilder:
    def test_returns_list_of_strings(self) -> None:
        request = _make_request()
        cmd = ClaudeCodeCommandBuilder.build_command(request)
        assert isinstance(cmd, list)
        assert all(isinstance(part, str) for part in cmd)


class TestClaudeCodeExecutionAdapter:
    def setup_method(self) -> None:
        self.adapter = ClaudeCodeExecutionAdapter()

    def test_dry_run_does_not_execute(self) -> None:
        request = _make_request(mode=ExecutionMode.DRY_RUN)
        result = self.adapter.execute(request)
        assert result.status == ExecutionStatus.SKIPPED

    def test_real_execution_disabled_blocks(self) -> None:
        config = ExecutionConfig(allow_real_execution=False)
        adapter = ClaudeCodeExecutionAdapter(config=config)
        request = _make_request(mode=ExecutionMode.REAL)
        result = adapter.execute(request)
        assert result.status == ExecutionStatus.SKIPPED
        assert "Real execution disabled" in result.failure_reason

    def test_real_execution_allowed_with_config(self) -> None:
        """Verify real execution succeeds when properly configured."""
        with patch.object(
            ClaudeCodeCommandBuilder, "build_command", return_value=_PYTHON_CMD
        ):
            config = ExecutionConfig(
                allow_real_execution=True,
                command_allowlist=[_PYTHON_EXE],
            )
            adapter = ClaudeCodeExecutionAdapter(config=config)
            request = _make_request(
                mode=ExecutionMode.REAL,
                prompt="hello",
            )
            result = adapter.execute(request)
            assert result.status == ExecutionStatus.SUCCEEDED
            assert result.exit_code == 0

    def test_execution_config_defaults(self) -> None:
        assert self.adapter.config.dry_run is True
        assert self.adapter.config.allow_real_execution is False
        assert "fcc-claude" in self.adapter.config.command_allowlist
        assert "claude" in self.adapter.config.command_allowlist

    def test_no_shell_true(self) -> None:
        """Verify subprocess is never called with shell=True."""
        original_run = subprocess.run

        def _check_shell(argv, **kwargs):
            assert kwargs.get("shell") is False, "shell=True would be unsafe!"
            return original_run(argv, **kwargs)

        with (
            patch.object(
                ClaudeCodeCommandBuilder, "build_command", return_value=_PYTHON_CMD
            ),
            patch("subprocess.run", side_effect=_check_shell),
        ):
            config = ExecutionConfig(
                allow_real_execution=True,
                command_allowlist=[_PYTHON_EXE],
            )
            adapter = ClaudeCodeExecutionAdapter(config=config)
            request = _make_request(mode=ExecutionMode.REAL, prompt="test")
            result = adapter.execute(request)
            assert result.status == ExecutionStatus.SUCCEEDED

    def test_cwd_enforced(self) -> None:
        """Verify subprocess is called with the correct cwd."""
        with (
            patch("subprocess.run") as mock_run,
            patch.object(
                ClaudeCodeCommandBuilder,
                "build_command",
                return_value=_PYTHON_CMD,
            ),
        ):
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = ""
            mock_run.return_value.stderr = ""

            config = ExecutionConfig(
                allow_real_execution=True,
                command_allowlist=[_PYTHON_EXE],
            )
            adapter = ClaudeCodeExecutionAdapter(config=config)
            request = _make_request(
                mode=ExecutionMode.REAL,
                prompt="test",
                workspace_path="/custom/workspace",
            )
            adapter.execute(request)
            _call_kwargs = mock_run.call_args.kwargs
            assert _call_kwargs.get("cwd") == "/custom/workspace"

    def test_output_truncation(self) -> None:
        """Verify long output is truncated to max_output_chars."""
        with patch.object(
            ClaudeCodeCommandBuilder, "build_command", return_value=_PYTHON_CMD
        ):
            config = ExecutionConfig(
                allow_real_execution=True,
                max_output_chars=50,
                command_allowlist=[_PYTHON_EXE],
            )
            adapter = ClaudeCodeExecutionAdapter(config=config)
            request = _make_request(mode=ExecutionMode.REAL, prompt="x" * 200)
            result = adapter.execute(request)
            assert len(result.stdout_summary) <= 50

    def test_mocked_timeout_returns_timed_out(self) -> None:
        """Verify TimeoutExpired results in TIMED_OUT status."""
        with (
            patch(
                "subprocess.run",
                side_effect=subprocess.TimeoutExpired(cmd="echo", timeout=1),
            ),
            patch.object(
                ClaudeCodeCommandBuilder,
                "build_command",
                return_value=_PYTHON_CMD,
            ),
        ):
            config = ExecutionConfig(
                allow_real_execution=True,
                command_allowlist=[_PYTHON_EXE],
            )
            adapter = ClaudeCodeExecutionAdapter(config=config)
            request = _make_request(mode=ExecutionMode.REAL, prompt="test")
            result = adapter.execute(request)
            assert result.status == ExecutionStatus.TIMED_OUT
            assert result.timed_out is True

    def test_command_allowlist_blocks_unknown(self) -> None:
        """Verify unknown commands are blocked by the allowlist."""
        with patch.object(
            ClaudeCodeCommandBuilder,
            "build_command",
            return_value=["/usr/bin/malicious", "evil"],
        ):
            config = ExecutionConfig(
                allow_real_execution=True,
                command_allowlist=["echo"],
            )
            adapter = ClaudeCodeExecutionAdapter(config=config)
            request = _make_request(mode=ExecutionMode.REAL, prompt="test")
            result = adapter.execute(request)
            assert result.status == ExecutionStatus.FAILED
            assert "allowlist" in result.failure_reason

    # ------------------------------------------------------------------
    # Command fallback hardening
    # ------------------------------------------------------------------

    def test_real_execution_fails_when_no_cli_found(self) -> None:
        """Real execution fails cleanly when no Claude CLI is found on system."""
        with patch("shutil.which", return_value=None):
            config = ExecutionConfig(
                allow_real_execution=True,
                allow_test_fallback=False,
                command_allowlist=["echo"],
            )
            adapter = ClaudeCodeExecutionAdapter(config=config)
            request = _make_request(mode=ExecutionMode.REAL, prompt="test")
            result = adapter.execute(request)
            assert result.status == ExecutionStatus.FAILED
            assert "No Claude Code CLI found" in result.failure_reason

    def test_echo_fallback_not_allowed_in_real_mode(self) -> None:
        """Echo/testing fallback must not execute real tasks."""
        with patch("shutil.which", return_value=None):
            config = ExecutionConfig(
                allow_real_execution=True,
                allow_test_fallback=False,
                command_allowlist=["echo"],
            )
            adapter = ClaudeCodeExecutionAdapter(config=config)
            request = _make_request(mode=ExecutionMode.REAL, prompt="test")
            result = adapter.execute(request)
            assert result.status == ExecutionStatus.FAILED
            assert "No Claude Code CLI found" in result.failure_reason

    def test_dry_run_does_not_call_shutil_which(self) -> None:
        """Dry-run must not call shutil.which (avoids unnecessary I/O)."""
        with patch("shutil.which") as mock_which:
            adapter = ClaudeCodeExecutionAdapter()
            request = _make_request(mode=ExecutionMode.DRY_RUN)
            result = adapter.execute(request)
            assert result.status == ExecutionStatus.SKIPPED
            mock_which.assert_not_called()

    def test_dry_run_does_not_call_subprocess(self) -> None:
        """Dry-run must never call subprocess.run."""
        with patch("subprocess.run") as mock_run:
            adapter = ClaudeCodeExecutionAdapter()
            request = _make_request(mode=ExecutionMode.DRY_RUN)
            result = adapter.execute(request)
            assert result.status == ExecutionStatus.SKIPPED
            mock_run.assert_not_called()

    def test_real_execution_disabled_does_not_call_subprocess(self) -> None:
        """When real execution disabled, never call subprocess.run."""
        with patch("subprocess.run") as mock_run:
            config = ExecutionConfig(allow_real_execution=False)
            adapter = ClaudeCodeExecutionAdapter(config=config)
            request = _make_request(mode=ExecutionMode.REAL)
            result = adapter.execute(request)
            assert result.status == ExecutionStatus.SKIPPED
            mock_run.assert_not_called()

    def test_real_with_test_fallback_rejected_by_validation(self) -> None:
        """Real execution with echo fallback is rejected by config validation."""
        config = ExecutionConfig(
            allow_real_execution=True,
            allow_test_fallback=True,
        )
        adapter = ClaudeCodeExecutionAdapter(config=config)
        request = _make_request(mode=ExecutionMode.REAL, prompt="test")
        result = adapter.execute(request)
        assert result.status == ExecutionStatus.FAILED
        assert "allow_test_fallback" in result.failure_reason

    # ------------------------------------------------------------------
    # Command allowlist hardening
    # ------------------------------------------------------------------

    def test_allowlist_allows_fcc_claude(self) -> None:
        """fcc-claude basename is allowed by default."""
        config = ExecutionConfig(command_allowlist=["fcc-claude"])
        adapter = ClaudeCodeExecutionAdapter(config=config)
        assert adapter._is_command_allowed(["fcc-claude", "--print", "prompt"])

    def test_allowlist_allows_claude(self) -> None:
        """claude basename is allowed by default."""
        config = ExecutionConfig(command_allowlist=["claude"])
        adapter = ClaudeCodeExecutionAdapter(config=config)
        assert adapter._is_command_allowed(["claude", "--print", "prompt"])

    def test_allowlist_rejects_malicious_prefix(self) -> None:
        """Prefix-matching attack: fcc-claude-malicious must not match fcc-claude."""
        config = ExecutionConfig(command_allowlist=["fcc-claude"])
        adapter = ClaudeCodeExecutionAdapter(config=config)
        assert not adapter._is_command_allowed(
            ["fcc-claude-malicious", "--print", "prompt"]
        )

    def test_allowlist_rejects_unrelated_command(self) -> None:
        """Completely unrelated command must be rejected."""
        config = ExecutionConfig(command_allowlist=["fcc-claude"])
        adapter = ClaudeCodeExecutionAdapter(config=config)
        assert not adapter._is_command_allowed(["/usr/bin/malicious", "evil"])

    def test_allowlist_handles_quoted_windows_path(self) -> None:
        """Windows path with spaces extracts basename correctly."""
        config = ExecutionConfig(command_allowlist=["fcc-claude.exe"])
        adapter = ClaudeCodeExecutionAdapter(config=config)
        assert adapter._is_command_allowed(
            ["C:\\Program Files\\fcc-claude.exe", "--print", "prompt"]
        )

    def test_allowlist_handles_windows_path(self) -> None:
        """Windows backslash path extracts basename correctly."""
        config = ExecutionConfig(command_allowlist=["fcc-claude.exe"])
        adapter = ClaudeCodeExecutionAdapter(config=config)
        assert adapter._is_command_allowed(
            ["C:\\tools\\fcc-claude.exe", "--print", "prompt"]
        )

    def test_allowlist_handles_unix_path(self) -> None:
        """Unix full path extracts basename correctly."""
        config = ExecutionConfig(command_allowlist=["fcc-claude"])
        adapter = ClaudeCodeExecutionAdapter(config=config)
        assert adapter._is_command_allowed(
            ["/usr/local/bin/fcc-claude", "--print", "prompt"]
        )

    def test_allowlist_handles_empty_list(self) -> None:
        """Empty command list must not crash the allowlist check."""
        config = ExecutionConfig(command_allowlist=["fcc-claude"])
        adapter = ClaudeCodeExecutionAdapter(config=config)
        assert not adapter._is_command_allowed([])
