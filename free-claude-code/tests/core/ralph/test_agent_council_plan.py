"""Tests for Council Plan models (core/ralph/agent_council/plan.py)."""

from __future__ import annotations

import dataclasses

import pytest

from core.ralph.agent_council.plan import (
    CouncilPlanAgentNode,
    CouncilPlanArtifactNode,
    CouncilPlanEvidenceRequirement,
    CouncilPlanNextAction,
    CouncilPlanRequest,
    CouncilPlanResearchReference,
    CouncilPlanResult,
    CouncilPlanRisk,
    RiskSeverity,
)


class TestCouncilPlanNextAction:
    def test_all_expected_actions_exist(self):
        """Verify all 6 expected next action values exist."""
        expected = {
            "ready_for_runtime_planning",
            "needs_missing_artifacts",
            "needs_scope_clarification",
            "blocked_by_dependency_cycle",
            "blocked_by_unknown_project_type",
            "blocked_by_missing_required_agent",
        }
        actual = {e.value for e in CouncilPlanNextAction}
        assert actual == expected

    def test_action_values_are_strings(self):
        for action in CouncilPlanNextAction:
            assert isinstance(action.value, str)
            assert len(action.value) > 0


class TestRiskSeverity:
    def test_all_severities_exist(self):
        expected = {"blocking", "high", "medium", "low"}
        actual = {e.value for e in RiskSeverity}
        assert actual == expected


class TestCouncilPlanRequest:
    def test_minimal_request(self):
        req = CouncilPlanRequest(project_goal="Build a test app")
        assert req.project_goal == "Build a test app"
        assert req.project_type == ""
        assert req.constraints == ()
        assert req.available_artifacts == ()
        assert req.requested_agents == ()
        assert req.excluded_agents == ()
        assert req.research_root == ""
        assert req.strict_mode is False

    def test_full_request(self):
        req = CouncilPlanRequest(
            project_goal="Build a SaaS CRM",
            project_type="full_stack_app",
            constraints=("max 100 users",),
            available_artifacts=("business_brief",),
            requested_agents=("security_engineer",),
            excluded_agents=("content_strategist",),
            research_root="/opt/vega-cloud/research",
            strict_mode=True,
        )
        assert req.project_type == "full_stack_app"
        assert req.strict_mode is True
        assert "business_brief" in req.available_artifacts
        assert "security_engineer" in req.requested_agents
        assert "content_strategist" in req.excluded_agents

    def test_request_is_immutable(self):
        req = CouncilPlanRequest(project_goal="Test")
        with pytest.raises(dataclasses.FrozenInstanceError):
            req.project_goal = "Changed"  # type: ignore[misc]


class TestCouncilPlanResult:
    def test_minimal_result(self):
        result = CouncilPlanResult(
            project_type="landing_page",
            project_goal="Build a landing page",
            active_agents=(),
            critical_path=(),
            parallel_groups=(),
            required_artifacts=(),
            missing_artifacts=(),
            artifact_contracts=(),
            research_references=(),
            evidence_requirements=(),
            risks=(),
            next_action=CouncilPlanNextAction.READY_FOR_RUNTIME_PLANNING,
            is_ready_to_execute=True,
        )
        assert result.project_type == "landing_page"
        assert result.is_ready_to_execute is True
        assert result.is_blocked is False
        assert result.total_active_agents == 0
        assert result.total_phases == 0

    def test_blocked_result(self):
        result = CouncilPlanResult(
            project_type="unknown_type",
            project_goal="Test",
            active_agents=(),
            critical_path=(),
            parallel_groups=(),
            required_artifacts=(),
            missing_artifacts=(),
            artifact_contracts=(),
            research_references=(),
            evidence_requirements=(),
            risks=(),
            next_action=CouncilPlanNextAction.BLOCKED_BY_UNKNOWN_PROJECT_TYPE,
            is_ready_to_execute=False,
        )
        assert result.is_ready_to_execute is False
        assert result.is_blocked is True

    def test_next_action_label(self):
        result = CouncilPlanResult(
            project_type="full_stack_app",
            project_goal="Test",
            active_agents=(),
            critical_path=(),
            parallel_groups=(),
            required_artifacts=(),
            missing_artifacts=(),
            artifact_contracts=(),
            research_references=(),
            evidence_requirements=(),
            risks=(),
            next_action=CouncilPlanNextAction.READY_FOR_RUNTIME_PLANNING,
            is_ready_to_execute=True,
        )
        assert "Ready" in result.next_action_label

    def test_agent_count_by_layer(self):
        agents = (
            CouncilPlanAgentNode(agent_id="a1", role_name="Agent 1", layer=1, phase=0),
            CouncilPlanAgentNode(agent_id="a2", role_name="Agent 2", layer=1, phase=0),
            CouncilPlanAgentNode(agent_id="a3", role_name="Agent 3", layer=7, phase=1),
        )
        result = CouncilPlanResult(
            project_type="test",
            project_goal="Test",
            active_agents=agents,
            critical_path=("a1", "a2", "a3"),
            parallel_groups=(("a1", "a2"), ("a3",)),
            required_artifacts=(),
            missing_artifacts=(),
            artifact_contracts=(),
            research_references=(),
            evidence_requirements=(),
            risks=(),
            next_action=CouncilPlanNextAction.READY_FOR_RUNTIME_PLANNING,
            is_ready_to_execute=True,
        )
        counts = result.agent_count_by_layer
        assert counts[1] == 2
        assert counts[7] == 1
        # total_active_agents is set by the generator; manually constructed
        # results have the default (0) unless explicitly passed
        assert result.total_phases == 0  # not auto-computed


