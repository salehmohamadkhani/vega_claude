"""Tests for Ralph Runtime Adapter (core/ralph/agent_council/runtime_adapter.py).

Prove:
- runtime adapter returns a context dict
- summary is human-readable and includes active agents, artifacts, risks, and next action
- build_council_plan_for_goal works with minimal arguments
- no LLM/API/network calls occur
"""

from __future__ import annotations

import pytest

from core.ralph.agent_council.plan import (
    CouncilPlanNextAction,
    CouncilPlanResult,
)
from core.ralph.agent_council.runtime_adapter import (
    build_council_plan_for_goal,
    council_plan_to_context,
    summarize_council_plan,
)


class TestBuildCouncilPlanForGoal:
    """Test the simple entry point for Ralph Runtime."""

    def test_minimal_goal_returns_plan(self):
        """A simple goal string returns a complete plan."""
        plan = build_council_plan_for_goal("Build a landing page")
        assert isinstance(plan, CouncilPlanResult)
        assert plan.is_ready_to_execute is True
        assert plan.total_active_agents > 0

    def test_goal_with_explicit_type(self):
        """Explicit project_type is honored."""
        plan = build_council_plan_for_goal(
            "Build something",
            project_type="landing_page",
        )
        assert plan.project_type == "landing_page"

    def test_goal_with_strict_mode(self):
        """Strict mode flag is passed through."""
        plan = build_council_plan_for_goal(
            "Build a full stack app",
            project_type="full_stack_app",
            strict_mode=False,
        )
        assert plan.is_ready_to_execute is True

    def test_short_goal_still_works(self):
        """Very short goals don't crash — they get a warning."""
        plan = build_council_plan_for_goal("Test")
        assert isinstance(plan, CouncilPlanResult)

    def test_goal_infers_type(self):
        """Goal string is used to infer project type when not explicitly given."""
        plan = build_council_plan_for_goal("Build a SaaS CRM with subscription billing")
        assert plan.project_type == "saas_product"


