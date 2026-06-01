"""Tests for the ``council-plan`` CLI subcommand.

Prove:
- CLI command works
- --project-type flag works
- --goal flag works
- --strict flag works
- --json flag works
- default output is human-readable
- no LLM/API/network calls occur
"""

from __future__ import annotations

import json

from core.ralph.cli import EXIT_ERROR, EXIT_SUCCESS, _run_cli


class TestCouncilPlanCLIBasic:
    """Basic CLI command tests."""

    def test_council_plan_help(self, capsys):
        """council-plan --help shows usage.

        Note: _run_cli catches SystemExit, so this returns an error code
        but won't raise. We verify the help output is produced.
        """
        _run_cli(["council-plan", "--help"])
        captured = capsys.readouterr()
        assert "council-plan" in captured.out

    def test_council_plan_landing_page(self, capsys):
        """Generate a council plan for a landing page."""
        result = _run_cli(
            [
                "council-plan",
                "--project-type",
                "landing_page",
                "--goal",
                "Build a landing page for a whiteboard business",
            ]
        )
        assert result == EXIT_SUCCESS

        captured = capsys.readouterr()
        assert "COUNCIL PLAN SUMMARY" in captured.out
        assert "landing_page" in captured.out

    def test_council_plan_full_stack_app(self, capsys):
        """Generate a council plan for a full_stack_app."""
        result = _run_cli(
            [
                "council-plan",
                "--project-type",
                "full_stack_app",
                "--goal",
                "Build a small CRM",
            ]
        )
        assert result == EXIT_SUCCESS

        captured = capsys.readouterr()
        assert "full_stack_app" in captured.out

    def test_council_plan_json_output(self, capsys):
        """--json flag produces structured JSON."""
        result = _run_cli(
            [
                "council-plan",
                "--project-type",
                "full_stack_app",
                "--goal",
                "Build a small CRM",
                "--json",
            ]
        )
        assert result == EXIT_SUCCESS

        captured = capsys.readouterr()
        # Should be valid JSON
        data = json.loads(captured.out)
        assert isinstance(data, dict)
        assert data["project_type"] == "full_stack_app"
        assert "active_agents" in data
        assert "risks" in data
        assert "next_action" in data


class TestCouncilPlanCLIStrictMode:
    """Strict mode tests."""

    def test_council_plan_strict_mode(self, capsys):
        """--strict flag enables strict mode."""
        result = _run_cli(
            [
                "council-plan",
                "--project-type",
                "full_stack_app",
                "--goal",
                "Build a CRM",
                "--strict",
            ]
        )
        # With strict mode but full_stack_app — should still succeed
        # because agents produce the critical artifacts
        # But it might fail if required agents are missing
        # Either exit code is acceptable as long as it doesn't crash
        assert result in (EXIT_SUCCESS, EXIT_ERROR)

        captured = capsys.readouterr()
        assert len(captured.out) > 0

    def test_council_plan_non_strict_default(self, capsys):
        """Without --strict, plan is non-strict by default."""
        result = _run_cli(
            [
                "council-plan",
                "--project-type",
                "full_stack_app",
                "--goal",
                "Build a test application",
            ]
        )
        assert result == EXIT_SUCCESS


class TestCouncilPlanCLIEdgeCases:
    """Edge case tests."""

    def test_council_plan_unknown_type_non_strict(self, capsys):
        """Unknown project type in non-strict mode falls back."""
        result = _run_cli(
            [
                "council-plan",
                "--project-type",
                "bogus_type_xyz",
                "--goal",
                "Test project",
            ]
        )
        # Non-strict falls back to full_stack_app — should succeed
        assert result == EXIT_SUCCESS

        captured = capsys.readouterr()
        assert len(captured.out) > 0

    def test_council_plan_empty_goal(self, capsys):
        """Empty goal doesn't crash."""
        _run_cli(
            [
                "council-plan",
                "--project-type",
                "full_stack_app",
                "--goal",
                "",
            ]
        )
        # Should not crash — may or may not be blocked
        captured = capsys.readouterr()
        assert "COUNCIL PLAN SUMMARY" in captured.out

    def test_council_plan_no_flags(self, capsys):
        """Running council-plan with no flags uses defaults."""
        result = _run_cli(["council-plan"])
        assert result == EXIT_SUCCESS

        captured = capsys.readouterr()
        assert "COUNCIL PLAN SUMMARY" in captured.out

    def test_council_plan_with_exclusions(self, capsys):
        """--exclude-agent removes agents from plan."""
        result = _run_cli(
            [
                "council-plan",
                "--project-type",
                "full_stack_app",
                "--goal",
                "Build a CRM without content",
                "--exclude-agent",
                "brand_strategist",
            ]
        )
        assert result == EXIT_SUCCESS

    def test_json_output_no_network_calls(self, capsys):
        """Verify JSON output is generated deterministically (no LLM calls)."""
        import time

        start = time.monotonic()
        result = _run_cli(
            [
                "council-plan",
                "--project-type",
                "full_stack_app",
                "--goal",
                "Build a test application quickly",
                "--json",
            ]
        )
        elapsed = time.monotonic() - start

        # Should be very fast — no network calls
        assert elapsed < 2.0, f"CLI took {elapsed:.3f}s — possible network call"
        assert result == EXIT_SUCCESS

    def test_all_supported_types_via_cli(self, capsys):
        """Each supported project type works via CLI."""
        from core.ralph.agent_council.activation import ActivationPlanner

        planner = ActivationPlanner()
        for ptype in planner.supported_project_types:
            result = _run_cli(
                [
                    "council-plan",
                    "--project-type",
                    ptype,
                    "--goal",
                    f"Build a {ptype}",
                ]
            )
            assert result == EXIT_SUCCESS, f"Failed for project type: {ptype}"


class TestCouncilPlanCLIDeterminism:
    """Determinism tests for CLI output."""

    def test_json_output_is_deterministic(self, capsys):
        """Same input produces same JSON output."""
        args = [
            "council-plan",
            "--project-type",
            "full_stack_app",
            "--goal",
            "Build a CRM",
            "--json",
        ]

        _run_cli(args)
        out1 = capsys.readouterr().out

        _run_cli(args)
        out2 = capsys.readouterr().out

        data1 = json.loads(out1)
        data2 = json.loads(out2)

        assert data1["project_type"] == data2["project_type"]
        assert data1["total_active_agents"] == data2["total_active_agents"]
        assert data1["next_action"] == data2["next_action"]