class TestCouncilPlanAgentNode:
    def test_basic_node(self):
        node = CouncilPlanAgentNode(
            agent_id="test_agent",
            role_name="Test Agent",
            layer=1,
            phase=0,
        )
        assert node.agent_id == "test_agent"
        assert node.role_name == "Test Agent"
        assert node.layer == 1
        assert node.phase == 0
        assert node.can_run_parallel is True

    def test_node_with_deps_and_artifacts(self):
        node = CouncilPlanAgentNode(
            agent_id="backend_dev",
            role_name="Backend Developer",
            layer=9,
            phase=2,
            depends_on=("software_architect", "api_architect"),
            produces_artifacts=("backend_implementation_plan",),
            can_run_parallel=False,
        )
        assert "software_architect" in node.depends_on
        assert "backend_implementation_plan" in node.produces_artifacts
        assert node.can_run_parallel is False

    def test_node_immutable(self):
        node = CouncilPlanAgentNode(agent_id="a", role_name="R", layer=1, phase=0)
        with pytest.raises(dataclasses.FrozenInstanceError):
            node.agent_id = "b"  # type: ignore[misc]


class TestCouncilPlanArtifactNode:
    def test_pending_artifact(self):
        node = CouncilPlanArtifactNode(
            artifact_id="business_brief",
            name="Business Brief",
            owner_agent="chief_vision_officer",
            status="pending",
            is_critical=True,
        )
        assert node.status == "pending"
        assert node.is_critical is True
        assert node.owner_agent == "chief_vision_officer"

    def test_available_artifact(self):
        node = CouncilPlanArtifactNode(
            artifact_id="test_artifact",
            name="Test",
            status="available",
        )
        assert node.status == "available"
        assert node.is_critical is False


class TestCouncilPlanRisk:
    def test_basic_risk(self):
        risk = CouncilPlanRisk(
            risk_id="test_risk",
            description="A test risk",
            severity=RiskSeverity.HIGH,
        )
        assert risk.risk_id == "test_risk"
        assert risk.severity == RiskSeverity.HIGH

    def test_blocking_risk(self):
        risk = CouncilPlanRisk(
            risk_id="blocking",
            description="Blocks everything",
            severity=RiskSeverity.BLOCKING,
            affected_agents=("agent1",),
            affected_artifacts=("artifact1",),
            mitigation="Fix it",
        )
        assert risk.severity == RiskSeverity.BLOCKING
        assert "agent1" in risk.affected_agents
        assert risk.mitigation == "Fix it"


class TestCouncilPlanEvidenceRequirement:
    def test_basic_requirement(self):
        req = CouncilPlanEvidenceRequirement(
            requirement_id="ev_1",
            description="Test evidence requirement",
            priority="high",
        )
        assert req.requirement_id == "ev_1"
        assert req.priority == "high"

    def test_evidence_for_agent(self):
        req = CouncilPlanEvidenceRequirement(
            requirement_id="ev_arch",
            description="Architecture evidence",
            required_for_agent="software_architect",
            required_for_artifact="architecture_spec",
            source_hint="Agent output",
            priority="medium",
        )
        assert req.required_for_agent == "software_architect"
        assert req.required_for_artifact == "architecture_spec"


class TestCouncilPlanResearchReference:
    def test_basic_reference(self):
        ref = CouncilPlanResearchReference(
            repo_id="facebook-react",
            category="Frontend Engineering",
            relevance_agent="senior_frontend_developer",
            relevance_level="high",
        )
        assert ref.repo_id == "facebook-react"
        assert ref.relevance_level == "high"
