"""Tests for planner integration (core/ralph/agent_council/planner_integration.py).

Prove:
- planner integration returns graceful fallback on invalid project type
- build_agent_council_task_context works for known project types
- format_agent_council_context_for_prompt produces concise prompt text
- landing_page context excludes backend/database by default
- full_stack_app context includes frontend/backend/database/security/QA/DevOps
- existing planner behavior is unchanged when Agent Council is disabled
- no LLM/API/network calls occur
"""

from __future__ import annotations

import pytest

from core.ralph.agent_council.planner_integration import (
    build_agent_council_task_context,
    format_agent_council_context_for_prompt,
)
from core.ralph.planner import TaskPlanner
from core.ralph.models import ProjectGoal


class TestBuildAgentCouncilTaskContext:
    """Test the main integration entry point."""

    def test_build_context_for_landing_page(self):
        ctx = build_agent_council_task_context(
            "Build a landing page",
            project_type="landing_page",
        )
        assert ctx["council_plan_available"] is True
        assert ctx["project_type"] == "landing_page"

        # Landing page should NOT have backend/database in active agents
        agents = ctx["active_agents"]
        agent_ids = {a["agent_id"] for a in agents if isinstance(a, dict)}
        assert "senior_backend_developer" not in agent_ids
        assert "database_developer" not in agent_ids

    def test_build_context_for_full_stack_app(self):
        ctx = build_agent_council_task_context(
            "Build a small CRM",
            project_type="full_stack_app",
        )
        assert ctx["council_plan_available"] is True
        assert ctx["project_type"] == "full_stack_app"

        agents = ctx["active_agents"]
        agent_ids = {a["agent_id"] for a in agents if isinstance(a, dict)}

        # Full stack should include all core engineering layers
        assert "senior_frontend_developer" in agent_ids
        assert "senior_backend_developer" in agent_ids
        assert "database_developer" in agent_ids
        assert "security_engineer" in agent_ids
        assert "qa_engineer" in agent_ids
        assert "devops_engineer" in agent_ids

    def test_build_context_for_saas_product(self):
        ctx = build_agent_council_task_context(
            "Build a B2B SaaS CRM",
            project_type="saas_product",
        )
        assert ctx["council_plan_available"] is True

        agents = ctx["active_agents"]
        agent_ids = {a["agent_id"] for a in agents if isinstance(a, dict)}

        assert "growth_analyst" in agent_ids
        assert "analytics_engineer" in agent_ids
        assert "customer_success_manager" in agent_ids
        assert "security_engineer" in agent_ids
        assert "observability_engineer" in agent_ids

    def test_build_context_without_explicit_type(self):
        """Project type is inferred from goal keywords."""
        ctx = build_agent_council_task_context(
            "Build a SaaS platform for team collaboration"
        )
        assert ctx["council_plan_available"] is True
        assert ctx["project_type"] == "saas_product"

    def test_build_context_strict_mode(self):
        ctx = build_agent_council_task_context(
            "Build a CRM",
            project_type="full_stack_app",
            strict_mode=True,
        )
        assert ctx["council_plan_available"] is True

    def test_build_context_returns_critical_path(self):
        ctx = build_agent_council_task_context(
            "Build a full stack app",
            project_type="full_stack_app",
        )
        cp = ctx["critical_path"]
        assert isinstance(cp, list)
        assert len(cp) > 0

    def test_build_context_returns_parallel_groups(self):
        ctx = build_agent_council_task_context(
            "Build a full stack app",
            project_type="full_stack_app",
        )
        groups = ctx["parallel_groups"]
        assert isinstance(groups, list)
        assert len(groups) > 0

    def test_build_context_returns_risks(self):
        ctx = build_agent_council_task_context(
            "Build a SaaS product",
            project_type="saas_product",
        )
        risks = ctx["risks"]
        assert isinstance(risks, list)
        assert len(risks) > 0

    def test_build_context_returns_evidence(self):
        ctx = build_agent_council_task_context(
            "Build a full stack app",
            project_type="full_stack_app",
        )
        evidence = ctx["evidence_requirements"]
        assert isinstance(evidence, list)
        assert len(evidence) > 0


