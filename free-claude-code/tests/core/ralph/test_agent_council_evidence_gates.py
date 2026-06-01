"""Tests for evidence gate models and default gates (evidence_gates.py).

Prove:
- gate enums exist with correct values
- EvidenceGateRequirement creates correctly
- EvidenceGateFinding creates correctly
- EvidenceGateResult aggregates correctly
- all 12 default gates load
- gate IDs are unique
- default gate metadata is complete
- gate functions exist and are callable
- no LLM/API/network calls occur
"""

from __future__ import annotations

from core.ralph.agent_council.evidence_gates import (
    EvidenceGateFinding,
    EvidenceGateRequirement,
    EvidenceGateResult,
    EvidenceGateSeverity,
    EvidenceGateStatus,
    GateEvaluationContext,
    _gate_artifact_exists,
    _gate_artifact_non_empty,
    _gate_claim_has_evidence,
    _gate_final_arbiter,
    _gate_implementation_file,
    _gate_no_fake_echo,
    _gate_qa_behavior,
    _gate_research_reference,
    _gate_runtime_artifact_exclusion,
    _gate_security_evidence,
    _gate_verification_command,
    _gate_visual_evidence,
    get_default_gate_requirements,
    get_gate_function,
    list_default_gate_ids,
)
from core.ralph.agent_council.models import EvidenceItem, EvidenceType

# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEvidenceGateSeverity:
    def test_all_values_exist(self):
        assert {e.value for e in EvidenceGateSeverity} == {
            "info",
            "warning",
            "error",
            "critical",
        }


class TestEvidenceGateStatus:
    def test_all_values_exist(self):
        assert {e.value for e in EvidenceGateStatus} == {
            "passed",
            "warning",
            "failed",
            "blocked",
            "not_applicable",
        }


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------


class TestEvidenceGateRequirement:
    def test_minimal_requirement(self):
        req = EvidenceGateRequirement(gate_id="test_gate")
        assert req.gate_id == "test_gate"
        assert req.name == ""
        assert req.blocking is False

    def test_full_requirement(self):
        req = EvidenceGateRequirement(
            gate_id="artifact_exists_gate",
            name="Artifact Existence Check",
            description="Must exist.",
            required_evidence_types=("test_result",),
            required_paths=("reports/",),
            required_artifacts=("QA_report",),
            applies_to_agents=("qa_engineer",),
            applies_to_task_roles=("verifier",),
            applies_to_layers=(11,),
            blocking=True,
            severity=EvidenceGateSeverity.CRITICAL,
            min_evidence_count=1,
            exclusive_paths=(".fcc/",),
        )
        assert req.blocking is True
        assert req.severity == EvidenceGateSeverity.CRITICAL
        assert "qa_engineer" in req.applies_to_agents


class TestEvidenceGateFinding:
    def test_minimal_finding(self):
        f = EvidenceGateFinding(gate_id="test")
        assert f.gate_id == "test"
        assert f.status == EvidenceGateStatus.NOT_APPLICABLE

    def test_finding_with_details(self):
        f = EvidenceGateFinding(
            gate_id="test",
            status=EvidenceGateStatus.FAILED,
            message="Something wrong.",
            affected_paths=["test.py"],
            required_action="Fix it.",
            severity=EvidenceGateSeverity.ERROR,
        )
        assert f.status == EvidenceGateStatus.FAILED
        assert "test.py" in f.affected_paths
        assert f.severity == EvidenceGateSeverity.ERROR


class TestEvidenceGateResult:
    def test_empty_result(self):
        r = EvidenceGateResult()
        assert r.overall_status == EvidenceGateStatus.NOT_APPLICABLE
        assert r.is_ready is True  # no blocking issues
        assert r.has_warnings is False

    def test_result_with_blocking_issues(self):
        r = EvidenceGateResult(
            blocking_issues=["Critical: missing artifact"],
            overall_status=EvidenceGateStatus.BLOCKED,
        )
        assert r.is_ready is False

    def test_result_with_warnings(self):
        r = EvidenceGateResult(
            warnings=["Missing research references"],
            gates_warned=1,
            overall_status=EvidenceGateStatus.WARNING,
        )
        assert r.has_warnings is True

    def test_result_aggregation(self):
        findings = [
            EvidenceGateFinding(gate_id="g1", status=EvidenceGateStatus.PASSED),
            EvidenceGateFinding(
                gate_id="g2", status=EvidenceGateStatus.WARNING, message="warn"
            ),
            EvidenceGateFinding(
                gate_id="g3", status=EvidenceGateStatus.FAILED, message="fail"
            ),
            EvidenceGateFinding(
                gate_id="g4", status=EvidenceGateStatus.BLOCKED, message="block"
            ),
        ]
        r = EvidenceGateResult(
            gate_id="test_run",
            findings=findings,
            gates_run=4,
            gates_passed=1,
            gates_warned=1,
            gates_failed=1,
            gates_blocked=1,
            overall_status=EvidenceGateStatus.BLOCKED,
        )
        assert r.gates_run == 4
        assert len(r.findings) == 4


