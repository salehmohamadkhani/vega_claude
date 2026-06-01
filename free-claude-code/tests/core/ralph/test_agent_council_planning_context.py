"""Tests for planning context helpers (core/ralph/agent_council/planning_context.py).

Prove:
- planning context is generated from a CouncilPlanResult
- context includes active agents and artifacts
- context includes evidence requirements
- context includes risk hints
- extract functions produce valid output
- no LLM/API/network calls occur
"""

from __future__ import annotations

from core.ralph.agent_council.plan import (
    CouncilPlanAgentNode,
    CouncilPlanArtifactNode,
    CouncilPlanEvidenceRequirement,
    CouncilPlanNextAction,
    CouncilPlanResearchReference,
    CouncilPlanResult,
    CouncilPlanRisk,
    RiskSeverity,
)
from core.ralph.agent_council.planning_context import (
    build_planning_context_from_council_plan,
    extract_agent_task_hints,
    extract_artifact_task_hints,
    extract_evidence_task_hints,
    extract_risk_task_hints,
    summarize_planning_context,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_plan(**overrides) -> CouncilPlanResult:
    """Build a minimal CouncilPlanResult for testing."""
    defaults = {
        "project_type": "full_stack_app",
        "project_goal": "Build a test app",
        "active_agents": (
            CouncilPlanAgentNode(
                agent_id="chief_vision_officer",
                role_name="Chief Vision Officer",
                layer=1,
                phase=0,
                produces_artifacts=("business_brief", "strategic_direction"),
            ),
            CouncilPlanAgentNode(
                agent_id="software_architect",
                role_name="Software Architect",
                layer=7,
                phase=2,
                depends_on=("product_manager",),
                produces_artifacts=("architecture_spec",),
            ),
            CouncilPlanAgentNode(
                agent_id="senior_backend_developer",
                role_name="Senior Backend Developer",
                layer=9,
                phase=4,
                depends_on=("software_architect",),
                produces_artifacts=("backend_implementation_plan",),
            ),
        ),
        "critical_path": (
            "chief_vision_officer",
            "software_architect",
            "senior_backend_developer",
        ),
        "parallel_groups": (
            ("chief_vision_officer",),
            ("software_architect",),
            ("senior_backend_developer",),
        ),
        "required_artifacts": (
            CouncilPlanArtifactNode(
                artifact_id="business_brief",
                name="Business Brief",
                owner_agent="chief_vision_officer",
                status="pending",
                is_critical=True,
            ),
            CouncilPlanArtifactNode(
                artifact_id="architecture_spec",
                name="Architecture Specification",
                owner_agent="software_architect",
                status="pending",
                is_critical=True,
            ),
        ),
        "missing_artifacts": (),
        "artifact_contracts": ("business_brief", "architecture_spec"),
        "research_references": (
            CouncilPlanResearchReference(
                repo_id="facebook-react",
                category="Frontend Engineering",
                relevance_agent="senior_frontend_developer",
                relevance_level="high",
            ),
        ),
        "evidence_requirements": (
            CouncilPlanEvidenceRequirement(
                requirement_id="ev_arch",
                description="Architecture decisions have documented rationale.",
                required_for_agent="software_architect",
                required_for_artifact="architecture_spec",
                priority="high",
            ),
            CouncilPlanEvidenceRequirement(
                requirement_id="ev_test",
                description="Test coverage report with pass/fail counts.",
                required_for_agent="qa_engineer",
                priority="medium",
            ),
        ),
        "risks": (
            CouncilPlanRisk(
                risk_id="r1",
                description="Test risk",
                severity=RiskSeverity.MEDIUM,
                mitigation="Monitor closely.",
            ),
        ),
        "next_action": CouncilPlanNextAction.READY_FOR_RUNTIME_PLANNING,
        "is_ready_to_execute": True,
        "summary": "Test plan summary.",
    }
    defaults.update(overrides)
    return CouncilPlanResult(**defaults)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestBuildPlanningContext:
    def test_build_context_has_required_keys(self):
        plan = _make_plan()
        ctx = build_planning_context_from_council_plan(plan)

        assert ctx["council_plan_available"] is True
        assert ctx["project_type"] == "full_stack_app"
        assert ctx["project_goal"] == "Build a test app"
        assert ctx["is_ready_to_execute"] is True
        assert ctx["next_action"] == "ready_for_runtime_planning"

    def test_context_active_agents_are_list_of_dicts(self):
        plan = _make_plan()
        ctx = build_planning_context_from_council_plan(plan)

        agents = ctx["active_agents"]
        assert isinstance(agents, list)
        assert len(agents) == 3
        assert agents[0]["agent_id"] == "chief_vision_officer"

    def test_context_artifacts_include_status_and_critical(self):
        plan = _make_plan()
        ctx = build_planning_context_from_council_plan(plan)

        artifacts = ctx["required_artifacts"]
        assert isinstance(artifacts, list)
        assert len(artifacts) == 2
        assert artifacts[0]["is_critical"] is True

    def test_context_evidence_requirements(self):
        plan = _make_plan()
        ctx = build_planning_context_from_council_plan(plan)

        evidence = ctx["evidence_requirements"]
        assert isinstance(evidence, list)
        assert len(evidence) == 2
        assert evidence[0]["priority"] == "high"

    def test_context_risks_with_severity(self):
        plan = _make_plan()
        ctx = build_planning_context_from_council_plan(plan)

        risks = ctx["risks"]
        assert isinstance(risks, list)
        assert len(risks) == 1
        assert risks[0]["severity"] == "medium"

    def test_context_missing_artifacts(self):
        plan = _make_plan(missing_artifacts=("deployment_plan",))
        ctx = build_planning_context_from_council_plan(plan)

        assert "deployment_plan" in ctx["missing_artifact_ids"]

    def test_context_parallel_groups(self):
        plan = _make_plan()
        ctx = build_planning_context_from_council_plan(plan)

        groups = ctx["parallel_groups"]
        assert isinstance(groups, list)
        assert len(groups) == 3

    def test_context_critical_path(self):
        plan = _make_plan()
        ctx = build_planning_context_from_council_plan(plan)

        cp = ctx["critical_path"]
        assert isinstance(cp, list)
        assert len(cp) == 3

    def test_blocked_plan_context(self):
        plan = _make_plan(
            is_ready_to_execute=False,
            next_action=CouncilPlanNextAction.BLOCKED_BY_UNKNOWN_PROJECT_TYPE,
        )
        ctx = build_planning_context_from_council_plan(plan)

        assert ctx["is_ready_to_execute"] is False
        assert ctx["next_action"] == "blocked_by_unknown_project_type"


class TestSummarizePlanningContext:
    def test_summary_includes_project_info(self):
        plan = _make_plan()
        ctx = build_planning_context_from_council_plan(plan)
        summary = summarize_planning_context(ctx)

        assert "full_stack_app" in summary
        assert "Build a test app" in summary
        assert "Active agents" in summary

    def test_summary_includes_risks(self):
        plan = _make_plan()
        ctx = build_planning_context_from_council_plan(plan)
        summary = summarize_planning_context(ctx)

        assert "Risks:" in summary

    def test_summary_includes_missing_artifacts(self):
        plan = _make_plan(missing_artifacts=("test_plan",))
        ctx = build_planning_context_from_council_plan(plan)
        summary = summarize_planning_context(ctx)

        assert "test_plan" in summary

    def test_summary_returns_string(self):
        plan = _make_plan()
        ctx = build_planning_context_from_council_plan(plan)
        summary = summarize_planning_context(ctx)

        assert isinstance(summary, str)
        assert len(summary) > 0


class TestExtractAgentTaskHints:
    def test_extracts_hints_for_all_agents(self):
        plan = _make_plan()
        ctx = build_planning_context_from_council_plan(plan)
        hints = extract_agent_task_hints(ctx)

        assert len(hints) == 3
        assert any("Chief Vision Officer" in h for h in hints)
        assert any("Software Architect" in h for h in hints)

    def test_empty_context_returns_empty(self):
        hints = extract_agent_task_hints({})
        assert hints == []

    def test_no_agents_returns_empty(self):
        ctx = {"active_agents": []}
        hints = extract_agent_task_hints(ctx)
        assert hints == []


class TestExtractArtifactTaskHints:
    def test_extracts_hints_for_all_artifacts(self):
        plan = _make_plan()
        ctx = build_planning_context_from_council_plan(plan)
        hints = extract_artifact_task_hints(ctx)

        assert len(hints) == 2
        assert any("Business Brief" in h for h in hints)
        assert any("CRITICAL" in h for h in hints)

    def test_empty_context_returns_empty(self):
        hints = extract_artifact_task_hints({})
        assert hints == []


class TestExtractEvidenceTaskHints:
    def test_extracts_evidence_hints(self):
        plan = _make_plan()
        ctx = build_planning_context_from_council_plan(plan)
        hints = extract_evidence_task_hints(ctx)

        assert len(hints) == 2
        assert any("HIGH" in h for h in hints)
        assert any("MEDIUM" in h for h in hints)

    def test_empty_context_returns_empty(self):
        hints = extract_evidence_task_hints({})
        assert hints == []


class TestExtractRiskTaskHints:
    def test_extracts_risk_hints(self):
        plan = _make_plan()
        ctx = build_planning_context_from_council_plan(plan)
        hints = extract_risk_task_hints(ctx)

        assert len(hints) == 1
        assert "MEDIUM" in hints[0]
        assert "Test risk" in hints[0]

    def test_blocking_risks(self):
        plan = _make_plan(
            risks=(
                CouncilPlanRisk(
                    risk_id="b1",
                    description="Blocking risk",
                    severity=RiskSeverity.BLOCKING,
                    mitigation="Fix it.",
                ),
            )
        )
        ctx = build_planning_context_from_council_plan(plan)
        hints = extract_risk_task_hints(ctx)

        assert len(hints) == 1
        assert "BLOCKING" in hints[0]

    def test_empty_context_returns_empty(self):
        hints = extract_risk_task_hints({})
        assert hints == []


class TestNoNetworkOrLLM:
    """Verify no network/LLM calls in planning_context module."""

    def test_no_network_imports(self):
        from core.ralph.agent_council import planning_context

        source = planning_context.__file__
        if source:
            with open(str(source)) as f:
                content = f.read()
            assert "anthropic" not in content
            assert "requests" not in content
            assert "urllib" not in content

    def test_all_operations_are_deterministic(self):
        plan = _make_plan()

        ctx1 = build_planning_context_from_council_plan(plan)
        ctx2 = build_planning_context_from_council_plan(plan)

        assert ctx1["project_type"] == ctx2["project_type"]
        assert ctx1["active_agent_count"] == ctx2["active_agent_count"]
        assert ctx1["next_action"] == ctx2["next_action"]