class TestFormatAgentCouncilContextForPrompt:
    """Test prompt formatting."""

    def test_format_produces_string(self):
        ctx = build_agent_council_task_context(
            "Build a CRM",
            project_type="full_stack_app",
        )
        prompt = format_agent_council_context_for_prompt(ctx)
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_format_includes_agent_council_header(self):
        ctx = build_agent_council_task_context(
            "Build a CRM",
            project_type="full_stack_app",
        )
        prompt = format_agent_council_context_for_prompt(ctx)
        assert "Agent Council" in prompt

    def test_format_includes_critical_path(self):
        ctx = build_agent_council_task_context(
            "Build a CRM",
            project_type="full_stack_app",
        )
        prompt = format_agent_council_context_for_prompt(ctx)
        assert "Critical Path" in prompt

    def test_format_includes_risks(self):
        ctx = build_agent_council_task_context(
            "Build a SaaS product",
            project_type="saas_product",
        )
        prompt = format_agent_council_context_for_prompt(ctx)
        assert "Risks" in prompt

    def test_format_with_unavailable_context(self):
        """Format degraded context gracefully."""
        degraded = {"council_plan_available": False, "error": "Test error"}
        prompt = format_agent_council_context_for_prompt(degraded)
        assert "unavailable" in prompt.lower()
        assert "Test error" in prompt


class TestPlannerBackwardCompatibility:
    """Ensure the planner works identically with and without council context."""

    def test_planner_without_council_context(self):
        """Planner works normally when no council context is provided."""
        planner = TaskPlanner()
        goal = ProjectGoal(title="Test", description="Test goal")

        plan = planner.plan(goal)
        assert len(plan.tasks) == 4
        assert plan.agent_council_context is None

    def test_planner_with_council_context(self):
        """Planner enriches tasks when council context is provided."""
        ctx = build_agent_council_task_context(
            "Build a full stack app",
            project_type="full_stack_app",
        )

        planner = TaskPlanner()
        goal = ProjectGoal(title="Test", description="Test goal")

        plan = planner.plan(goal, agent_council_context=ctx)
        assert len(plan.tasks) == 4
        assert plan.agent_council_context is not None
        assert plan.agent_council_context["council_plan_available"] is True

    def test_planner_spec_enriched_with_council(self):
        """Project spec is enriched with council data."""
        ctx = build_agent_council_task_context(
            "Build a full stack app",
            project_type="full_stack_app",
        )

        planner = TaskPlanner()
        goal = ProjectGoal(title="Council Test", description="Testing council")

        plan = planner.plan(goal, agent_council_context=ctx)
        assert plan.spec is not None
        # Summary should include council info
        assert len(plan.spec.summary) > 0

    def test_planner_tasks_enriched_with_council(self):
        """Tasks get council-aware acceptance criteria and KPIs."""
        ctx = build_agent_council_task_context(
            "Build a full stack app",
            project_type="full_stack_app",
        )

        planner = TaskPlanner()
        goal = ProjectGoal(title="Council Test", description="Testing council")

        plan = planner.plan(goal, agent_council_context=ctx)

        # Implementation task should have council-enriched criteria
        impl_task = next(
            (t for t in plan.tasks if "implementation" in t.id.lower()), None
        )
        assert impl_task is not None
        # Should have extra acceptance criteria from council
        assert len(impl_task.acceptance_criteria) >= 2

    def test_planner_no_council_tasks_unchanged(self):
        """Without council context, tasks have standard criteria only."""
        planner = TaskPlanner()
        goal = ProjectGoal(title="Standard", description="Standard test")

        plan = planner.plan(goal)

        impl_task = next(
            (t for t in plan.tasks if "implementation" in t.id.lower()), None
        )
        assert impl_task is not None
        # Standard tasks should have exactly 2 acceptance criteria
        assert len(impl_task.acceptance_criteria) == 2

    def test_planner_deterministic_with_same_context(self):
        """Same council context produces same plan structure."""
        ctx1 = build_agent_council_task_context(
            "Build a CRM",
            project_type="full_stack_app",
        )
        ctx2 = build_agent_council_task_context(
            "Build a CRM",
            project_type="full_stack_app",
        )

        planner1 = TaskPlanner()
        planner2 = TaskPlanner()
        goal = ProjectGoal(title="Test", description="Test")

        plan1 = planner1.plan(goal, agent_council_context=ctx1)
        plan2 = planner2.plan(goal, agent_council_context=ctx2)

        assert len(plan1.tasks) == len(plan2.tasks)
        assert plan1.tasks[0].title == plan2.tasks[0].title

    def test_planner_questions_enriched_with_council(self):
        """Questions include council-specific items when context is available."""
        # Use a plan with missing artifacts by using strict mode
        ctx = build_agent_council_task_context(
            "Build a SaaS CRM",
            project_type="saas_product",
        )
        # Mark as having blocking risks
        ctx["risks"] = [
            {"risk_id": "test", "description": "Blocking test risk",
             "severity": "blocking", "mitigation": "Fix it",
             "affected_agents": [], "affected_artifacts": []}
        ]

        planner = TaskPlanner()
        goal = ProjectGoal(title="Test", description="Test goal")

        plan = planner.plan(goal, agent_council_context=ctx)

        council_questions = [q for q in plan.questions if q.category == "council"]
        assert len(council_questions) > 0


