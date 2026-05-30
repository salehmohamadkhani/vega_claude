"""Tests for Agent Council V2 activation planner."""

from __future__ import annotations

import pytest

from core.ralph.agent_council.activation import ActivationPlanner


class TestActivationPlanner:
    @pytest.fixture
    def planner(self):
        return ActivationPlanner()

    def test_supported_project_types(self, planner):
        types = planner.supported_project_types
        assert "landing_page" in types
        assert "full_stack_app" in types
        assert "saas_product" in types
        assert "research_project" in types
        assert len(types) == 8

    def test_plan_landing_page(self, planner):
        plan = planner.plan("landing_page")
        assert plan.project_type == "landing_page"
        assert "executive_vision_agent" in plan.active_agents
        assert "senior_frontend_developer_agent" in plan.active_agents
        assert "senior_backend_developer_agent" not in plan.active_agents  # no backend for landing page
        assert "database_developer_agent" not in plan.active_agents  # no DB for landing page
        assert len(plan.parallel_groups) >= 1
        assert plan.total_phases == len(plan.parallel_groups)

    def test_plan_full_stack_app_includes_all_layers(self, planner):
        plan = planner.plan("full_stack_app")
        agents = set(plan.active_agents)
        # full_stack_app should include frontend, backend, database
        assert "executive_vision_agent" in agents
        assert "senior_frontend_developer_agent" in agents
        assert "senior_backend_developer_agent" in agents
        assert "database_developer_agent" in agents
        assert "qa_verification_agent" in agents
        assert "security_compliance_agent" in agents
        assert "devops_infrastructure_agent" in agents

    def test_plan_full_stack_app_includes_backend_and_db(self, planner):
        plan = planner.plan("full_stack_app")
        assert "senior_backend_developer_agent" in plan.active_agents
        assert "database_developer_agent" in plan.active_agents
        assert "security_compliance_agent" in plan.active_agents

    def test_plan_landing_page_no_backend_or_db(self, planner):
        plan = planner.plan("landing_page")
        assert "senior_backend_developer_agent" not in plan.active_agents
        assert "database_developer_agent" not in plan.active_agents

    def test_plan_saas_product_most_comprehensive(self, planner):
        plan = planner.plan("saas_product")
        agents = set(plan.active_agents)
        # SaaS should include growth and support
        assert "growth_analytics_agent" in agents
        assert "support_operations_agent" in agents
        assert len(agents) >= 15  # most comprehensive

    def test_plan_internal_tool_minimal(self, planner):
        plan = planner.plan("internal_tool")
        agents = set(plan.active_agents)
        # Internal tool: no brand, no market research
        assert "brand_content_agent" not in agents
        assert "market_research_agent" not in agents
        # But does have database and security
        assert "database_developer_agent" in agents
        assert "security_compliance_agent" in agents

    def test_plan_research_project_minimal(self, planner):
        plan = planner.plan("research_project")
        agents = set(plan.active_agents)
        # Research: minimal agents
        assert len(agents) <= 6
        assert "executive_vision_agent" in agents
        assert "senior_frontend_developer_agent" not in agents

    def test_plan_ai_tool_has_ml_capable_agents(self, planner):
        plan = planner.plan("ai_tool")
        agents = set(plan.active_agents)
        assert "senior_backend_developer_agent" in agents
        assert "database_developer_agent" in agents
        assert "security_compliance_agent" in agents

    def test_plan_static_site_no_backend(self, planner):
        plan = planner.plan("static_site")
        agents = set(plan.active_agents)
        assert "senior_backend_developer_agent" not in agents
        assert "database_developer_agent" not in agents
        assert "senior_frontend_developer_agent" in agents

    def test_parallel_groups_ordered(self, planner):
        plan = planner.plan("full_stack_app")
        groups = plan.parallel_groups
        # First group should contain agents with no dependencies
        first = set(groups[0])
        for aid in first:
            agent = planner.registry.get(aid)
            deps_in_plan = [d for d in agent.dependencies if d in plan.active_agents]
            assert len(deps_in_plan) == 0, f"{aid} in group 0 but has deps: {deps_in_plan}"

    def test_unknown_project_type_raises(self, planner):
        with pytest.raises(ValueError, match="Unknown project type"):
            planner.plan("nonexistent_project_type")

    def test_get_project_description(self, planner):
        desc = planner.get_project_description("saas_product")
        assert "SaaS" in desc

    def test_get_project_description_unknown(self, planner):
        desc = planner.get_project_description("unknown")
        assert "Unknown" in desc


class TestShouldActivate:
    @pytest.fixture
    def planner(self):
        return ActivationPlanner()

    def test_exec_vision_always_activates(self, planner):
        decision = planner.should_activate("executive_vision_agent", "landing_page")
        assert decision.should_activate is True

    def test_backend_not_for_landing_page(self, planner):
        decision = planner.should_activate("senior_backend_developer_agent", "landing_page")
        assert decision.should_activate is False

    def test_backend_activates_for_full_stack(self, planner):
        decision = planner.should_activate("senior_backend_developer_agent", "full_stack_app")
        assert decision.should_activate is True

    def test_security_activates_for_full_stack(self, planner):
        decision = planner.should_activate("security_compliance_agent", "full_stack_app")
        assert decision.should_activate is True

    def test_all_project_types_have_exec_vision(self, planner):
        for pt in planner.supported_project_types:
            decision = planner.should_activate("executive_vision_agent", pt)
            assert decision.should_activate, f"executive_vision_agent should activate for {pt}"

    def test_all_project_types_have_final_arbiter(self, planner):
        for pt in planner.supported_project_types:
            decision = planner.should_activate("final_arbiter_agent", pt)
            assert decision.should_activate, f"final_arbiter_agent should activate for {pt}"

    def test_missing_agent_returns_false(self, planner):
        decision = planner.should_activate("nonexistent_agent", "full_stack_app")
        assert decision.should_activate is False

    def test_unknown_project_type_returns_false(self, planner):
        decision = planner.should_activate("executive_vision_agent", "unknown_type")
        assert decision.should_activate is False

    def test_activation_phase_assigned(self, planner):
        decision = planner.should_activate("executive_vision_agent", "full_stack_app")
        assert decision.activation_phase >= 0

    def test_missing_dependency_listed_as_blocked(self, planner):
        # saas_product includes growth_analytics_agent which depends on brand_content_agent
        # Both should be in saas_product
        plan = planner.plan("saas_product")
        assert "growth_analytics_agent" in plan.active_agents
        assert "brand_content_agent" in plan.active_agents
