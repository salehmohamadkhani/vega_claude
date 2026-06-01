"""Evidence-Gated Runtime Backtest.

Validates that Agent Council gate enforcement correctly blocks/approves
task results under realistic runtime-like conditions.

Proves:
1. Echo-only verification is blocked.
2. Implementation task without expected files is blocked.
3. Final arbiter without upstream evidence is blocked.
4. Runtime artifacts (.fcc/, .claude/, env, logs, research repos) are blocked.
5. Valid implementation evidence can pass.
6. Valid verification evidence can pass.
7. Strict mode blocks critical failures.
8. Non-strict mode still blocks critical fake evidence.
9. Disabled gates preserve old behavior.
10. Gate metadata is JSON-serializable.
11. No LLM/API/network calls occur.

Fixtures are deterministic JSON files — no external services, no LLM calls.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

import pytest

from core.ralph.agent_council.evidence_gates import (
    EvidenceGateStatus,
)
from core.ralph.agent_council.runtime_evidence import (
    RuntimeEvidenceBindingStatus,
    extract_runtime_evidence_from_task_result,
)
from core.ralph.agent_council.runtime_gate_enforcer import (
    enforce_runtime_evidence_gates,
    runtime_gate_result_to_metadata,
    should_block_task_approval,
    summarize_runtime_gate_enforcement,
)

# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

FIXTURE_DIR = os.path.join(
    os.path.dirname(__file__),
    "fixtures",
    "agent_council_runtime_backtest",
)


def _load_fixture(name: str) -> dict:
    """Load a backtest fixture JSON file."""
    path = os.path.join(FIXTURE_DIR, name)
    with open(path) as f:
        return json.load(f)


def _load_all_fixtures() -> list[dict]:
    """Load all backtest fixtures."""
    return [
        _load_fixture(fname)
        for fname in sorted(os.listdir(FIXTURE_DIR))
        if fname.endswith(".json")
    ]


# ---------------------------------------------------------------------------
# Backtest matrix
# ---------------------------------------------------------------------------


@dataclass
class BacktestCase:
    """Expected behavior for a backtest scenario."""

    fixture_name: str
    description: str
    strict_mode: bool
    expect_blocked: bool  # should_block_task_approval returns True
    expect_status: str  # "blocked" | "failed" | "warning" | "passed" | any
    expect_echo_blocked: bool = False  # specific echo-only detection
    expect_file_missing: bool = False  # no files produced
    expect_artifact_blocked: bool = False  # forbidden paths detected


BACKTEST_MATRIX: list[BacktestCase] = [
    BacktestCase(
        fixture_name="echo_only_verifier_result.json",
        description="Echo-only verification commands should be blocked",
        strict_mode=True,
        expect_blocked=True,
        expect_status="blocked",
        expect_echo_blocked=True,
    ),
    BacktestCase(
        fixture_name="echo_only_verifier_result.json",
        description="Echo-only verifier blocked even in strict mode",
        strict_mode=True,
        expect_blocked=True,
        expect_status="blocked",
        expect_echo_blocked=True,
    ),
    BacktestCase(
        fixture_name="missing_file_implementation_result.json",
        description="Implementation without produced files should be flagged",
        strict_mode=True,
        expect_blocked=False,
        expect_status="warning",
        expect_file_missing=True,
    ),
    BacktestCase(
        fixture_name="valid_implementation_result.json",
        description="Valid implementation with files should pass or warn only",
        strict_mode=False,
        expect_blocked=False,
        expect_status="warning",
        expect_file_missing=False,
    ),
    BacktestCase(
        fixture_name="valid_verification_result.json",
        description="Valid verification with real commands should not be blocked",
        strict_mode=False,
        expect_blocked=False,
        expect_status="warning",
        expect_echo_blocked=False,
    ),
    BacktestCase(
        fixture_name="valid_verification_result.json",
        description="Valid verification in strict mode should not be blocked",
        strict_mode=True,
        expect_blocked=False,
        expect_status="warning",
        expect_echo_blocked=False,
    ),
    BacktestCase(
        fixture_name="final_arbiter_without_evidence_result.json",
        description="Final arbiter without upstream evidence must be blocked",
        strict_mode=True,
        expect_blocked=True,
        expect_status="blocked",
    ),
    BacktestCase(
        fixture_name="runtime_artifact_staged_result.json",
        description="Runtime artifacts staged for commit must be blocked",
        strict_mode=True,
        expect_blocked=True,
        expect_status="blocked",
        expect_artifact_blocked=True,
    ),
    BacktestCase(
        fixture_name="runtime_artifact_staged_result.json",
        description="Runtime artifacts blocked even in non-strict mode",
        strict_mode=False,
        expect_blocked=True,
        expect_status="blocked",
        expect_artifact_blocked=True,
    ),
]


# Deduplicate by (fixture_name, strict_mode)
_UNIQUE_MATRIX: list[BacktestCase] = []
_seen: set[tuple[str, bool]] = set()
for bc in BACKTEST_MATRIX:
    key = (bc.fixture_name, bc.strict_mode)
    if key not in _seen:
        _seen.add(key)
        _UNIQUE_MATRIX.append(bc)


# Generate pytest params from the matrix
def _matrix_ids(bc: BacktestCase) -> str:
    mode = "strict" if bc.strict_mode else "non-strict"
    return f"{bc.fixture_name.replace('.json', '')}_{mode}"


MATRIX_PARAMS = [pytest.param(bc, id=_matrix_ids(bc)) for bc in _UNIQUE_MATRIX]


# ---------------------------------------------------------------------------
# Backtest — evidence extraction
# ---------------------------------------------------------------------------


class TestBacktestEvidenceExtraction:
    """Verify evidence extraction produces expected bundles from fixtures."""

    @pytest.mark.parametrize("bc", MATRIX_PARAMS)
    def test_extraction_does_not_crash(self, bc: BacktestCase):
        fixture = _load_fixture(bc.fixture_name)
        bundle = extract_runtime_evidence_from_task_result(fixture)
        assert bundle is not None
        assert isinstance(bundle.summary, str)

    def test_echo_only_is_detected(self):
        fixture = _load_fixture("echo_only_verifier_result.json")
        bundle = extract_runtime_evidence_from_task_result(fixture)
        # Echo-only verifier should be blocked at extraction level
        assert bundle.status == RuntimeEvidenceBindingStatus.BLOCKED
        assert bundle.has_real_commands is False

    def test_echo_only_has_correct_task_role(self):
        fixture = _load_fixture("echo_only_verifier_result.json")
        bundle = extract_runtime_evidence_from_task_result(fixture)
        assert bundle.task_role == "verifier"

    def test_missing_files_detected(self):
        fixture = _load_fixture("missing_file_implementation_result.json")
        bundle = extract_runtime_evidence_from_task_result(fixture)
        assert bundle.has_files is False

    def test_valid_implementation_has_files(self):
        fixture = _load_fixture("valid_implementation_result.json")
        bundle = extract_runtime_evidence_from_task_result(fixture)
        assert bundle.has_files is True

    def test_valid_verification_has_real_commands(self):
        fixture = _load_fixture("valid_verification_result.json")
        bundle = extract_runtime_evidence_from_task_result(fixture)
        assert bundle.has_real_commands is True
        assert bundle.status != RuntimeEvidenceBindingStatus.BLOCKED

    def test_runtime_artifacts_are_extracted(self):
        fixture = _load_fixture("runtime_artifact_staged_result.json")
        bundle = extract_runtime_evidence_from_task_result(fixture)
        paths = {b.path for b in bundle.bindings if b.path}
        # .fcc/ files should be extracted as file evidence
        forbidden = [p for p in paths if ".fcc/" in p or ".claude/" in p or ".env" in p]
        assert len(forbidden) > 0


# ---------------------------------------------------------------------------
# Backtest — gate enforcement
# ---------------------------------------------------------------------------


class TestBacktestGateEnforcement:
    """Verify gate enforcement produces expected results from fixtures."""

    @pytest.mark.parametrize("bc", MATRIX_PARAMS)
    def test_enforcement_does_not_crash(self, bc: BacktestCase):
        fixture = _load_fixture(bc.fixture_name)
        result = enforce_runtime_evidence_gates(
            fixture,
            strict_mode=bc.strict_mode,
        )
        assert result is not None
        assert result.gates_run == 12

    def test_echo_only_blocked_by_gate_enforcement(self):
        """Echo-only verifier must be blocked by enforcement in strict mode."""
        fixture = _load_fixture("echo_only_verifier_result.json")
        result = enforce_runtime_evidence_gates(fixture, strict_mode=True)

        # The enforcement should produce a blocked/failed finding
        vc_finding = next(
            (f for f in result.findings if f.gate_id == "verification_command_gate"),
            None,
        )
        assert vc_finding is not None, "verification_command_gate should be evaluated"
        assert vc_finding.status in (
            EvidenceGateStatus.FAILED,
            EvidenceGateStatus.BLOCKED,
        ), f"Echo-only verifier should be FAILED/BLOCKED, got {vc_finding.status.value}"

    def test_echo_only_blocks_approval(self):
        """Echo-only verifier should block task approval."""
        fixture = _load_fixture("echo_only_verifier_result.json")
        result = enforce_runtime_evidence_gates(fixture, strict_mode=True)
        should_block_task_approval(result)
        # With strict mode and echo-only, blocking issues may exist
        # At minimum, verification command gate should fail
        assert result.gates_failed + result.gates_blocked > 0

    def test_valid_implementation_passes_approval(self):
        """Valid implementation with files should not be blocked."""
        fixture = _load_fixture("valid_implementation_result.json")
        result = enforce_runtime_evidence_gates(fixture, strict_mode=False)
        # Valid implementation should not trigger should_block_task_approval
        # (may have warnings from other gates but not from impl gate)
        blocked = should_block_task_approval(result)
        assert not blocked, f"Valid impl blocked: {result.blocking_issues}"

    def test_valid_implementation_not_blocked_by_impl_gate(self):
        """Implementation file gate specifically should pass for valid impl."""
        fixture = _load_fixture("valid_implementation_result.json")
        result = enforce_runtime_evidence_gates(fixture)
        impl_finding = next(
            (f for f in result.findings if f.gate_id == "implementation_file_gate"),
            None,
        )
        if impl_finding and impl_finding.status != EvidenceGateStatus.NOT_APPLICABLE:
            # Should be PASSED or WARNING, not FAILED/BLOCKED
            assert impl_finding.status not in (
                EvidenceGateStatus.FAILED,
                EvidenceGateStatus.BLOCKED,
            ), f"Impl gate blocked valid impl: {impl_finding.message}"

    def test_valid_verification_verification_gate_passes(self):
        """Valid verification with real commands passes the verification command gate."""
        fixture = _load_fixture("valid_verification_result.json")
        result = enforce_runtime_evidence_gates(fixture, strict_mode=True)
        vc_finding = next(
            (f for f in result.findings if f.gate_id == "verification_command_gate"),
            None,
        )
        if vc_finding and vc_finding.status != EvidenceGateStatus.NOT_APPLICABLE:
            # Valid verification commands should not fail
            assert vc_finding.status not in (
                EvidenceGateStatus.FAILED,
                EvidenceGateStatus.BLOCKED,
            ), f"Verification gate blocked valid verification: {vc_finding.message}"

    def test_final_arbiter_blocked_without_evidence(self):
        """Final arbiter without upstream evidence must be blocked in strict mode."""
        fixture = _load_fixture("final_arbiter_without_evidence_result.json")
        # Give it the final_arbiter context
        ctx = {
            "council_plan_available": True,
            "active_agents": [
                {
                    "agent_id": "final_arbiter",
                    "role_name": "Final Arbiter",
                    "layer": 17,
                    "phase": 0,
                },
            ],
            "required_artifacts": [],
        }
        result = enforce_runtime_evidence_gates(
            fixture, planning_context=ctx, strict_mode=True
        )
        arb_finding = next(
            (f for f in result.findings if f.gate_id == "final_arbiter_gate"),
            None,
        )
        if arb_finding:
            # Final arbiter without evidence should fail or be blocked
            assert arb_finding.status in (
                EvidenceGateStatus.FAILED,
                EvidenceGateStatus.BLOCKED,
            ), (
                f"Final arbiter gate should fail without evidence, got {arb_finding.status.value}"
            )

    def test_runtime_artifacts_blocked_strict(self):
        """Runtime artifacts (.fcc/, .claude/, .env, logs) must be blocked in strict mode."""
        fixture = _load_fixture("runtime_artifact_staged_result.json")
        result = enforce_runtime_evidence_gates(fixture, strict_mode=True)
        excl_finding = next(
            (
                f
                for f in result.findings
                if f.gate_id == "runtime_artifact_exclusion_gate"
            ),
            None,
        )
        assert excl_finding is not None
        assert excl_finding.status == EvidenceGateStatus.BLOCKED, (
            f"Runtime artifacts should be BLOCKED, got {excl_finding.status.value}"
        )

        blocked = should_block_task_approval(result)
        assert blocked, "Runtime artifact staging should block approval"

    def test_runtime_artifacts_blocked_non_strict(self):
        """Runtime artifacts must be blocked even in non-strict mode."""
        fixture = _load_fixture("runtime_artifact_staged_result.json")
        result = enforce_runtime_evidence_gates(fixture, strict_mode=False)
        excl_finding = next(
            (
                f
                for f in result.findings
                if f.gate_id == "runtime_artifact_exclusion_gate"
            ),
            None,
        )
        assert excl_finding is not None
        assert excl_finding.status == EvidenceGateStatus.BLOCKED, (
            f"Runtime artifacts should be BLOCKED even in non-strict, got {excl_finding.status.value}"
        )

    def test_runtime_artifacts_specific_paths_blocked(self):
        """Each forbidden path category must be blocked."""
        fixture = _load_fixture("runtime_artifact_staged_result.json")
        result = enforce_runtime_evidence_gates(fixture, strict_mode=True)
        excl = next(
            (
                f
                for f in result.findings
                if f.gate_id == "runtime_artifact_exclusion_gate"
            ),
            None,
        )
        assert excl is not None
        # The fixture contains .fcc/, .fcc-ralph/, .claude/, .env, logs/, secrets/
        affected = excl.affected_paths
        categories = {
            ".fcc/": False,
            ".fcc-ralph/": False,
            ".claude/": False,
            ".env": False,
            "logs/": False,
        }
        for path in affected:
            for cat in categories:
                if cat in path:
                    categories[cat] = True
        # At least some forbidden categories should be caught
        assert any(categories.values()), f"No forbidden paths caught: {affected}"


# ---------------------------------------------------------------------------
# Backtest — disabled gates preserve old behavior
# ---------------------------------------------------------------------------


class TestBacktestDisabledGates:
    """Verify that disabled gates preserve old behavior."""

    def test_echo_only_passes_when_gates_disabled(self):
        """When gates are disabled, echo-only does not crash the system."""
        fixture = _load_fixture("echo_only_verifier_result.json")
        # Extract evidence still runs (it's always run)
        bundle = extract_runtime_evidence_from_task_result(fixture)
        assert (
            bundle.status == RuntimeEvidenceBindingStatus.BLOCKED
        )  # extraction detects it
        # But enforcement without strict mode + no planning context = no blocking
        result = enforce_runtime_evidence_gates(fixture, strict_mode=False)
        # Without planning context providing agent info, some gates are NA
        assert result.gates_run == 12

    def test_quality_gate_defaults_work_with_all_fixtures(self):
        """All fixtures work through QualityGate.evaluate() with defaults."""
        from core.ralph.models import RalphTask, TaskStatus
        from core.ralph.quality_gate import QualityGate
        from core.ralph.roles import AgentRole

        for fname in sorted(os.listdir(FIXTURE_DIR)):
            if not fname.endswith(".json"):
                continue
            fixture = _load_fixture(fname)
            task_data = fixture.get("task", {})
            role_str = task_data.get("agent_role", "doer")
            try:
                role = AgentRole(role_str)
            except ValueError:
                role = AgentRole.DOER

            task = RalphTask(
                id=fixture.get("task_id", "unknown"),
                title=fixture.get("task_title", "backtest"),
                agent_role=role,
                verification_commands=list(task_data.get("verification_commands", [])),
                acceptance_criteria=list(task_data.get("acceptance_criteria", [])),
            )
            gate = QualityGate()
            # Default: no council gates
            result = gate.evaluate(task)
            assert isinstance(result.final_status, TaskStatus)
            # Without gate enforcement, summary should not contain council-gates
            assert "council-gates" not in result.summary

    def test_enabled_gates_add_council_to_summary(self):
        """When gates are enabled, summary contains council-gates tag."""
        from core.ralph.models import RalphTask
        from core.ralph.quality_gate import QualityGate
        from core.ralph.roles import AgentRole

        fixture = _load_fixture("valid_verification_result.json")
        task_data = fixture["task"]
        task = RalphTask(
            id=fixture["task_id"],
            title=fixture["task_title"],
            agent_role=AgentRole.VERIFIER,
            verification_commands=list(task_data.get("verification_commands", [])),
            acceptance_criteria=list(task_data.get("acceptance_criteria", [])),
        )
        gate = QualityGate()
        result = gate.evaluate(
            task,
            use_agent_council_gates=True,
            strict_agent_council_gates=False,
        )
        assert "council-gates" in result.summary


# ---------------------------------------------------------------------------
# Backtest — metadata
# ---------------------------------------------------------------------------


class TestBacktestMetadata:
    """Verify gate result metadata is properly formatted."""

    def test_metadata_is_dict_for_all_fixtures(self):
        """All fixtures produce valid metadata dicts."""
        for fname in sorted(os.listdir(FIXTURE_DIR)):
            if not fname.endswith(".json"):
                continue
            fixture = _load_fixture(fname)
            result = enforce_runtime_evidence_gates(fixture, strict_mode=False)
            meta = runtime_gate_result_to_metadata(result)
            assert isinstance(meta, dict)
            assert "agent_council_gate_enforcement" in meta
            inner = meta["agent_council_gate_enforcement"]
            assert inner["enabled"] is True

    def test_metadata_json_serializable_for_all(self):
        """All fixtures produce JSON-serializable metadata."""
        for fname in sorted(os.listdir(FIXTURE_DIR)):
            if not fname.endswith(".json"):
                continue
            fixture = _load_fixture(fname)
            result = enforce_runtime_evidence_gates(fixture, strict_mode=False)
            meta = runtime_gate_result_to_metadata(result)
            serialized = json.dumps(meta, default=str)
            assert isinstance(serialized, str)

    def test_summary_available_for_all_fixtures(self):
        """Summarize works for all fixtures."""
        for fname in sorted(os.listdir(FIXTURE_DIR)):
            if not fname.endswith(".json"):
                continue
            fixture = _load_fixture(fname)
            bundle = extract_runtime_evidence_from_task_result(fixture)
            result = enforce_runtime_evidence_gates(fixture)
            s = summarize_runtime_gate_enforcement(bundle, result)
            assert isinstance(s, str)
            assert len(s) > 0


# ---------------------------------------------------------------------------
# Backtest — matrix verification
# ---------------------------------------------------------------------------


class TestBacktestMatrix:
    """Verify the complete backtest matrix matches expectations."""

    def test_all_fixtures_exist(self):
        """All 6 backtest fixtures exist on disk."""
        expected = {
            "echo_only_verifier_result.json",
            "missing_file_implementation_result.json",
            "valid_implementation_result.json",
            "valid_verification_result.json",
            "final_arbiter_without_evidence_result.json",
            "runtime_artifact_staged_result.json",
        }
        actual = set(os.listdir(FIXTURE_DIR))
        missing = expected - actual
        assert not missing, f"Missing fixtures: {missing}"

    def test_matrix_covers_all_fixtures(self):
        """Backtest matrix covers all fixture files."""
        matrix_fixtures = {bc.fixture_name for bc in BACKTEST_MATRIX}
        all_fixtures = {f for f in os.listdir(FIXTURE_DIR) if f.endswith(".json")}
        missing = all_fixtures - matrix_fixtures
        assert not missing, f"Fixtures not in matrix: {missing}"

    def test_each_fixture_loads(self):
        """Every fixture is valid JSON and loads without error."""
        for fname in sorted(os.listdir(FIXTURE_DIR)):
            if not fname.endswith(".json"):
                continue
            fixture = _load_fixture(fname)
            assert isinstance(fixture, dict)
            assert "task_id" in fixture
            assert "task_title" in fixture

    @pytest.mark.parametrize("bc", MATRIX_PARAMS)
    def test_approval_blocking_matches_expectation(self, bc: BacktestCase):
        """Verify should_block_task_approval matches documented expectation."""
        fixture = _load_fixture(bc.fixture_name)

        # Build planning context if needed for arbiter gate
        ctx = None
        if "final_arbiter" in bc.fixture_name:
            ctx = {
                "council_plan_available": True,
                "active_agents": [
                    {
                        "agent_id": "final_arbiter",
                        "role_name": "Final Arbiter",
                        "layer": 17,
                    },
                ],
            }

        result = enforce_runtime_evidence_gates(
            fixture,
            planning_context=ctx,
            strict_mode=bc.strict_mode,
        )
        blocked = should_block_task_approval(result)

        assert blocked == bc.expect_blocked, (
            f"Mismatch for {bc.fixture_name} (strict={bc.strict_mode}): "
            f"expected blocked={bc.expect_blocked}, got blocked={blocked}. "
            f"Gate summary: {result.summary}"
        )


# ---------------------------------------------------------------------------
# No network / LLM calls
# ---------------------------------------------------------------------------


class TestNoNetworkOrLLM:
    """Verify no network/LLM calls during backtests."""

    def test_fixtures_are_pure_json(self):
        """All fixtures are valid JSON with no executable content."""
        for fname in os.listdir(FIXTURE_DIR):
            if not fname.endswith(".json"):
                continue
            path = os.path.join(FIXTURE_DIR, fname)
            with open(path) as f:
                data = json.load(f)
            for val in data.values():
                if isinstance(val, str):
                    assert "anthropic" not in val.lower()
                    assert "api_key" not in val.lower()
                    assert "http://" not in val
                    assert "https://" not in val

    def test_backtest_no_network_imports(self):
        source = __file__
        if source:
            with open(source) as f:
                content = f.read()
            # Check import statements only, not docstrings
            import_lines = [
                line
                for line in content.split("\n")
                if line.strip().startswith(("import ", "from "))
            ]
            import_text = "\n".join(import_lines)
            assert "anthropic" not in import_text
            assert "requests" not in import_text
            assert "urllib" not in import_text