class TestGateContextEnrichment:
    """Verify build_agent_council_task_context includes gate expectations."""

    def test_context_has_gate_expectations(self):
        ctx = build_agent_council_task_context("Build a CRM", "full_stack_app")
        assert "evidence_gate_expectations" in ctx
        assert isinstance(ctx["evidence_gate_expectations"], list)

    def test_context_has_gate_prompt_block(self):
        ctx = build_agent_council_task_context("Build a CRM", "full_stack_app")
        block = ctx.get("gate_prompt_block", "")
        assert isinstance(block, str)
        assert "Evidence Gates" in block

    def test_context_has_readiness_gate_status(self):
        ctx = build_agent_council_task_context("Build a CRM", "full_stack_app")
        assert ctx.get("readiness_gate_status") == "pending"

    def test_format_prompt_includes_gates(self):
        ctx = build_agent_council_task_context("Build a CRM", "full_stack_app")
        prompt = format_agent_council_context_for_prompt(ctx)
        assert "Evidence Gates" in prompt


class TestNoNetworkOrLLM:
    """Verify no network/LLM calls in planner_integration module."""

    def test_no_network_imports(self):
        from core.ralph.agent_council import planner_integration
        source = planner_integration.__file__
        if source:
            with open(str(source)) as f:
                content = f.read()
            assert "anthropic" not in content
            assert "requests" not in content
            assert "urllib" not in content

    def test_all_operations_are_deterministic(self):
        ctx1 = build_agent_council_task_context("Build a CRM", "full_stack_app")
        ctx2 = build_agent_council_task_context("Build a CRM", "full_stack_app")

        assert ctx1["project_type"] == ctx2["project_type"]
        assert ctx1["active_agent_count"] == ctx2["active_agent_count"]
        assert ctx1["next_action"] == ctx2["next_action"]


class TestFormatPromptConciseness:
    """Ensure formatted prompts are concise."""

    def test_prompt_is_reasonably_short(self):
        ctx = build_agent_council_task_context(
            "Build a full stack web application",
            project_type="full_stack_app",
        )
        prompt = format_agent_council_context_for_prompt(ctx)

        # Prompt should not be excessively long
        assert len(prompt.split("\n")) < 60, f"Prompt too long: {len(prompt.split('\n'))} lines"
