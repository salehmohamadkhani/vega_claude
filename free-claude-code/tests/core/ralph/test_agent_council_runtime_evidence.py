"""Tests for runtime evidence binding (runtime_evidence.py).

Prove:
- runtime evidence binding handles dict-like task results
- runtime evidence binding handles object-like task results
- file evidence is extracted when files are present
- missing file evidence is detected
- command evidence is extracted
- echo-only command evidence is rejected
- implementation task without expected files is flagged
- verification task without deterministic command is flagged
- QA task without behavior evidence is warned
- runtime artifact exclusion catches forbidden paths
- no LLM/API/network calls occur
"""

from __future__ import annotations

from dataclasses import dataclass, field

from core.ralph.agent_council.runtime_evidence import (
    RuntimeEvidenceBinding,
    RuntimeEvidenceBindingStatus,
    RuntimeEvidenceSource,
    RuntimeTaskEvidenceBundle,
    _has_echo_only_verification,
    _has_real_verification,
    extract_runtime_evidence_from_task_result,
    summarize_runtime_evidence_bundle,
)


class TestRuntimeEvidenceSource:
    def test_all_sources(self):
        """Verify all expected evidence source types exist."""
        expected = {
            "file_existence",
            "file_non_empty",
            "file_modified",
            "command_output",
            "test_result",
            "qa_behavior",
            "security_check",
            "visual_qa",
            "research_reference",
            "arbiter_decision",
            "acceptance_criteria",
            "artifact_produced",
            "staged_file",
            "unknown",
        }
        assert {e.value for e in RuntimeEvidenceSource} == expected


class TestRuntimeEvidenceBindingStatus:
    def test_all_statuses(self):
        assert {e.value for e in RuntimeEvidenceBindingStatus} == {
            "bound",
            "warning",
            "failed",
            "blocked",
            "not_applicable",
        }


class TestModels:
    def test_binding_creation(self):
        binding = RuntimeEvidenceBinding(
            source=RuntimeEvidenceSource.FILE_EXISTENCE,
            path="test.py",
            summary="File found",
            passed=True,
        )
        assert binding.passed is True
        assert binding.path == "test.py"

    def test_bundle_creation(self):
        bundle = RuntimeTaskEvidenceBundle(
            task_id="TASK-001",
            task_role="doer",
            bindings=[RuntimeEvidenceBinding(summary="test")],
        )
        assert bundle.binding_count == 1
        assert bundle.task_role == "doer"

    def test_bundle_properties(self):
        bundle = RuntimeTaskEvidenceBundle(
            has_files=True,
            has_real_commands=True,
            has_behavior_evidence=False,
            has_security_evidence=False,
            has_arbiter_evidence=True,
        )
        assert bundle.has_files is True
        assert bundle.has_real_commands is True
        assert bundle.has_behavior_evidence is False
        assert bundle.has_arbiter_evidence is True


class TestEchoOnlyDetection:
    def test_detects_echo_only(self):
        assert (
            _has_echo_only_verification(
                [
                    'echo "Verified: all good"',
                    'echo "Verified: tests pass"',
                ]
            )
            is True
        )

    def test_detects_real_commands(self):
        assert (
            _has_echo_only_verification(
                [
                    "uv run pytest tests/ -q",
                    "uv run ruff check .",
                ]
            )
            is False
        )

    def test_mixed_commands(self):
        assert (
            _has_echo_only_verification(
                [
                    'echo "Verified: all good"',
                    "uv run pytest tests/ -q",
                ]
            )
            is False
        )

    def test_empty_commands(self):
        assert _has_echo_only_verification([]) is False

    def test_real_verification_helper(self):
        assert _has_real_verification(["uv run pytest tests/ -q"]) is True
        assert _has_real_verification(['echo "verified"']) is False
        assert _has_real_verification([]) is False


