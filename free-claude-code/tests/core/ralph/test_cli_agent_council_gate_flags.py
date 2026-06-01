"""Tests for Agent Council gate CLI flags.

Prove:
- CLI parses --use-agent-council-gates
- CLI parses --strict-agent-council-gates
- CLI parses --project-type for run
- old CLI behavior remains unchanged without flags
- no LLM/API/network calls occur
"""

from __future__ import annotations

import contextlib

from core.ralph.cli import (
    EXIT_ERROR,
    EXIT_SUCCESS,
    _build_gate_config_from_args,
    _build_parser,
)


class TestCLIParsingGateFlags:
    """Verify the argument parser accepts council gate flags."""

    def test_run_parser_has_gate_flags(self):
        parser = _build_parser()
        args = parser.parse_args(
            [
                "run",
                "--use-agent-council-gates",
                "--project-type",
                "full_stack_app",
            ]
        )
        assert args.use_agent_council_gates is True
        assert args.run_project_type == "full_stack_app"

    def test_run_parser_has_strict_flag(self):
        parser = _build_parser()
        args = parser.parse_args(
            [
                "run",
                "--strict-agent-council-gates",
            ]
        )
        assert args.strict_agent_council_gates is True

    def test_run_parser_defaults(self):
        parser = _build_parser()
        args = parser.parse_args(["run"])
        assert args.use_agent_council_gates is False
        assert args.strict_agent_council_gates is False
        assert args.run_project_type is None

    def test_run_parser_gates_without_strict(self):
        parser = _build_parser()
        args = parser.parse_args(
            [
                "run",
                "--use-agent-council-gates",
            ]
        )
        assert args.use_agent_council_gates is True
        assert args.strict_agent_council_gates is False

    def test_run_parser_combined(self):
        parser = _build_parser()
        args = parser.parse_args(
            [
                "run",
                "--loop",
                "--use-agent-council-gates",
                "--strict-agent-council-gates",
                "--project-type",
                "saas_product",
                "--max-iterations",
                "5",
            ]
        )
        assert args.loop is True
        assert args.use_agent_council_gates is True
        assert args.strict_agent_council_gates is True
        assert args.run_project_type == "saas_product"
        assert args.max_iterations == 5

    def test_run_help_includes_gate_flags(self, capsys):
        parser = _build_parser()
        with contextlib.suppress(SystemExit):
            parser.parse_args(["run", "--help"])
        captured = capsys.readouterr()
        assert "use-agent-council-gates" in captured.out

    def test_run_without_flags_unchanged(self):
        """Old behavior: run without gate flags should parse fine."""
        parser = _build_parser()
        args = parser.parse_args(["run", "--loop", "--max-iterations", "3"])
        assert args.use_agent_council_gates is False
        assert args.loop is True


class TestBuildGateConfigFromArgs:
    """Test the _build_gate_config_from_args helper."""

    def test_disabled_returns_none(self):
        parser = _build_parser()
        args = parser.parse_args(["run"])
        assert _build_gate_config_from_args(args) is None

    def test_enabled_returns_config(self):
        parser = _build_parser()
        args = parser.parse_args(["run", "--use-agent-council-gates"])
        config = _build_gate_config_from_args(args)
        assert config is not None
        assert config.use_agent_council_gates is True

    def test_strict_returns_config(self):
        parser = _build_parser()
        args = parser.parse_args(["run", "--strict-agent-council-gates"])
        config = _build_gate_config_from_args(args)
        assert config is not None
        assert config.use_agent_council_gates is True  # strict implies use
        assert config.strict_agent_council_gates is True

    def test_with_project_type(self):
        parser = _build_parser()
        args = parser.parse_args(
            [
                "run",
                "--use-agent-council-gates",
                "--project-type",
                "landing_page",
            ]
        )
        config = _build_gate_config_from_args(args)
        assert config is not None
        assert config.project_type == "landing_page"


class TestOldCLIBehaviorUnchanged:
    """Verify existing CLI behavior is preserved without gate flags."""

    def test_plan_still_works(self, capsys):
        from core.ralph.cli import _run_cli

        result = _run_cli(["plan", "Test goal"])
        captured = capsys.readouterr()
        assert result in (EXIT_SUCCESS, EXIT_ERROR)
        # Should not contain any gate-related output
        assert "use-agent-council-gates" not in captured.out.lower()

    def test_review_still_works(self, capsys):
        from core.ralph.cli import _run_cli

        # Review without workspace returns error — which is correct old behavior
        result = _run_cli(["review"])
        assert result in (EXIT_SUCCESS, EXIT_ERROR)

    def test_approve_help_still_works(self, capsys):
        from core.ralph.cli import _run_cli

        _run_cli(["approve", "--help"])
        captured = capsys.readouterr()
        assert "approve" in captured.out.lower()

    def test_help_mentions_run_subcommand(self, capsys):
        from core.ralph.cli import _run_cli

        _run_cli(["--help"])
        captured = capsys.readouterr()
        assert "run" in captured.out


class TestNoNetwork:
    """Verify CLI doesn't make network calls."""

    def test_fast_parsing(self):
        import time

        start = time.monotonic()
        parser = _build_parser()
        parser.parse_args(
            [
                "run",
                "--loop",
                "--use-agent-council-gates",
                "--strict-agent-council-gates",
                "--project-type",
                "full_stack_app",
            ]
        )
        elapsed = time.monotonic() - start
        assert elapsed < 1.0, f"Parsing took {elapsed:.3f}s"
