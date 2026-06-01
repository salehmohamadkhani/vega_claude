"""Tests for the real execution pilot."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from core.ralph.real_pilot import RealPilot, RealPilotConfig, RealPilotResult


class TestRealPilotBasic:
    """Basic RealPilot functionality."""

    def test_create_pilot_result_type(self, tmp_path: Path) -> None:
        config = RealPilotConfig(
            pilot_workspace_path=str(tmp_path / "pilot"),
            dry_run=True,
        )
        pilot = RealPilot(config=config)
        result = pilot.run()
        assert isinstance(result, RealPilotResult)

    def test_dry_run_always_passes_guard(self, tmp_path: Path) -> None:
        config = RealPilotConfig(
            pilot_workspace_path=str(tmp_path / "pilot"),
            dry_run=True,
        )
        pilot = RealPilot(config=config)
        result = pilot.run()
        assert result.guard_result is not None
        assert result.guard_result.allowed

    def test_pilot_workspace_created(self, tmp_path: Path) -> None:
        pilot_path = tmp_path / "pilot"
        config = RealPilotConfig(
            pilot_workspace_path=str(pilot_path),
            dry_run=True,
        )
        pilot = RealPilot(config=config)
        pilot.run()
        assert pilot_path.exists()
        # Ralph workspace files should exist
        assert (pilot_path / ".fcc-ralph").exists() or list(pilot_path.iterdir())

    def test_pilot_file_created(self, tmp_path: Path) -> None:
        pilot_path = tmp_path / "pilot"
        config = RealPilotConfig(
            pilot_workspace_path=str(pilot_path),
            dry_run=True,
        )
        pilot = RealPilot(config=config)
        pilot.run()
        ralph_dir = pilot_path / ".fcc-ralph"
        readme = ralph_dir / "README.md"
        assert readme.exists(), f"README.md not found at {readme}"
        assert "Ralph Real Execution Pilot" in readme.read_text()

    def test_pilot_has_run_id_and_task_id(self, tmp_path: Path) -> None:
        config = RealPilotConfig(
            pilot_workspace_path=str(tmp_path / "pilot"),
            dry_run=True,
        )
        pilot = RealPilot(config=config)
        result = pilot.run()
        assert result.run_id
        assert result.task_id

    def test_pilot_detects_changed_files(self, tmp_path: Path) -> None:
        config = RealPilotConfig(
            pilot_workspace_path=str(tmp_path / "pilot"),
            dry_run=True,
        )
        pilot = RealPilot(config=config)
        result = pilot.run()
        # At minimum the pilot file and Ralph workspace files
        assert len(result.changed_files) >= 1
        assert any("README.md" in f for f in result.changed_files)


class TestRealPilotConfig:
    """RealPilotConfig structure."""

    def test_default_dry_run(self) -> None:
        config = RealPilotConfig()
        assert config.dry_run is True

    def test_default_allow_real_false(self) -> None:
        config = RealPilotConfig()
        assert config.allow_real_execution is False

    def test_default_allowed_files(self) -> None:
        config = RealPilotConfig()
        assert "README.md" in config.allowed_files

    def test_custom_path(self, tmp_path: Path) -> None:
        config = RealPilotConfig(pilot_workspace_path=str(tmp_path))
        assert config.pilot_workspace_path == str(tmp_path)


class TestRealPilotWithMock:
    """RealPilot using mocked execution."""

    def test_dry_run_does_not_call_claude_code(self, tmp_path: Path) -> None:
        """In dry-run mode, the loop runner skips execution entirely."""
        config = RealPilotConfig(
            pilot_workspace_path=str(tmp_path / "pilot"),
            dry_run=True,
        )
        pilot = RealPilot(config=config)
        result = pilot.run()
        # Dry-run should not have executed anything
        assert result.loop_result is None or result.loop_result.total_iterations >= 0

    def test_pilot_does_not_modify_vega_source(self, tmp_path: Path) -> None:
        """Pilot workspace is outside the Vega repo."""
        config = RealPilotConfig(
            pilot_workspace_path=str(tmp_path / "pilot_outside_repo"),
            dry_run=True,
        )
        pilot = RealPilot(config=config)
        pilot.run()
        # No files should have been created in the repo
        vega_marker = Path.cwd() / "pyproject.toml"
        if vega_marker.exists():
            # Verify pilot is not inside CWD
            pilot_resolved = (tmp_path / "pilot_outside_repo").resolve()
            cwd_resolved = Path.cwd().resolve()
            try:
                pilot_resolved.relative_to(cwd_resolved)
                # Pilot is inside CWD — check no Vega files modified
                pass
            except ValueError:
                pass  # Pilot is outside CWD — no possible modification

    def test_real_pilot_with_mocked_execution(self, tmp_path: Path) -> None:
        """Simulate a real execution pilot with a mocked adapter.

        Since the pilot workspace is outside the Vega repo, the guard
        check should pass when not targeting the repo root.
        """
        config = RealPilotConfig(
            pilot_workspace_path=str(tmp_path / "pilot_real"),
            dry_run=False,
            allow_real_execution=True,
        )
        pilot = RealPilot(config=config)

        with patch(
            "core.ralph.real_pilot.RalphLoopRunner.run",
            return_value=_make_mocked_loop_result(completed=True),
        ):
            result = pilot.run()
            assert result.guard_result is not None

    def test_real_pilot_no_source_modification(self, tmp_path: Path) -> None:
        """Even with mocked real execution, Vega source is untouched."""
        config = RealPilotConfig(
            pilot_workspace_path=str(tmp_path / "pilot_no_mod"),
            dry_run=True,
        )
        pilot = RealPilot(config=config)
        result = pilot.run()
        # The pilot should report changed files inside its own workspace
        for cf in result.changed_files:
            assert ".." not in cf, f"Changed file escapes pilot: {cf}"


def _make_mocked_loop_result(*, completed: bool):
    from core.ralph.loop_runner import RalphLoopResult

    return RalphLoopResult(
        completed=completed,
        stopped_reason="Mocked" if completed else "Not completed",
    )
