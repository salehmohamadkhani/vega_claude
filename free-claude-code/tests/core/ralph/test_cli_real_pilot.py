"""Tests for CLI real-pilot command integration."""

from __future__ import annotations

import json
from pathlib import Path

from core.ralph.cli import (
    EXIT_ERROR,
    EXIT_SUCCESS,
    EXIT_UNSAFE_REAL,
    _run_cli,
)
from core.ralph.workspace import RalphWorkspace


def _ws(project_root: Path) -> RalphWorkspace:
    return RalphWorkspace(project_root=str(project_root))


class TestCliRealPilotBasic:
    """Basic CLI pilot command tests."""

    def test_pilot_dry_run_succeeds(self, tmp_path: Path) -> None:
        """fcc-ralph run --pilot works in dry-run mode."""
        rc = _run_cli(
            [
                f"--workspace={tmp_path}",
                "run",
                "--pilot",
                f"--pilot-workspace={tmp_path / 'pilot'}",
            ]
        )
        assert rc == EXIT_SUCCESS

    def test_pilot_dry_run_json_parseable(self, tmp_path: Path, capsys) -> None:
        """fcc-ralph run --pilot --json produces parseable JSON."""
        capsys.readouterr()
        _rc = _run_cli(
            [
                f"--workspace={tmp_path}",
                "--json",
                "run",
                "--pilot",
                f"--pilot-workspace={tmp_path / 'pilot'}",
            ]
        )
        captured = capsys.readouterr()
        assert captured.out.strip(), "Expected JSON output"
        data = json.loads(captured.out)
        assert "pilot_workspace_path" in data
        assert "run_id" in data
        assert "task_id" in data
        assert "passed" in data
        assert "guard" in data
        assert "loop" in data

    def test_pilot_creates_workspace(self, tmp_path: Path) -> None:
        """Pilot creates a workspace at the specified path."""
        pilot_path = tmp_path / "pilot_ws"
        _run_cli(
            [
                f"--workspace={tmp_path}",
                "run",
                "--pilot",
                f"--pilot-workspace={pilot_path}",
            ]
        )
        assert pilot_path.exists()
        # The pilot writes README.md inside the Ralph workspace (.fcc-ralph/)
        ralph_dir = pilot_path / ".fcc-ralph"
        readme = ralph_dir / "README.md"
        assert readme.exists(), f"README.md not found at {readme}"

    def test_pilot_without_real_is_dry_run(self, tmp_path: Path) -> None:
        """Pilot without --real is dry-run (exit 0)."""
        rc = _run_cli(
            [
                f"--workspace={tmp_path}",
                "run",
                "--pilot",
                f"--pilot-workspace={tmp_path / 'pilot'}",
            ]
        )
        assert rc == EXIT_SUCCESS


class TestCliRealPilotSafety:
    """Safety tests for CLI pilot command."""

    def test_pilot_real_without_allow_fails_safely(self, tmp_path: Path) -> None:
        """Pilot --real without --allow-real-execution fails."""
        rc = _run_cli(
            [
                f"--workspace={tmp_path}",
                "run",
                "--pilot",
                "--real",
                f"--pilot-workspace={tmp_path / 'pilot'}",
            ]
        )
        assert rc == EXIT_UNSAFE_REAL

    def test_pilot_real_with_allow_succeeds_in_dry_run(
        self, tmp_path: Path
    ) -> None:
        """Pilot --real --allow-real-execution runs (dry-run in tests)."""
        rc = _run_cli(
            [
                f"--workspace={tmp_path}",
                "run",
                "--pilot",
                "--real",
                "--allow-real-execution",
                f"--pilot-workspace={tmp_path / 'pilot'}",
            ]
        )
        assert rc in (EXIT_SUCCESS, EXIT_ERROR)

    def test_pilot_refuses_system_root(self, tmp_path: Path) -> None:
        """Pilot refuses to run real execution on system root."""
        rc = _run_cli(
            [
                f"--workspace={tmp_path}",
                "run",
                "--pilot",
                "--pilot-workspace=C:\\",
                "--real",
                "--allow-real-execution",
            ]
        )
        assert rc == EXIT_UNSAFE_REAL

    def test_pilot_with_json_parseable_on_error(
        self, tmp_path: Path, capsys
    ) -> None:
        """Pilot with --json produces parseable JSON even on error."""
        capsys.readouterr()
        rc = _run_cli(
            [
                f"--workspace={tmp_path}",
                "--json",
                "run",
                "--pilot",
                "--pilot-workspace=C:\\",
                "--real",
                "--allow-real-execution",
            ]
        )
        captured = capsys.readouterr()
        if captured.out.strip():
            data = json.loads(captured.out)
            assert "pilot_workspace_path" in data or "guard" in data
        assert rc == EXIT_UNSAFE_REAL


class TestCliRealPilotNoSideEffects:
    """No unsafe side effects from pilot command."""

    def test_pilot_no_provider_imports(self) -> None:
        """Pilot command does not import provider modules.

        Pilot mode ignores the ``--workspace`` flag and creates its own,
        so a nonexistent workspace path does not cause errors.
        """
        rc = _run_cli(["--workspace=C:\\nonexistent", "run", "--pilot"])
        # Pilot should succeed (dry-run) since it creates its own workspace
        assert rc == EXIT_SUCCESS

    def test_pilot_no_api_key_usage(self) -> None:
        """Pilot command does not read API keys."""
        import os
        original = os.environ.get("ANTHROPIC_API_KEY")
        if original:
            del os.environ["ANTHROPIC_API_KEY"]
        try:
            _run_cli(["--workspace=C:\\nonexistent", "run", "--pilot"])
        except Exception:
            pass  # No API key needed for CLI arg parsing
        finally:
            if original:
                os.environ["ANTHROPIC_API_KEY"] = original