class TestGateEvaluationContext:
    def test_minimal_context(self):
        ctx = GateEvaluationContext()
        assert ctx.project_type == ""
        assert ctx.strict_mode is False

    def test_context_with_agents(self):
        ctx = GateEvaluationContext(
            active_agent_ids=("qa_engineer", "security_engineer"),
            strict_mode=True,
        )
        assert "qa_engineer" in ctx.active_agent_ids
        assert ctx.strict_mode is True


# ---------------------------------------------------------------------------
# Default gates — registration
# ---------------------------------------------------------------------------


class TestDefaultGatesExist:
    def test_all_12_gates_exist(self):
        gates = list_default_gate_ids()
        assert len(gates) == 12

    def test_gate_ids_are_unique(self):
        gates = list_default_gate_ids()
        assert len(gates) == len(set(gates))

    def test_expected_gate_ids(self):
        gates = set(list_default_gate_ids())
        expected = {
            "artifact_exists_gate",
            "artifact_non_empty_gate",
            "claim_has_evidence_gate",
            "implementation_file_gate",
            "verification_command_gate",
            "qa_behavior_gate",
            "security_evidence_gate",
            "visual_evidence_gate",
            "research_reference_gate",
            "final_arbiter_gate",
            "no_fake_echo_gate",
            "runtime_artifact_exclusion_gate",
        }
        assert gates == expected

    def test_all_gate_functions_exist(self):
        for gid in list_default_gate_ids():
            fn = get_gate_function(gid)
            assert fn is not None, f"Gate function missing: {gid}"
            assert callable(fn)

    def test_default_gate_requirements_load(self):
        reqs = get_default_gate_requirements()
        assert len(reqs) == 12
        ids = {r.gate_id for r in reqs}
        assert len(ids) == 12  # unique

    def test_gate_requirements_have_names(self):
        for req in get_default_gate_requirements():
            assert req.name, f"Gate {req.gate_id} has no name"
            assert req.description, f"Gate {req.gate_id} has no description"

    def test_nonexistent_gate_returns_none(self):
        assert get_gate_function("does_not_exist") is None


# ---------------------------------------------------------------------------
# Default gates — evaluation
# ---------------------------------------------------------------------------


class TestArtifactExistsGate:
    def test_passes_when_all_artifacts_available(self):
        ctx = GateEvaluationContext(
            required_artifacts=("business_brief", "architecture_spec"),
            available_paths=("business_brief", "architecture_spec"),
        )
        finding = _gate_artifact_exists(ctx)
        assert finding.status == EvidenceGateStatus.PASSED

    def test_na_when_no_required_artifacts(self):
        ctx = GateEvaluationContext()
        finding = _gate_artifact_exists(ctx)
        assert finding.status == EvidenceGateStatus.NOT_APPLICABLE

    def test_warns_in_non_strict_mode(self):
        ctx = GateEvaluationContext(
            required_artifacts=("test_plan",),
            available_paths=("other",),
            strict_mode=False,
        )
        finding = _gate_artifact_exists(ctx)
        assert finding.status == EvidenceGateStatus.WARNING

    def test_blocks_in_strict_mode(self):
        ctx = GateEvaluationContext(
            required_artifacts=("test_plan",),
            available_paths=("other",),
            strict_mode=True,
        )
        finding = _gate_artifact_exists(ctx)
        assert finding.status == EvidenceGateStatus.BLOCKED

    def test_missing_artifacts_are_counted_correctly(self):
        ctx = GateEvaluationContext(
            required_artifacts=("a", "b", "c"),
            available_paths=("a",),
            missing_artifacts=("b",),
            strict_mode=False,
        )
        finding = _gate_artifact_exists(ctx)
        # 'c' is missing and not in missing_artifacts
        assert finding.status == EvidenceGateStatus.WARNING


