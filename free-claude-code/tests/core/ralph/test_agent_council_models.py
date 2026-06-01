"""Tests for Agent Council V2 models."""

from __future__ import annotations

import pytest

from core.ralph.agent_council.models import (
    AgentActivationMode,
    AgentCouncilPlan,
    AgentLayer,
    AgentProfile,
    ArtifactContract,
    ArtifactStatus,
    EvidenceItem,
    EvidenceType,
    ResearchReference,
)


class TestAgentLayer:
    def test_layer_values(self):
        assert AgentLayer.EXECUTIVE_VISION.value == 1
        assert AgentLayer.ORCHESTRATION_ARBITRATION.value == 17

    def test_layer_labels(self):
        assert AgentLayer.EXECUTIVE_VISION.label == "Executive / Vision"
        assert AgentLayer.SECURITY_COMPLIANCE.label == "Security / Compliance"

    def test_is_strategic(self):
        assert AgentLayer.EXECUTIVE_VISION.is_strategic is True
        assert AgentLayer.BUSINESS_STRATEGY.is_strategic is True
        assert AgentLayer.MARKET_RESEARCH.is_strategic is True
        assert AgentLayer.PRODUCT_MANAGEMENT.is_strategic is True
        assert AgentLayer.BRAND_CONTENT_MARKETING.is_strategic is True
        assert AgentLayer.SUPPORT_OPERATIONS.is_strategic is True

    def test_is_technical(self):
        assert AgentLayer.UX_UI_PRODUCT_DESIGN.is_technical is True
        assert AgentLayer.SOFTWARE_ARCHITECTURE.is_technical is True
        assert AgentLayer.SECURITY_COMPLIANCE.is_technical is True
        assert AgentLayer.ORCHESTRATION_ARBITRATION.is_technical is True
        # Strategy layers are not technical
        assert AgentLayer.EXECUTIVE_VISION.is_technical is False


class TestAgentActivationMode:
    def test_values(self):
        assert AgentActivationMode.ALWAYS.value == "always"
        assert AgentActivationMode.TRIGGERED.value == "triggered"
        assert AgentActivationMode.ON_DEMAND.value == "on_demand"
        assert AgentActivationMode.CHECKPOINT.value == "checkpoint"
        assert AgentActivationMode.BACKGROUND.value == "background"


class TestArtifactStatus:
    def test_values(self):
        assert ArtifactStatus.PENDING.value == "pending"
        assert ArtifactStatus.VALIDATED.value == "validated"


class TestAgentProfile:
    def test_creation(self):
        agent = AgentProfile(
            agent_id="test_agent",
            role_name="Test Agent",
            layer=1,
            purpose="Testing",
            required_inputs=("input_a",),
            produced_artifacts=("output_a",),
            reviewers=("reviewer_a",),
            fail_conditions=("bad_output",),
            activation_triggers=("project_start",),
            can_run_parallel=False,
            dependencies=("dep_agent",),
            research_categories=("Security",),
        )
        assert agent.agent_id == "test_agent"
        assert agent.layer == 1
        assert agent.layer_enum == AgentLayer.EXECUTIVE_VISION

    def test_immutable(self):
        agent = AgentProfile(
            agent_id="test",
            role_name="T",
            layer=1,
            purpose="P",
        )
        with pytest.raises(AttributeError):
            agent.agent_id = "changed"  # type: ignore[misc]

    def test_hash_and_eq(self):
        a1 = AgentProfile(agent_id="x", role_name="X", layer=1, purpose="p")
        a2 = AgentProfile(agent_id="x", role_name="X", layer=1, purpose="p")
        a3 = AgentProfile(agent_id="y", role_name="Y", layer=2, purpose="q")
        assert hash(a1) == hash(a2)
        assert a1 == a2
        assert a1 != a3
        # String comparison
        assert a1 == "x"
        assert a1 != "y"

    def test_defaults(self):
        agent = AgentProfile(agent_id="minimal", role_name="M", layer=5, purpose="P")
        assert agent.required_inputs == ()
        assert agent.produced_artifacts == ()
        assert agent.can_run_parallel is True
        assert agent.dependencies == ()
        assert agent.research_categories == ()


class TestArtifactContract:
    def test_creation(self):
        contract = ArtifactContract(
            artifact_id="test_artifact",
            name="Test Artifact",
            owner_agent="owner_agent",
            description="A test",
            required_fields=("field_a", "field_b"),
            consumers=("consumer_a", "consumer_b"),
            validation_method="Check fields",
            pass_criteria=("all fields present",),
            fail_criteria=("missing fields",),
        )
        assert contract.artifact_id == "test_artifact"
        assert len(contract.required_fields) == 2
        assert len(contract.consumers) == 2

    def test_immutable(self):
        contract = ArtifactContract(
            artifact_id="t",
            name="T",
            owner_agent="o",
        )
        with pytest.raises(AttributeError):
            contract.artifact_id = "changed"  # type: ignore[misc]

    def test_defaults(self):
        contract = ArtifactContract(artifact_id="t", name="T", owner_agent="o")
        assert contract.required_fields == ()
        assert contract.consumers == ()
        assert contract.validation_method == ""


class TestAgentCouncilPlan:
    def test_creation(self):
        plan = AgentCouncilPlan(
            project_type="full_stack_app",
            active_agents=("a1", "a2"),
            required_artifacts=("art1",),
            parallel_groups=(("a1",), ("a2",)),
            critical_path=("a1", "a2"),
            total_phases=2,
        )
        assert plan.project_type == "full_stack_app"
        assert plan.total_phases == 2
        assert plan.missing_prerequisites == ()


class TestEvidenceType:
    def test_values(self):
        assert EvidenceType.REPO_PATTERN.value == "repo_pattern"
        assert EvidenceType.TEST_RESULT.value == "test_result"


class TestEvidenceItem:
    def test_valid(self):
        item = EvidenceItem(
            source_path="/test/path",
            claim="This is a claim",
            evidence_type=EvidenceType.REPO_PATTERN,
        )
        assert item.is_valid() is True

    def test_invalid_empty_source(self):
        item = EvidenceItem(
            source_path="", claim="claim", evidence_type=EvidenceType.REPO_PATTERN
        )
        assert item.is_valid() is False

    def test_invalid_empty_claim(self):
        item = EvidenceItem(
            source_path="src", claim="", evidence_type=EvidenceType.REPO_PATTERN
        )
        assert item.is_valid() is False

    def test_defaults(self):
        item = EvidenceItem(source_path="s", claim="c")
        assert item.evidence_type == EvidenceType.REPO_PATTERN
        assert item.quality == "unvalidated"


class TestResearchReference:
    def test_creation(self):
        ref = ResearchReference(
            repo_id="facebook-react",
            repo_name="React",
            category="Frontend",
            patterns=("hooks", "fiber"),
            relevance_agent="senior_frontend_developer_agent",
            relevance_level="high",
        )
        assert ref.repo_id == "facebook-react"
        assert len(ref.patterns) == 2
        assert ref.relevance_level == "high"

    def test_defaults(self):
        ref = ResearchReference(repo_id="r")
        assert ref.relevance_level == "medium"
        assert ref.patterns == ()
