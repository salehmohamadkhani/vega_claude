"""Tests for execution models — ExecutionMode, ExecutionStatus,
ExecutionRequest, ExecutionResult, ExecutionConfig."""

from __future__ import annotations

from core.ralph.execution import (
    ExecutionConfig,
    ExecutionMode,
    ExecutionRequest,
    ExecutionResult,
    ExecutionStatus,
)


class TestExecutionMode:
    def test_dry_run_is_default(self) -> None:
        assert ExecutionMode.DRY_RUN.value == "dry_run"

    def test_real_mode_exists(self) -> None:
        assert ExecutionMode.REAL.value == "real"


class TestExecutionStatus:
    def test_all_status_values(self) -> None:
        expected = [
            "not_started",
            "skipped",
            "running",
            "succeeded",
            "failed",
            "timed_out",
            "cancelled",
        ]
        values = [s.value for s in ExecutionStatus]
        assert values == expected


class TestExecutionRequest:
    def test_defaults_are_sensible(self) -> None:
        req = ExecutionRequest()
        assert req.mode == ExecutionMode.DRY_RUN
        assert req.timeout_seconds == 300
        assert req.allowed_files == []
        assert req.forbidden_files == []

    def test_custom_values(self) -> None:
        req = ExecutionRequest(
            run_id="run-1",
            task_id="task-1",
            task_title="Test Task",
            prompt="Do the thing",
            workspace_path="/tmp/ws",
            mode=ExecutionMode.REAL,
            timeout_seconds=600,
            allowed_files=["src/"],
            forbidden_files=["tests/"],
            metadata={"key": "value"},
        )
        assert req.run_id == "run-1"
        assert req.task_id == "task-1"
        assert req.task_title == "Test Task"
        assert req.prompt == "Do the thing"
        assert req.workspace_path == "/tmp/ws"
        assert req.mode == ExecutionMode.REAL
        assert req.timeout_seconds == 600
        assert req.allowed_files == ["src/"]
        assert req.forbidden_files == ["tests/"]
        assert req.metadata == {"key": "value"}


class TestExecutionResult:
    def test_default_fields(self) -> None:
        result = ExecutionResult()
        assert result.status == ExecutionStatus.NOT_STARTED
        assert result.mode == ExecutionMode.DRY_RUN
        assert result.exit_code == -1
        assert result.changed_files == []
        assert not result.timed_out

    def test_to_dict_roundtrip(self) -> None:
        result = ExecutionResult(
            run_id="run-1",
            task_id="task-1",
            status=ExecutionStatus.SUCCEEDED,
            mode=ExecutionMode.REAL,
            command="claude --print prompt",
            exit_code=0,
            duration_seconds=12.5,
            stdout_summary="done",
            changed_files=["src/main.py"],
        )
        d = result.to_dict()
        assert d["run_id"] == "run-1"
        assert d["task_id"] == "task-1"
        assert d["status"] == "succeeded"
        assert d["mode"] == "real"
        assert d["command"] == "claude --print prompt"
        assert d["exit_code"] == 0
        assert d["duration_seconds"] == 12.5
        assert d["stdout_summary"] == "done"
        assert d["changed_files"] == ["src/main.py"]

    def test_skipped_factory(self) -> None:
        result = ExecutionResult.skipped(reason="No thanks")
        assert result.status == ExecutionStatus.SKIPPED
        assert result.mode == ExecutionMode.DRY_RUN
        assert result.failure_reason == "No thanks"
        assert result.finished_at != ""


class TestExecutionConfig:
    def test_default_config_is_dry_run(self) -> None:
        config = ExecutionConfig()
        assert config.dry_run is True
        assert config.allow_real_execution is False
        assert config.allow_test_fallback is False
        assert config.timeout_seconds == 300
        assert config.max_output_chars == 50000
        assert "fcc-claude" in config.command_allowlist
        assert "claude" in config.command_allowlist

    def test_custom_config(self) -> None:
        config = ExecutionConfig(
            workspace_path="/custom/ws",
            timeout_seconds=120,
            max_output_chars=1000,
            allow_real_execution=True,
            dry_run=False,
            allow_test_fallback=True,
        )
        assert config.workspace_path == "/custom/ws"
        assert config.timeout_seconds == 120
        assert config.max_output_chars == 1000
        assert config.allow_real_execution is True
        assert config.dry_run is False
        assert config.allow_test_fallback is True