class TestArtifactNonEmptyGate:
    def test_na_when_no_files_to_check(self):
        ctx = GateEvaluationContext()
        finding = _gate_artifact_non_empty(ctx)
        assert finding.status == EvidenceGateStatus.NOT_APPLICABLE

    def test_fails_on_empty_files(self):
        ctx = GateEvaluationContext(
            required_artifacts=("report.md",),
            available_file_sizes={"report.md": 0},
        )
        finding = _gate_artifact_non_empty(ctx)
        assert finding.status == EvidenceGateStatus.FAILED

    def test_passes_on_non_empty_files(self):
        ctx = GateEvaluationContext(
            required_artifacts=("report.md",),
            available_file_sizes={"report.md": 500},
        )
        finding = _gate_artifact_non_empty(ctx)
        assert finding.status == EvidenceGateStatus.PASSED


class TestClaimHasEvidenceGate:
    def test_warns_when_no_evidence(self):
        ctx = GateEvaluationContext()
        finding = _gate_claim_has_evidence(ctx)
        assert finding.status == EvidenceGateStatus.WARNING

    def test_passes_with_valid_evidence(self):
        item = EvidenceItem(
            source_path="test.py",
            claim="All tests pass",
            evidence_type=EvidenceType.TEST_RESULT,
        )
        ctx = GateEvaluationContext(evidence_items=(item,))
        finding = _gate_claim_has_evidence(ctx)
        assert finding.status == EvidenceGateStatus.PASSED

    def test_fails_with_invalid_evidence(self):
        item = EvidenceItem(
            source_path="", claim="", evidence_type=EvidenceType.TEST_RESULT
        )
        ctx = GateEvaluationContext(evidence_items=(item,))
        finding = _gate_claim_has_evidence(ctx)
        assert finding.status == EvidenceGateStatus.FAILED


class TestImplementationFileGate:
    def test_na_when_no_doer_role(self):
        ctx = GateEvaluationContext(active_task_roles=("verifier",))
        finding = _gate_implementation_file(ctx)
        assert finding.status == EvidenceGateStatus.NOT_APPLICABLE

    def test_warns_when_doer_has_no_files(self):
        ctx = GateEvaluationContext(active_task_roles=("doer",))
        finding = _gate_implementation_file(ctx)
        assert finding.status == EvidenceGateStatus.WARNING

    def test_passes_when_doer_has_files(self):
        ctx = GateEvaluationContext(
            active_task_roles=("doer",),
            available_paths=("index.html", "app.js"),
        )
        finding = _gate_implementation_file(ctx)
        assert finding.status == EvidenceGateStatus.PASSED


class TestVerificationCommandGate:
    def test_na_when_no_verifier(self):
        ctx = GateEvaluationContext(active_task_roles=("doer",))
        finding = _gate_verification_command(ctx)
        assert finding.status == EvidenceGateStatus.NOT_APPLICABLE

    def test_fails_when_no_commands(self):
        ctx = GateEvaluationContext(active_task_roles=("verifier",))
        finding = _gate_verification_command(ctx)
        assert finding.status == EvidenceGateStatus.FAILED

    def test_fails_when_echo_only(self):
        ctx = GateEvaluationContext(
            active_task_roles=("verifier",),
            verification_commands=(
                'echo "Verified: all good"',
                'echo "Verified: tests pass"',
            ),
        )
        finding = _gate_verification_command(ctx)
        assert finding.status == EvidenceGateStatus.FAILED

    def test_passes_with_real_commands(self):
        ctx = GateEvaluationContext(
            active_task_roles=("verifier",),
            verification_commands=(
                "uv run pytest tests/core/ralph -q",
                "uv run ruff check core/ralph",
            ),
        )
        finding = _gate_verification_command(ctx)
        assert finding.status == EvidenceGateStatus.PASSED

    def test_warns_when_mixed(self):
        ctx = GateEvaluationContext(
            active_task_roles=("verifier",),
            verification_commands=(
                'echo "Verified: all good"',
                "uv run pytest tests/core/ralph -q",
            ),
        )
        finding = _gate_verification_command(ctx)
        assert finding.status == EvidenceGateStatus.WARNING


class TestQABehaviorGate:
    def test_na_when_no_qa(self):
        ctx = GateEvaluationContext()
        finding = _gate_qa_behavior(ctx)
        assert finding.status == EvidenceGateStatus.NOT_APPLICABLE

    def test_warns_when_no_behavior_checks(self):
        ctx = GateEvaluationContext(
            active_agent_ids=("qa_engineer",),
            acceptance_criteria=("Files should exist in workspace.",),
            verification_commands=("test -f index.html",),
        )
        finding = _gate_qa_behavior(ctx)
        assert finding.status == EvidenceGateStatus.WARNING

    def test_passes_with_edge_case_checks(self):
        ctx = GateEvaluationContext(
            active_agent_ids=("qa_engineer",),
            acceptance_criteria=(
                "All edge cases for input validation must be covered.",
                "Regression tests must pass.",
            ),
            verification_commands=("uv run pytest -k edge",),
        )
        finding = _gate_qa_behavior(ctx)
        assert finding.status == EvidenceGateStatus.PASSED


