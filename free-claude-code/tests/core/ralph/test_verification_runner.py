"""Tests for core.ralph.verification_runner."""

from __future__ import annotations

from core.ralph.verification import (
    VerificationPlan,
    VerificationStatus,
)
from core.ralph.verification_runner import (
    VerificationRunner,
    VerificationRunnerConfig,
)


class TestVerificationRunnerConfig:
    def test_default_config_execution_disabled(self) -> None:
        config = VerificationRunnerConfig()
        assert config.allow_command_execution is False
        assert config.timeout_seconds == 60
        assert config.max_output_chars == 2000

    def test_custom_config(self) -> None:
        config = VerificationRunnerConfig(
            allow_command_execution=True,
            timeout_seconds=30,
            max_output_chars=100,
            allowed_command_prefixes=[["echo"]],
        )
        assert config.allow_command_execution is True
        assert config.timeout_seconds == 30


class TestVerificationRunner:
    def test_run_command_skipped_when_disabled(self) -> None:
        runner = VerificationRunner()
        result = runner.run_command("echo hello")
        assert result.skipped is True
        assert result.status == VerificationStatus.SKIPPED
        assert "disabled" in (result.failure_reason or "").lower()

    def test_run_plan_skipped_when_disabled(self) -> None:
        plan = VerificationPlan(
            commands=["echo hello", "echo world"],
        )
        runner = VerificationRunner()
        result = runner.run_plan(plan)
        assert result.status == VerificationStatus.SKIPPED
        assert "disabled" in (result.failure_reason or "").lower()
        # All commands should be marked as failed in skipped result
        assert all(v is False for v in result.command_results.values())

    def test_run_command_fails_on_malformed_input(self) -> None:
        config = VerificationRunnerConfig(allow_command_execution=True)
        runner = VerificationRunner(config)
        # Unclosed quote should fail to parse
        result = runner.run_command('echo "hello')
        assert result.status == VerificationStatus.FAILED
        assert result.failure_reason is not None

    def test_run_command_empty(self) -> None:
        config = VerificationRunnerConfig(allow_command_execution=True)
        runner = VerificationRunner(config)
        result = runner.run_command("")
        assert result.status == VerificationStatus.FAILED
        assert "empty" in (result.failure_reason or "").lower()

    def test_run_command_not_allowed_prefix(self) -> None:
        config = VerificationRunnerConfig(
            allow_command_execution=True,
            allowed_command_prefixes=[["python"]],
        )
        runner = VerificationRunner(config)
        result = runner.run_command("echo hello")
        assert result.skipped is True
        assert result.status == VerificationStatus.SKIPPED
        assert "not in allowed list" in (result.failure_reason or "")

    def test_run_command_allowed_prefix(self) -> None:
        config = VerificationRunnerConfig(
            allow_command_execution=True,
            allowed_command_prefixes=[["echo"]],
        )
        runner = VerificationRunner(config)
        result = runner.run_command("echo hello")
        assert result.status == VerificationStatus.PASSED
        assert result.exit_code == 0
        assert "hello" in result.stdout_summary

    def test_run_command_with_args(self) -> None:
        config = VerificationRunnerConfig(
            allow_command_execution=True,
            allowed_command_prefixes=[["echo"]],
        )
        runner = VerificationRunner(config)
        result = runner.run_command("echo hello world test")
        assert result.status == VerificationStatus.PASSED
        assert "hello world test" in result.stdout_summary

    def test_run_command_exit_code_nonzero(self) -> None:
        config = VerificationRunnerConfig(
            allow_command_execution=True,
            allowed_command_prefixes=[["python"]],
        )
        runner = VerificationRunner(config)
        result = runner.run_command("python -c 'exit(1)'")
        assert result.status == VerificationStatus.FAILED
        assert result.exit_code == 1

    def test_run_command_stderr_captured(self) -> None:
        config = VerificationRunnerConfig(
            allow_command_execution=True,
            allowed_command_prefixes=[["python"]],
        )
        runner = VerificationRunner(config)
        result = runner.run_command(
            "python -c 'import sys; sys.stderr.write(\"err msg\")'"
        )
        assert "err msg" in result.stderr_summary

    def test_truncate_long_output(self) -> None:
        config = VerificationRunnerConfig(
            allow_command_execution=True,
            allowed_command_prefixes=[["python"]],
            max_output_chars=20,
        )
        runner = VerificationRunner(config)
        result = runner.run_command("python -c 'print(\"x\" * 100)'")
        assert len(result.stdout_summary) <= 23  # 20 + "..."
        assert result.stdout_summary.endswith("...")

    def test_run_plan_empty(self) -> None:
        config = VerificationRunnerConfig(allow_command_execution=True)
        runner = VerificationRunner(config)
        plan = VerificationPlan()
        result = runner.run_plan(plan)
        assert result.status == VerificationStatus.SKIPPED
        assert "empty" in result.stdout_summary.lower()

    def test_run_plan_with_mixed_results(self) -> None:
        config = VerificationRunnerConfig(
            allow_command_execution=True,
            allowed_command_prefixes=[["echo"], ["python"]],
        )
        runner = VerificationRunner(config)
        plan = VerificationPlan(
            commands=["echo ok", "python -c 'exit(1)'"],
        )
        result = runner.run_plan(plan)
        assert result.status == VerificationStatus.FAILED
        assert result.command_results["echo ok"] is True
        assert result.command_results["python -c 'exit(1)'"] is False

    def test_run_plan_all_pass(self) -> None:
        config = VerificationRunnerConfig(
            allow_command_execution=True,
            allowed_command_prefixes=[["echo"]],
        )
        runner = VerificationRunner(config)
        plan = VerificationPlan(
            commands=["echo first", "echo second"],
        )
        result = runner.run_plan(plan)
        assert result.status == VerificationStatus.PASSED
        assert all(result.command_results.values())

    def test_run_command_timed_out_detected(self) -> None:
        config = VerificationRunnerConfig(
            allow_command_execution=True,
            allowed_command_prefixes=[["python"]],
            timeout_seconds=1,
        )
        runner = VerificationRunner(config)
        result = runner.run_command(
            "python -c 'import time; time.sleep(10)'"
        )
        assert result.timed_out is True
        assert result.status == VerificationStatus.FAILED
        assert "timed out" in (result.failure_reason or "").lower()

    def test_run_command_file_not_found(self) -> None:
        config = VerificationRunnerConfig(
            allow_command_execution=True,
            allowed_command_prefixes=[["nonexistent_binary_xyz"]],
        )
        runner = VerificationRunner(config)
        result = runner.run_command("nonexistent_binary_xyz --version")
        assert result.status == VerificationStatus.FAILED

    def test_runner_stores_metadata(self) -> None:
        config = VerificationRunnerConfig(
            allow_command_execution=True,
            allowed_command_prefixes=[["echo"]],
        )
        runner = VerificationRunner(config)
        result = runner.run_command("echo hello")
        assert result.duration_seconds >= 0
        assert result.command == ["echo", "hello"]
        assert result.timed_out is False

    def test_allowed_prefix_matches_partial_argv(self) -> None:
        """Prefix matching should work with compound prefixes."""
        config = VerificationRunnerConfig(
            allow_command_execution=True,
            allowed_command_prefixes=[["python", "-c"]],
        )
        runner = VerificationRunner(config)
        result = runner.run_command("python -c 'print(1)'")
        assert result.status == VerificationStatus.PASSED

    def test_prefix_mismatch_if_too_long(self) -> None:
        """Prefix longer than argv should not match."""
        config = VerificationRunnerConfig(
            allow_command_execution=True,
            allowed_command_prefixes=[["python", "-c", "long_script"]],
        )
        runner = VerificationRunner(config)
        result = runner.run_command("python -c 'short'")
        assert result.status == VerificationStatus.SKIPPED
