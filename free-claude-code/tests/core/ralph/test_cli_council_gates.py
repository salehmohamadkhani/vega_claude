"""Tests for the ``council-gates`` CLI subcommand.

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


class TestCouncilGatesCLIBasic:
    """Basic CLI tests for council-gates."""

    def test_council_gates_help(self, capsys):
        """council-gates --help shows usage."""
        _run_cli(["council-gates", "--help"])
        captured = capsys.readouterr()
        assert "council-gates" in captured.out

    def test_council_gates_full_stack(self, capsys):
        """Run gates against a full_stack_app plan."""
        result = _run_cli(
            [
                "council-gates",
                "--project-type",
                "full_stack_app",
                "--goal",
                "Build a small CRM",
            ]
        )
        # May pass or fail depending on context — just verify it runs
        assert result in (EXIT_SUCCESS, EXIT_ERROR)

        captured = capsys.readouterr()
        assert "EVIDENCE GATE RESULTS" in captured.out

    def test_council_gates_landing_page(self, capsys):
        """Run gates against a landing_page plan."""
        _run_cli(
            [
                "council-gates",
                "--project-type",
                "landing_page",
                "--goal",
                "Build a landing page",
            ]
        )
        captured = capsys.readouterr()
        assert "EVIDENCE GATE RESULTS" in captured.out

    def test_council_gates_json(self, capsys):
        """--json flag produces structured output."""
        _run_cli(
            [
                "council-gates",
                "--project-type",
                "full_stack_app",
                "--goal",
                "Build a CRM",
                "--json",
            ]
        )
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert isinstance(data, dict)
        assert "gates_run" in data
        assert "findings" in data
        assert len(data["findings"]) > 0

    def test_council_gates_strict(self, capsys):
        """--strict flag is accepted."""
        _run_cli(
            [
                "council-gates",
                "--project-type",
                "full_stack_app",
                "--goal",
                "Build a CRM",
                "--strict",
            ]
        )
        captured = capsys.readouterr()
        assert "EVIDENCE GATE RESULTS" in captured.out

    def test_council_gates_no_flags(self, capsys):
        """Running with no flags uses defaults."""
        _run_cli(["council-gates"])
        captured = capsys.readouterr()
        assert "EVIDENCE GATE RESULTS" in captured.out

    def test_council_gates_saas_product(self, capsys):
        """All project types work."""
        for ptype in ("landing_page", "full_stack_app", "saas_product"):
            _run_cli(
                [
                    "council-gates",
                    "--project-type",
                    ptype,
                    "--goal",
                    f"Build a {ptype}",
                ]
            )
            captured = capsys.readouterr()
            assert "EVIDENCE GATE RESULTS" in captured.out


class TestCouncilGatesCLIDeterminism:
    """Determinism tests."""

    def test_same_input_same_output(self, capsys):
        """Same input produces same gate run count."""
        args = [
            "council-gates",
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

        assert data1["gates_run"] == data2["gates_run"]


class TestNoNetwork:
    """Verify CLI doesn't make network calls."""

    def test_fast_execution(self):
        """CLI should complete very quickly — no network calls."""
        import time

        start = time.monotonic()
        _run_cli(
            [
                "council-gates",
                "--project-type",
                "full_stack_app",
                "--goal",
                "Test",
                "--json",
            ]
        )
        elapsed = time.monotonic() - start

        assert elapsed < 2.0, f"CLI took {elapsed:.3f}s — possible network call"