class TestSecurityEvidenceGate:
    def test_na_when_no_security_agents(self):
        ctx = GateEvaluationContext()
        finding = _gate_security_evidence(ctx)
        assert finding.status == EvidenceGateStatus.NOT_APPLICABLE

    def test_fails_when_no_security_checks(self):
        ctx = GateEvaluationContext(
            active_agent_ids=("security_engineer",),
            strict_mode=False,
        )
        finding = _gate_security_evidence(ctx)
        assert finding.status == EvidenceGateStatus.FAILED

    def test_blocks_in_strict_mode(self):
        ctx = GateEvaluationContext(
            active_agent_ids=("security_engineer",),
            strict_mode=True,
        )
        finding = _gate_security_evidence(ctx)
        assert finding.status == EvidenceGateStatus.BLOCKED

    def test_passes_with_threat_model_and_security_commands(self):
        ctx = GateEvaluationContext(
            active_agent_ids=("security_engineer",),
            required_artifacts=("security_requirements", "threat_model"),
            verification_commands=("uv run bandit -r .", "grep -r vulnerability ."),
        )
        finding = _gate_security_evidence(ctx)
        assert finding.status == EvidenceGateStatus.PASSED

    def test_warns_with_threat_model_but_no_commands(self):
        """Having security artifacts without explicit verification commands warns."""
        ctx = GateEvaluationContext(
            active_agent_ids=("security_engineer",),
            required_artifacts=("security_requirements", "threat_model"),
        )
        finding = _gate_security_evidence(ctx)
        assert finding.status == EvidenceGateStatus.WARNING

    def test_passes_with_security_keywords_in_ac(self):
        ctx = GateEvaluationContext(
            active_agent_ids=("security_engineer",),
            acceptance_criteria=(
                "Threat model must cover OWASP Top 10.",
                "Vulnerability scan must return no critical CVEs.",
            ),
        )
        finding = _gate_security_evidence(ctx)
        assert finding.status == EvidenceGateStatus.PASSED


class TestVisualEvidenceGate:
    def test_na_when_no_visual_agents(self):
        ctx = GateEvaluationContext()
        finding = _gate_visual_evidence(ctx)
        assert finding.status == EvidenceGateStatus.NOT_APPLICABLE

    def test_warns_when_no_visual_checks(self):
        ctx = GateEvaluationContext(active_agent_ids=("ui_designer",))
        finding = _gate_visual_evidence(ctx)
        assert finding.status == EvidenceGateStatus.WARNING  # warn, not block

    def test_passes_with_visual_artifacts(self):
        ctx = GateEvaluationContext(
            active_agent_ids=("ui_designer", "visual_qa_engineer"),
            required_artifacts=("visual_QA_report", "design_system"),
        )
        finding = _gate_visual_evidence(ctx)
        assert finding.status == EvidenceGateStatus.PASSED


class TestResearchReferenceGate:
    def test_na_when_no_research_agents(self):
        ctx = GateEvaluationContext()
        finding = _gate_research_reference(ctx)
        assert finding.status == EvidenceGateStatus.NOT_APPLICABLE

    def test_warns_when_no_references(self):
        ctx = GateEvaluationContext(active_agent_ids=("software_architect",))
        finding = _gate_research_reference(ctx)
        assert finding.status == EvidenceGateStatus.WARNING

    def test_passes_with_references(self):
        ctx = GateEvaluationContext(
            active_agent_ids=("software_architect",),
            research_references=("facebook-react",),
        )
        finding = _gate_research_reference(ctx)
        assert finding.status == EvidenceGateStatus.PASSED


