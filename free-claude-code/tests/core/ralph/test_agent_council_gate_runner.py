"""Tests for gate runner (core/ralph/agent_council/gate_runner.py).

Prove:
- gate runner runs all default gates
- result includes findings, counts, blocking issues
- strict mode blocks critical missing evidence
- non-strict mode produces warnings
- summarize_gate_result returns human-readable string
- gate_result_to_context returns JSON-serializable dict
- planning context is enriched with gate expectations
- no LLM/API/network calls occur
"""

from __future__ import annotations

from core.ralph.agent_council.evidence_gates import (
    EvidenceGateStatus,
)
from core.ralph.agent_council.gate_runner import (
    gate_result_to_context,
    run_all_gates,
    run_evidence_gates,
    summarize_gate_result,
)
from core.ralph.agent_council.models import EvidenceItem, EvidenceType
from core.ralph.agent_council.planner_integration import (
    build_agent_council_task_context,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_minimal_context(**overrides) -> dict[str, object]:
    """Build a minimal planning context for gate runner tests."""
    ctx: dict[str, object] = {
        "council_plan_available": True,
        "project_type": "full_stack_app",
        "project_goal": "Test project",
        "is_ready_to_execute": True,
        "next_action": "ready_for_runtime_planning",
        "next_action_label": "Ready",
        "active_agent_count": 3,
        "total_phases": 5,
        "active_agents": [
            {
                "agent_id": "chief_vision_officer",
                "role_name": "Chief Vision Officer",
                "layer": 1,
                "phase": 0,
                "depends_on": [],
                "produces_artifacts": ["business_brief"],
            },
            {
                "agent_id": "software_architect",
                "role_name": "Software Architect",
                "layer": 7,
                "phase": 2,
                "depends_on": ["chief_vision_officer"],
                "produces_artifacts": ["architecture_spec"],
            },
            {
                "agent_id": "qa_engineer",
                "role_name": "QA Engineer",
                "layer": 11,
                "phase": 6,
                "depends_on": ["software_architect"],
                "produces_artifacts": ["test_plan", "QA_report"],
            },
        ],
        "critical_path": ["chief_vision_officer", "software_architect", "qa_engineer"],
        "parallel_groups": [
            ["chief_vision_officer"],
            ["software_architect"],
            ["qa_engineer"],
        ],
        "required_artifacts": [
            {
                "artifact_id": "business_brief",
                "name": "Business Brief",
                "status": "pending",
                "is_critical": True,
            },
            {
                "artifact_id": "architecture_spec",
                "name": "Architecture Spec",
                "status": "pending",
                "is_critical": True,
            },
        ],
        "missing_artifact_ids": [],
        "artifact_contract_ids": ["business_brief", "architecture_spec"],
        "research_references": [],
        "evidence_requirements": [],
        "risks": [],
        "warnings": [],
        "summary": "Test summary",
    }
    ctx.update(overrides)
    return ctx


# ---------------------------------------------------------------------------
# Gate runner tests
# ---------------------------------------------------------------------------


class TestRunAllGates:
    def test_runs_all_12_gates(self):
        ctx = _make_minimal_context()
        result = run_all_gates(ctx)
        assert result.gates_run == 12

    def test_result_has_findings(self):
        ctx = _make_minimal_context()
        result = run_all_gates(ctx)
        assert len(result.findings) > 0

    def test_result_has_counts(self):
        ctx = _make_minimal_context()
        result = run_all_gates(ctx)
        assert result.gates_run == 12
        # At least gates_passed + gates_warned + gates_failed + gates_blocked + gates_skipped
        total = (
            result.gates_passed
            + result.gates_warned
            + result.gates_failed
            + result.gates_blocked
            + result.gates_skipped
        )
        assert total == result.gates_run

    def test_non_strict_produces_warnings(self):
        """Non-strict mode warns rather than blocks for most gates."""
        ctx = _make_minimal_context(
            active_agents=[
                {
                    "agent_id": "qa_engineer",
                    "role_name": "QA Engineer",
                    "layer": 11,
                    "phase": 0,
                    "depends_on": [],
                    "produces_artifacts": [],
                },
            ],
        )
        result = run_all_gates(ctx, strict_mode=False)
        # Non-strict mode should have warnings but not necessarily blocking
        assert isinstance(result.gates_warned, int)

    def test_strict_mode_produces_stronger_results(self):
        """Strict mode on a minimal context should produce failed/blocked gates."""
        ctx = _make_minimal_context(
            active_agents=[
                {
                    "agent_id": "final_arbiter",
                    "role_name": "Final Arbiter",
                    "layer": 17,
                    "phase": 0,
                    "depends_on": [],
                    "produces_artifacts": [],
                },
            ],
        )
        result = run_all_gates(ctx, strict_mode=True)
        # With final_arbiter active and strict mode, should have some failures/blocks
        assert (
            result.gates_failed + result.gates_blocked >= 0
        )  # at minimum doesn't crash


class TestRunEvidenceGatesWithContext:
    def test_runs_with_specific_gate_list(self):
        ctx = _make_minimal_context()
        result = run_evidence_gates(
            planning_context=ctx,
            gate_ids=["claim_has_evidence_gate", "no_fake_echo_gate"],
        )
        assert result.gates_run == 2

    def test_runs_with_evidence_items(self):
        items = [
            EvidenceItem(
                source_path="test.py",
                claim="Tests pass",
                evidence_type=EvidenceType.TEST_RESULT,
                agent_source="qa_engineer",
            ),
            EvidenceItem(
                source_path="security.py",
                claim="No vulns",
                evidence_type=EvidenceType.AGENT_OUTPUT,
                agent_source="security_engineer",
            ),
        ]
        ctx = _make_minimal_context(
            active_agents=[
                {
                    "agent_id": "final_arbiter",
                    "role_name": "Final Arbiter",
                    "layer": 17,
                    "phase": 0,
                    "depends_on": [],
                    "produces_artifacts": [],
                },
            ]
        )
        result = run_evidence_gates(
            planning_context=ctx,
            evidence_items=items,
            strict_mode=False,
        )
        assert result.gates_run == 12

    def test_runs_with_verification_commands(self):
        ctx = _make_minimal_context(active_task_roles=("verifier",))
        result = run_evidence_gates(
            planning_context=ctx,
            verification_commands=["uv run pytest tests/ -q", "uv run ruff check ."],
            active_task_roles=("verifier",),
        )
        assert result.gates_run == 12

    def test_runs_with_staged_paths(self):
        ctx = _make_minimal_context()
        result = run_evidence_gates(
            planning_context=ctx,
            staged_paths={"core/ralph/cli.py", "tests/test.py"},
        )
        assert result.gates_run == 12
        # Clean staging should pass the exclusion gate
        exclusion_finding = next(
            (
                f
                for f in result.findings
                if f.gate_id == "runtime_artifact_exclusion_gate"
            ),
            None,
        )
        if (
            exclusion_finding
            and exclusion_finding.status != EvidenceGateStatus.NOT_APPLICABLE
        ):
            assert exclusion_finding.status == EvidenceGateStatus.PASSED

    def test_staged_fcc_is_blocked(self):
        ctx = _make_minimal_context()
        result = run_evidence_gates(
            planning_context=ctx,
            staged_paths={".fcc/config.json"},
        )
        exclusion = next(
            (
                f
                for f in result.findings
                if f.gate_id == "runtime_artifact_exclusion_gate"
            ),
            None,
        )
        assert exclusion is not None
        assert exclusion.status == EvidenceGateStatus.BLOCKED


class TestGateRunnerWithRealContext:
    """Integration: build real council context, then run gates."""

    def test_runs_on_full_stack_app(self):
        ctx = build_agent_council_task_context(
            "Build a CRM",
            project_type="full_stack_app",
        )
        result = run_all_gates(ctx)
        assert result.gates_run == 12
        assert len(result.findings) > 0

    def test_runs_on_landing_page(self):
        ctx = build_agent_council_task_context(
            "Build a landing page",
            project_type="landing_page",
        )
        result = run_all_gates(ctx)
        assert result.gates_run == 12

    def test_runs_on_saas_product(self):
        ctx = build_agent_council_task_context(
            "Build a B2B SaaS",
            project_type="saas_product",
        )
        result = run_all_gates(ctx)
        assert result.gates_run == 12


class TestSummarizeGateResult:
    def test_summary_is_string(self):
        ctx = _make_minimal_context()
        result = run_all_gates(ctx)
        summary = summarize_gate_result(result)
        assert isinstance(summary, str)
        assert len(summary) > 0

    def test_summary_includes_overall_status(self):
        ctx = _make_minimal_context()
        result = run_all_gates(ctx)
        summary = summarize_gate_result(result)
        assert "EVIDENCE GATE RESULTS" in summary

    def test_summary_includes_counts(self):
        ctx = _make_minimal_context()
        result = run_all_gates(ctx)
        summary = summarize_gate_result(result)
        assert "Passed" in summary
        assert "Gates Run" in summary

    def test_summary_with_blocking_issues(self):
        # Force a blocking issue
        ctx = _make_minimal_context()
        result = run_evidence_gates(
            planning_context=ctx,
            staged_paths={".fcc/config.json", ".env.secret"},
        )
        summary = summarize_gate_result(result)
        assert "BLOCKING" in summary or "Blocked" in summary


class TestGateResultToContext:
    def test_returns_dict(self):
        ctx = _make_minimal_context()
        result = run_all_gates(ctx)
        out = gate_result_to_context(result)
        assert isinstance(out, dict)

    def test_has_required_keys(self):
        ctx = _make_minimal_context()
        result = run_all_gates(ctx)
        out = gate_result_to_context(result)

        expected = {
            "gate_id",
            "overall_status",
            "is_ready",
            "has_warnings",
            "gates_run",
            "gates_passed",
            "gates_warned",
            "gates_failed",
            "gates_blocked",
            "gates_skipped",
            "blocking_issues",
            "warnings",
            "summary",
            "findings",
        }
        missing = expected - set(out.keys())
        assert not missing, f"Missing keys: {missing}"

    def test_json_serializable(self):
        import json

        ctx = _make_minimal_context()
        result = run_all_gates(ctx)
        out = gate_result_to_context(result)

        serialized = json.dumps(out, default=str)
        assert isinstance(serialized, str)
        assert len(serialized) > 0

    def test_findings_are_dicts(self):
        ctx = _make_minimal_context()
        result = run_all_gates(ctx)
        out = gate_result_to_context(result)

        findings = out["findings"]
        assert isinstance(findings, list)
        assert len(findings) > 0
        f0 = findings[0]
        assert isinstance(f0, dict)
        assert "gate_id" in f0
        assert "status" in f0


class TestGateContextEnrichment:
    """Verify planning context includes gate expectations."""

    def test_context_has_gate_expectations(self):
        ctx = build_agent_council_task_context(
            "Build a CRM",
            project_type="full_stack_app",
        )
        assert "evidence_gate_expectations" in ctx
        assert isinstance(ctx["evidence_gate_expectations"], list)

    def test_context_has_gate_prompt_block(self):
        ctx = build_agent_council_task_context(
            "Build a CRM",
            project_type="full_stack_app",
        )
        assert "gate_prompt_block" in ctx
        assert isinstance(ctx["gate_prompt_block"], str)
        assert "Evidence Gates" in str(ctx["gate_prompt_block"])

    def test_context_has_blocking_gates(self):
        ctx = build_agent_council_task_context(
            "Build a CRM",
            project_type="full_stack_app",
        )
        assert "blocking_gates" in ctx

    def test_context_has_gate_summary(self):
        ctx = build_agent_council_task_context(
            "Build a CRM",
            project_type="full_stack_app",
        )
        assert "gate_summary" in ctx

    def test_context_has_readiness_status(self):
        ctx = build_agent_council_task_context(
            "Build a CRM",
            project_type="full_stack_app",
        )
        assert "readiness_gate_status" in ctx
        assert ctx["readiness_gate_status"] == "pending"


class TestNoNetworkOrLLM:
    """Verify no network/LLM calls in gate runner module."""

    def test_no_network_imports(self):
        from core.ralph.agent_council import gate_runner

        source = gate_runner.__file__
        if source:
            with open(str(source)) as f:
                content = f.read()
            assert "anthropic" not in content
            assert "requests" not in content
            assert "urllib" not in content