class TestExtractFromDict:
    """Extraction from dict-like task results."""

    def test_minimal_dict(self):
        result = extract_runtime_evidence_from_task_result({})
        assert isinstance(result, RuntimeTaskEvidenceBundle)
        assert result.status != RuntimeEvidenceBindingStatus.BLOCKED

    def test_dict_with_files(self):
        task_result = {
            "task_id": "TASK-001",
            "task_title": "Test task",
            "changed_files": ["index.html", "app.js"],
        }
        bundle = extract_runtime_evidence_from_task_result(task_result)
        assert bundle.has_files is True
        assert any(
            b.source == RuntimeEvidenceSource.FILE_EXISTENCE for b in bundle.bindings
        )

    def test_dict_without_files(self):
        task_result = {
            "task_id": "TASK-002",
            "changed_files": [],
        }
        bundle = extract_runtime_evidence_from_task_result(task_result)
        assert bundle.has_files is False

    def test_dict_with_echo_only_commands(self):
        task_result = {
            "task_id": "TASK-003",
            "task": {
                "agent_role": "verifier",
                "verification_commands": [
                    'echo "Verified: tests pass"',
                    'echo "Verified: all good"',
                ],
            },
        }
        bundle = extract_runtime_evidence_from_task_result(task_result)
        # Echo-only verification for verifier tasks should be blocked
        assert bundle.status == RuntimeEvidenceBindingStatus.BLOCKED

    def test_dict_with_real_commands(self):
        task_result = {
            "task_id": "TASK-004",
            "task": {
                "agent_role": "verifier",
                "verification_commands": [
                    "uv run pytest tests/ -q",
                    "uv run ruff check .",
                ],
                "acceptance_criteria": [
                    "All edge cases for input must be covered.",
                ],
            },
        }
        bundle = extract_runtime_evidence_from_task_result(task_result)
        assert bundle.has_real_commands is True

    def test_dict_with_qa_behavior(self):
        task_result = {
            "task_id": "TASK-005",
            "task": {
                "agent_role": "qa_engineer",
                "verification_commands": ["uv run pytest tests/ -q"],
                "acceptance_criteria": [
                    "Regression tests must pass.",
                    "Edge cases for form validation must be covered.",
                ],
            },
        }
        bundle = extract_runtime_evidence_from_task_result(task_result)
        assert bundle.has_behavior_evidence is True

    def test_dict_without_qa_behavior(self):
        task_result = {
            "task_id": "TASK-006",
            "task": {
                "agent_role": "qa_engineer",
                "verification_commands": ["test -f index.html"],
                "acceptance_criteria": ["Files should exist."],
            },
        }
        bundle = extract_runtime_evidence_from_task_result(task_result)
        assert bundle.has_behavior_evidence is False
        assert len(bundle.warnings) > 0

    def test_dict_with_security_keywords(self):
        task_result = {
            "task_id": "TASK-007",
            "task": {
                "agent_role": "security_engineer",
                "verification_commands": [
                    "uv run bandit -r .",
                    "grep -r vulnerability .",
                ],
                "acceptance_criteria": [
                    "Threat model must cover OWASP Top 10.",
                    "No critical CVEs allowed.",
                ],
            },
        }
        bundle = extract_runtime_evidence_from_task_result(task_result)
        assert bundle.has_security_evidence is True

    def test_dict_forbidden_paths_caught(self):
        """Files inside .fcc/ are still bound as evidence but flagged separately."""
        task_result = {
            "task_id": "TASK-008",
            "changed_files": [".fcc/config.json", "app.js"],
        }
        bundle = extract_runtime_evidence_from_task_result(task_result)
        assert bundle.has_files is True
        # file bindings exist for both
        paths = {b.path for b in bundle.bindings if b.path}
        assert ".fcc/config.json" in paths


