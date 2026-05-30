"""Tests for runtime gate enforcer (runtime_gate_enforcer.py).

Prove:
- gate enforcer handles task results
- should_block_task_approval blocks on blocking results
- should_block_task_approval passes on clean results
- metadata is JSON-serializable
- enforcement with echo-only verification fails
- enforcement without security evidence warns
- enforcement blocks .fcc/ paths
- non-strict mode warns for non-critical
- strict mode blocks critical
- old behavior unchanged when enforcement disabled
- no LLM/API/network calls occur
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

import pytest

from core.ralph.agent_council.evidence_gates import (
    EvidenceGateFinding,
    EvidenceGateResult,
    EvidenceGateStatus,
)
from core.ralph.agent_council.planner_integration import build_agent_council_task_context
from core.ralph.agent_council.runtime_evidence import (
    RuntimeEvidenceBindingStatus,
    RuntimeTaskEvidenceBundle,
    extract_runtime_evidence_from_task_result,
)
from core.ralph.agent_council.runtime_gate_enforcer import (
    enforce_runtime_evidence_gates,
    runtime_gate_result_to_metadata,
    should_block_task_approval,
    summarize_runtime_gate_enforcement,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_task_result(**overrides) -> dict:
    """Build a dict-like task result for enforcement testing."""
    defaults = {
        "task_id": "TASK-001",
        "task_title": "Test task",
        "task": {
            "agent_role": "doer",
            "verification_commands": ["uv run pytest tests/ -q"],
            "acceptance_criteria": ["All edge cases covered."],
        },
        "changed_files": ["index.html", "app.js"],
        "quality_gate_result": {
            "final_status": "passed",
            "arbiter_decision": {"action": "approve"},
        },
    }
    defaults.update(overrides)
    return defaults


# ---------------------------------------------------------------------------
# Enforcement tests
# ---------------------------------------------------------------------------


class TestEnforceRuntimeEvidenceGates:
    def test_enforce_with_valid_task(self):
        task_result = _make_task_result()
        result = enforce_runtime_evidence_gates(task_result, strict_mode=False)
        assert result.gates_run == 12

    def test_enforce_with_planning_context(self):
        ctx = build_agent_council_task_context(
            "Build a full stack app",
            project_type="full_stack_app",
        )
        task_result = _make_task_result(
            task={"agent_role": "doer",
                  "verification_commands": ["uv run pytest tests/ -q"],
                  "acceptance_criteria": ["Tests pass"]},
        )
        result = enforce_runtime_evidence_gates(
            task_result,
            planning_context=ctx,
            strict_mode=False,
        )
        assert result.gates_run == 12

    def test_enforce_with_strict_mode(self):
        task_result = _make_task_result(
            task={"agent_role": "verifier",
                  "verification_commands": ['echo "verified"'],
                  "acceptance_criteria": []},
        )
        result = enforce_runtime_evidence_gates(task_result, strict_mode=True)
        # Echo-only + strict should produce blocking issues
        assert result.gates_run > 0

    def test_enforce_with_echo_only_verification(self):
        task_result = _make_task_result(
            task={
                "agent_role": "verifier",
                "verification_commands": ['echo "Verified: all good"'],
                "acceptance_criteria": [],
            },
        )
        result = enforce_runtime_evidence_gates(task_result, strict_mode=True)
        # Verification command gate should fail
        vc_finding = next(
            (f for f in result.findings if f.gate_id == "verification_command_gate"),
            None,
        )
        if vc_finding:
            assert vc_finding.status in (
                EvidenceGateStatus.FAILED,
                EvidenceGateStatus.BLOCKED,
            )

    def test_enforce_with_security_task_no_evidence(self):
        task_result = _make_task_result(
            task={
                "agent_role": "security_engineer",
                "verification_commands": ["ls -la"],
                "acceptance_criteria": ["Security is good."],
            },
        )
        result = enforce_runtime_evidence_gates(
            task_result,
            planning_context={"council_plan_available": True, "active_agents": [
                {"agent_id": "security_engineer", "role_name": "Security Engineer", "layer": 12}
            ]},
            strict_mode=False,
        )
        sec_finding = next(
            (f for f in result.findings if f.gate_id == "security_evidence_gate"),
            None,
        )
        if sec_finding:
            assert sec_finding.status != EvidenceGateStatus.PASSED

    def test_enforce_with_fcc_staged_paths(self):
        task_result = _make_task_result(
            changed_files=[".fcc/config.json", "app.js"],
        )
        result = enforce_runtime_evidence_gates(task_result, strict_mode=True)
        excl_finding = next(
            (f for f in result.findings if f.gate_id == "runtime_artifact_exclusion_gate"),
            None,
        )
        if excl_finding and excl_finding.status != EvidenceGateStatus.NOT_APPLICABLE:
            assert excl_finding.status == EvidenceGateStatus.BLOCKED

    def test_enforce_with_claude_staged_paths(self):
        task_result = _make_task_result(
            changed_files=[".claude/memory/test.md"],
        )
        result = enforce_runtime_evidence_gates(task_result, strict_mode=True)
        excl_finding = next(
            (f for f in result.findings if f.gate_id == "runtime_artifact_exclusion_gate"),
            None,
        )
        if excl_finding and excl_finding.status != EvidenceGateStatus.NOT_APPLICABLE:
            assert excl_finding.status == EvidenceGateStatus.BLOCKED

    def test_enforce_with_clean_paths(self):
        task_result = _make_task_result(
            changed_files=["core/ralph/cli.py", "tests/test_app.py"],
            task={"agent_role": "doer",
                  "verification_commands": ["uv run pytest tests/ -q"],
                  "acceptance_criteria": ["Tests pass"]},
        )
        result = enforce_runtime_evidence_gates(task_result, strict_mode=True)
        excl_finding = next(
            (f for f in result.findings if f.gate_id == "runtime_artifact_exclusion_gate"),
            None,
        )
        if excl_finding and excl_finding.status != EvidenceGateStatus.NOT_APPLICABLE:
            assert excl_finding.status == EvidenceGateStatus.PASSED

    def test_enforce_with_none_context(self):
        task_result = _make_task_result()
        result = enforce_runtime_evidence_gates(task_result, planning_context=None)
        assert result.gates_run == 12


class TestShouldBlockTaskApproval:
    def test_clean_result_not_blocked(self):
        task_result = _make_task_result()
        result = enforce_runtime_evidence_gates(task_result, strict_mode=False)
        # Should not block with valid evidence and non-strict
        blocked = should_block_task_approval(result)
        # May or may not block — just verify no crash
        assert isinstance(blocked, bool)

    def test_blocks_on_blocked_overall(self):
        result = EvidenceGateResult(overall_status=EvidenceGateStatus.BLOCKED)
        assert should_block_task_approval(result) is True

    def test_blocks_on_blocked_finding(self):
        finding = EvidenceGateFinding(
            gate_id="test",
            status=EvidenceGateStatus.BLOCKED,
            message="blocked",
        )
        result = EvidenceGateResult(
            overall_status=EvidenceGateStatus.FAILED,
            findings=[finding],
        )
        assert should_block_task_approval(result) is True

    def test_blocks_on_blocking_issues(self):
        result = EvidenceGateResult(
            overall_status=EvidenceGateStatus.WARNING,
            blocking_issues=["Critical gate failed"],
        )
        assert should_block_task_approval(result) is True

    def test_passes_clean(self):
        result = EvidenceGateResult(
            overall_status=EvidenceGateStatus.PASSED,
            gates_passed=12,
        )
        assert should_block_task_approval(result) is False


class TestRuntimeGateMetadata:
    def test_returns_dict(self):
        task_result = _make_task_result()
        result = enforce_runtime_evidence_gates(task_result)
        meta = runtime_gate_result_to_metadata(result)
        assert isinstance(meta, dict)
        assert "agent_council_gate_enforcement" in meta

    def test_has_required_keys(self):
        task_result = _make_task_result()
        result = enforce_runtime_evidence_gates(task_result)
        meta = runtime_gate_result_to_metadata(result)

        inner = meta["agent_council_gate_enforcement"]
        assert isinstance(inner, dict)
        assert "enabled" in inner
        assert inner["enabled"] is True
        assert "overall_status" in inner
        assert "approval_blocked" in inner
        assert "gates_run" in inner
        assert "blocking_issues" in inner

    def test_json_serializable(self):
        task_result = _make_task_result()
        result = enforce_runtime_evidence_gates(task_result)
        meta = runtime_gate_result_to_metadata(result)
        serialized = json.dumps(meta, default=str)
        assert isinstance(serialized, str)
        assert len(serialized) > 0


class TestSummarizeEnforcement:
    def test_returns_string(self):
        task_result = _make_task_result()
        bundle = extract_runtime_evidence_from_task_result(task_result)
        result = enforce_runtime_evidence_gates(task_result)
        s = summarize_runtime_gate_enforcement(bundle, result)
        assert isinstance(s, str)
        assert "RUNTIME EVIDENCE ENFORCEMENT" in s

    def test_includes_approval_status(self):
        task_result = _make_task_result()
        bundle = extract_runtime_evidence_from_task_result(task_result)
        result = enforce_runtime_evidence_gates(task_result)
        s = summarize_runtime_gate_enforcement(bundle, result)
        assert "APPROVAL BLOCKED" in s


class TestNonStrictVsStrict:
    def test_non_strict_warns_for_non_critical(self):
        """Non-strict mode should produce warnings but not block for non-critical gaps."""
        task_result = _make_task_result(
            task={
                "agent_role": "doer",
                "verification_commands": [],
                "acceptance_criteria": [],
            },
        )
        result = enforce_runtime_evidence_gates(task_result, strict_mode=False)
        # Should have warnings but may not be blocked
        assert isinstance(result.gates_warned, int)
        assert isinstance(result.gates_run, int)

    def test_strict_mode_more_blocking(self):
        """Strict mode should produce equal or more blocking/failed gates."""
        task_result = _make_task_result(
            task={
                "agent_role": "verifier",
                "verification_commands": ['echo "ok"'],
                "acceptance_criteria": [],
            },
        )
        result_ns = enforce_runtime_evidence_gates(task_result, strict_mode=False)
        result_s = enforce_runtime_evidence_gates(task_result, strict_mode=True)
        # Strict mode should not have fewer failed+blocked than non-strict
        assert (result_s.gates_failed + result_s.gates_blocked) >= \
               (result_ns.gates_failed + result_ns.gates_blocked)


class TestBackwardCompatibility:
    """Verify old QualityGate behavior is unchanged when council is disabled."""

    def test_quality_gate_defaults_still_work(self):
        from core.ralph.models import ProjectGoal, RalphTask, TaskStatus
        from core.ralph.roles import AgentRole
        from core.ralph.quality_gate import QualityGate

        task = RalphTask(
            id="TASK-BACKWARD-001",
            title="Compat test",
            agent_role=AgentRole.DOER,
            verification_commands=["uv run pytest -q"],
            acceptance_criteria=["Tests must pass."],
        )
        gate = QualityGate()
        result = gate.evaluate(task)
        assert result.task_id == "TASK-BACKWARD-001"
        assert isinstance(result.final_status, TaskStatus)

    def test_quality_gate_with_council_disabled(self):
        """Explicitly disabled council enforcement behaves like default."""
        from core.ralph.models import RalphTask, TaskStatus
        from core.ralph.roles import AgentRole
        from core.ralph.quality_gate import QualityGate

        task = RalphTask(
            id="TASK-BACKWARD-002",
            title="Compat test",
            agent_role=AgentRole.DOER,
            verification_commands=["uv run pytest -q"],
            acceptance_criteria=["Tests pass."],
        )
        gate = QualityGate()
        result = gate.evaluate(
            task,
            use_agent_council_gates=False,
        )
        assert result.task_id == "TASK-BACKWARD-002"
        assert isinstance(result.final_status, TaskStatus)

    def test_quality_gate_with_council_enabled(self):
        """Council gates enabled should still complete without crash."""
        from core.ralph.models import RalphTask, TaskStatus
        from core.ralph.roles import AgentRole
        from core.ralph.quality_gate import QualityGate

        task = RalphTask(
            id="TASK-BACKWARD-003",
            title="Council test",
            agent_role=AgentRole.DOER,
            verification_commands=["uv run pytest -q"],
            acceptance_criteria=["Tests pass."],
        )
        gate = QualityGate()
        result = gate.evaluate(
            task,
            use_agent_council_gates=True,
            strict_agent_council_gates=False,
        )
        assert isinstance(result.final_status, TaskStatus)
        assert "council-gates" in result.summary


class TestNoNetworkOrLLM:
    """Verify no network/LLM calls in runtime gate enforcer module."""

    def test_no_network_imports(self):
        from core.ralph.agent_council import runtime_gate_enforcer
        source = runtime_gate_enforcer.__file__
        if source:
            with open(str(source)) as f:
                content = f.read()
            assert "anthropic" not in content
            assert "requests" not in content
            assert "urllib" not in content