class TestFinalArbiterGate:
    def test_na_when_no_final_arbiter(self):
        ctx = GateEvaluationContext()
        finding = _gate_final_arbiter(ctx)
        assert finding.status == EvidenceGateStatus.NOT_APPLICABLE

    def test_fails_without_evidence(self):
        ctx = GateEvaluationContext(
            active_agent_ids=("final_arbiter",),
            strict_mode=False,
        )
        finding = _gate_final_arbiter(ctx)
        assert finding.status == EvidenceGateStatus.FAILED

    def test_blocks_in_strict_mode(self):
        ctx = GateEvaluationContext(
            active_agent_ids=("final_arbiter",),
            strict_mode=True,
        )
        finding = _gate_final_arbiter(ctx)
        assert finding.status == EvidenceGateStatus.BLOCKED

    def test_passes_with_evidence_from_core_agents(self):
        items = (
            EvidenceItem(
                source_path="qa_output.json",
                claim="All tests pass",
                evidence_type=EvidenceType.TEST_RESULT,
                agent_source="qa_engineer",
            ),
            EvidenceItem(
                source_path="security_review.md",
                claim="No critical vulns",
                evidence_type=EvidenceType.AGENT_OUTPUT,
                agent_source="security_engineer",
            ),
            EvidenceItem(
                source_path="perf_report.json",
                claim="Response time < 200ms",
                evidence_type=EvidenceType.TEST_RESULT,
                agent_source="performance_tester",
            ),
        )
        ctx = GateEvaluationContext(
            active_agent_ids=("final_arbiter",),
            evidence_items=items,
            required_artifacts=(
                "QA_report",
                "security_review",
                "performance_report",
                "release_readiness_report",
                "deployment_plan",
            ),
        )
        finding = _gate_final_arbiter(ctx)
        assert finding.status == EvidenceGateStatus.PASSED


class TestNoFakeEchoGate:
    def test_na_when_no_commands(self):
        ctx = GateEvaluationContext()
        finding = _gate_no_fake_echo(ctx)
        assert finding.status == EvidenceGateStatus.NOT_APPLICABLE

    def test_fails_echo_verified(self):
        ctx = GateEvaluationContext(
            verification_commands=('echo "Verified: all good"',),
        )
        finding = _gate_no_fake_echo(ctx)
        assert finding.status == EvidenceGateStatus.FAILED

    def test_passes_with_real_commands(self):
        ctx = GateEvaluationContext(
            verification_commands=("uv run pytest tests/ -q",),
        )
        finding = _gate_no_fake_echo(ctx)
        assert finding.status == EvidenceGateStatus.PASSED


class TestRuntimeArtifactExclusion:
    def test_na_when_no_staged_paths(self):
        ctx = GateEvaluationContext()
        finding = _gate_runtime_artifact_exclusion(ctx)
        assert finding.status == EvidenceGateStatus.NOT_APPLICABLE

    def test_passes_with_clean_staging(self):
        ctx = GateEvaluationContext(
            staged_paths=("core/ralph/cli.py", "tests/test_foo.py")
        )
        finding = _gate_runtime_artifact_exclusion(ctx)
        assert finding.status == EvidenceGateStatus.PASSED

    def test_blocks_on_fcc_staged(self):
        ctx = GateEvaluationContext(
            staged_paths=(".fcc/some_config.json", "core/ralph/cli.py")
        )
        finding = _gate_runtime_artifact_exclusion(ctx)
        assert finding.status == EvidenceGateStatus.BLOCKED

    def test_blocks_on_fcc_ralph_staged(self):
        ctx = GateEvaluationContext(staged_paths=(".fcc-ralph/runs/test.json",))
        finding = _gate_runtime_artifact_exclusion(ctx)
        assert finding.status == EvidenceGateStatus.BLOCKED

    def test_blocks_on_claude_staged(self):
        ctx = GateEvaluationContext(staged_paths=(".claude/memory/test.md",))
        finding = _gate_runtime_artifact_exclusion(ctx)
        assert finding.status == EvidenceGateStatus.BLOCKED

    def test_blocks_on_env_staged(self):
        ctx = GateEvaluationContext(staged_paths=("config/.env.production",))
        finding = _gate_runtime_artifact_exclusion(ctx)
        assert finding.status == EvidenceGateStatus.BLOCKED

    def test_blocks_on_logs_staged(self):
        ctx = GateEvaluationContext(staged_paths=("logs/error.log",))
        finding = _gate_runtime_artifact_exclusion(ctx)
        assert finding.status == EvidenceGateStatus.BLOCKED

    def test_blocks_on_raw_research_repos(self):
        ctx = GateEvaluationContext(
            staged_paths=("raw_research_repos/facebook-react/package.json",),
        )
        finding = _gate_runtime_artifact_exclusion(ctx)
        assert finding.status == EvidenceGateStatus.BLOCKED


class TestNoNetworkOrLLM:
    """Verify no network/LLM calls in evidence gates module."""

    def test_no_network_imports(self):
        from core.ralph.agent_council import evidence_gates

        source = evidence_gates.__file__
        if source:
            with open(str(source)) as f:
                content = f.read()
            assert "anthropic" not in content
            assert "requests" not in content
            assert "urllib" not in content