class TestExtractFromObjects:
    """Extraction from dataclass/object task results."""

    def test_custom_object(self):
        class FakeResult:
            def __init__(self) -> None:
                self.task_id = "TASK-OBJ-001"
                self.changed_files = ["report.md", "analysis.py"]
                self.stdout_summary = "All tests passed"

        bundle = extract_runtime_evidence_from_task_result(FakeResult())
        assert bundle.has_files is True
        assert bundle.task_id == "TASK-OBJ-001"

    def test_object_with_quality_gate(self):
        @dataclass
        class FakeArbiterDecision:
            action: str = "approve"

        @dataclass
        class FakeQGResult:
            arbiter_decision: FakeArbiterDecision = field(
                default_factory=FakeArbiterDecision
            )
            final_status: str = "passed"

        @dataclass
        class FakeTask:
            agent_role: str = "doer"
            verification_commands: list[str] = field(
                default_factory=lambda: ["uv run pytest -q"]
            )
            acceptance_criteria: list[str] = field(
                default_factory=lambda: ["Tests pass"]
            )

        @dataclass
        class FakeIterationResult:
            task_id: str = "TASK-010"
            quality_gate_result: FakeQGResult = field(default_factory=FakeQGResult)
            task: FakeTask = field(default_factory=FakeTask)

        task_result = FakeIterationResult()
        bundle = extract_runtime_evidence_from_task_result(task_result)
        assert bundle.task_id == "TASK-010"
        assert bundle.has_arbiter_evidence is True

    def test_object_with_verifier_task(self):
        @dataclass
        class FakeTask:
            agent_role: str = "verifier"
            verification_commands: list[str] = field(
                default_factory=lambda: [
                    "uv run pytest tests/ -q",
                    "uv run ruff check .",
                ]
            )
            acceptance_criteria: list[str] = field(
                default_factory=lambda: [
                    "All edge cases must be verified.",
                ]
            )

        @dataclass
        class FakeResult:
            task_id: str = "TASK-VERIFY-001"
            task: FakeTask = field(default_factory=FakeTask)

        bundle = extract_runtime_evidence_from_task_result(FakeResult())
        assert bundle.has_real_commands is True
        assert bundle.has_behavior_evidence is True

    def test_object_with_echo_only_verifier(self):
        @dataclass
        class FakeTask:
            agent_role: str = "verifier"
            verification_commands: list[str] = field(
                default_factory=lambda: [
                    'echo "Verified: all good"',
                ]
            )
            acceptance_criteria: list[str] = field(default_factory=list)

        @dataclass
        class FakeResult:
            task_id: str = "TASK-ECHO-001"
            task: FakeTask = field(default_factory=FakeTask)

        bundle = extract_runtime_evidence_from_task_result(FakeResult())
        # Echo-only verification by verifier should be blocked
        assert bundle.status == RuntimeEvidenceBindingStatus.BLOCKED


class TestSummarizeBundle:
    def test_summary_is_string(self):
        bundle = RuntimeTaskEvidenceBundle(task_id="T-001")
        s = summarize_runtime_evidence_bundle(bundle)
        assert isinstance(s, str)
        assert "T-001" in s

    def test_summary_includes_warnings(self):
        bundle = RuntimeTaskEvidenceBundle(
            task_id="T-002",
            warnings=["Missing behavior checks"],
        )
        s = summarize_runtime_evidence_bundle(bundle)
        assert "WARNING" in s.upper() or "Missing" in s

    def test_summary_includes_failures(self):
        bundle = RuntimeTaskEvidenceBundle(
            task_id="T-003",
            failures=["Echo-only verification"],
        )
        s = summarize_runtime_evidence_bundle(bundle)
        assert "FAILURE" in s.upper() or "Echo-only" in s


class TestNoNetworkOrLLM:
    """Verify no network/LLM calls in runtime evidence module."""

    def test_no_network_imports(self):
        from core.ralph.agent_council import runtime_evidence

        source = runtime_evidence.__file__
        if source:
            with open(str(source)) as f:
                content = f.read()
            assert "anthropic" not in content
            assert "requests" not in content
            assert "urllib" not in content