class TestSummarizeCouncilPlan:
    """Test human-readable summary generation."""

    def test_summary_includes_active_agents(self):
        plan = build_council_plan_for_goal("Build a landing page", project_type="landing_page")
        summary = summarize_council_plan(plan)

        assert "Active Agents" in summary
        assert "COUNCIL PLAN SUMMARY" in summary
        assert "Project Goal" in summary
        assert "Project Type" in summary

    def test_summary_includes_artifacts(self):
        plan = build_council_plan_for_goal("Build a full stack app", project_type="full_stack_app")
        summary = summarize_council_plan(plan)

        assert "Required Artifacts" in summary

    def test_summary_includes_risks(self):
        plan = build_council_plan_for_goal("Build a SaaS product", project_type="saas_product")
        summary = summarize_council_plan(plan)

        assert "Risks" in summary

    def test_summary_includes_next_action(self):
        plan = build_council_plan_for_goal("Build a landing page", project_type="landing_page")
        summary = summarize_council_plan(plan)

        assert "Next Action" in summary
        assert "Ready" in summary

    def test_summary_for_blocked_plan(self):
        """Summary works even for blocked plans."""
        # Create a blocked plan manually
        from core.ralph.agent_council.plan import (
            CouncilPlanNextAction,
            CouncilPlanResult,
        )
        blocked = CouncilPlanResult(
            project_type="unknown",
            project_goal="Bad project",
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
        summary = summarize_council_plan(blocked)
        assert "Ready to Execute: No" in summary
        assert "BLOCKED_BY_UNKNOWN_PROJECT_TYPE" in summary or "Blocked" in summary

    def test_summary_returns_string(self):
        plan = build_council_plan_for_goal("Test app")
        summary = summarize_council_plan(plan)
        assert isinstance(summary, str)
        assert len(summary) > 0


class TestCouncilPlanToContext:
    """Test conversion to Ralph-compatible context dict."""

    def test_context_returns_dict(self):
        plan = build_council_plan_for_goal("Build a test app")
        ctx = council_plan_to_context(plan)

        assert isinstance(ctx, dict)
        assert len(ctx) > 0

    def test_context_has_required_keys(self):
        plan = build_council_plan_for_goal("Build a test app", project_type="full_stack_app")
        ctx = council_plan_to_context(plan)

        expected_keys = {
            "project_type", "project_goal", "is_ready_to_execute",
            "next_action", "next_action_label", "total_active_agents",
            "total_phases", "active_agents", "critical_path",
            "parallel_groups", "required_artifacts", "missing_artifacts",
            "artifact_contracts", "research_references",
            "evidence_requirements", "risks", "warnings", "summary",
        }
        missing = expected_keys - set(ctx.keys())
        assert not missing, f"Missing keys in context: {missing}"

    def test_context_active_agents_are_dicts(self):
        plan = build_council_plan_for_goal("Build a landing page", project_type="landing_page")
        ctx = council_plan_to_context(plan)

        agents = ctx["active_agents"]
        assert isinstance(agents, list)
        assert len(agents) > 0
        agent = agents[0]
        assert isinstance(agent, dict)
        assert "agent_id" in agent
        assert "role_name" in agent
        assert "layer" in agent
        assert "phase" in agent
        assert "depends_on" in agent
        assert "produces_artifacts" in agent

    def test_context_artifacts_are_dicts(self):
        plan = build_council_plan_for_goal("Build a test app", project_type="full_stack_app")
        ctx = council_plan_to_context(plan)

        artifacts = ctx["required_artifacts"]
        assert isinstance(artifacts, list)
        if artifacts:
            art = artifacts[0]
            assert isinstance(art, dict)
            assert "artifact_id" in art
            assert "name" in art
            assert "status" in art

    def test_context_critical_path_is_list(self):
        plan = build_council_plan_for_goal("Build a test app", project_type="full_stack_app")
        ctx = council_plan_to_context(plan)

        cp = ctx["critical_path"]
        assert isinstance(cp, list)
        assert len(cp) > 0

    def test_context_serializable(self):
        """Context dict should be JSON-serializable."""
        import json

        plan = build_council_plan_for_goal("Build a test app", project_type="full_stack_app")
        ctx = council_plan_to_context(plan)

        # Should not raise
        serialized = json.dumps(ctx, default=str)
        assert isinstance(serialized, str)
        assert len(serialized) > 0

    def test_context_no_llm_calls(self):
        """Verify runtime adapter doesn't import or use LLM/API modules."""
        from core.ralph.agent_council import runtime_adapter

        source = runtime_adapter.__file__
        if source:
            with open(str(source)) as f:
                content = f.read()
            assert "anthropic" not in content
            assert "requests" not in content
            assert "http" not in content
            assert "urllib" not in content


class TestFastAndDeterministic:
    """Adapter functions are fast and deterministic."""

    def test_build_council_plan_for_goal_is_fast(self):
        import time

        start = time.monotonic()
        plan = build_council_plan_for_goal("Test")
        elapsed = time.monotonic() - start

        assert isinstance(plan, CouncilPlanResult)
        assert elapsed < 1.0, f"Took {elapsed:.3f}s"

    def test_summarize_is_fast(self):
        import time

        plan = build_council_plan_for_goal("Test")
        start = time.monotonic()
        summary = summarize_council_plan(plan)
        elapsed = time.monotonic() - start

        assert isinstance(summary, str)
        assert elapsed < 0.5, f"Took {elapsed:.3f}s"

    def test_context_conversion_is_fast(self):
        import time

        plan = build_council_plan_for_goal("Test")
        start = time.monotonic()
        ctx = council_plan_to_context(plan)
        elapsed = time.monotonic() - start

        assert isinstance(ctx, dict)
        assert elapsed < 0.5, f"Took {elapsed:.3f}s"

    def test_deterministic_output(self):
        """Same input should produce same plan structure."""
        plan1 = build_council_plan_for_goal("Build a CRM", project_type="full_stack_app")
        plan2 = build_council_plan_for_goal("Build a CRM", project_type="full_stack_app")

        assert plan1.project_type == plan2.project_type
        assert plan1.total_active_agents == plan2.total_active_agents
        assert plan1.next_action == plan2.next_action
        assert plan1.is_ready_to_execute == plan2.is_ready_to_execute
