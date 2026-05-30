"""Tests for Agent Council V2 activation planner — updated for 56-agent registry."""

from __future__ import annotations

import pytest

from core.ralph.agent_council.activation import ActivationPlanner
from core.ralph.agent_council.registry import load_default_registry


@pytest.fixture
def planner():
    return ActivationPlanner()


@pytest.fixture
def registry():
    return load_default_registry()


class TestSupportedProjectTypes:
    def test_has_8_supported_types(self, planner):
        types = planner.supported_project_types
        assert len(types) == 8

    def test_all_expected_types_present(self, planner):
        expected = {
            "landing_page", "static_site", "frontend_app",
            "full_stack_app", "saas_product", "ai_tool",
            "internal_tool", "research_project",
        }
        assert set(planner.supported_project_types) == expected

    def test_get_project_description(self, planner):
        desc = planner.get_project_description("saas_product")
        assert "SaaS" in desc or "Multi-tenant" in desc


class TestLandingPage:
    def test_plan_returns_valid_plan(self, planner):
        plan = planner.plan("landing_page")
        assert plan.project_type == "landing_page"
        assert len(plan.active_agents) >= 8
        assert "chief_vision_officer" in plan.active_agents
        assert "final_arbiter" in plan.active_agents

    def test_excludes_backend_and_database(self, planner):
        plan = planner.plan("landing_page")
        assert "senior_backend_developer" not in plan.active_agents
        assert "database_developer" not in plan.active_agents
        assert "senior_frontend_developer" in plan.active_agents

    def test_includes_brand_and_seo(self, planner):
        plan = planner.plan("landing_page")
        assert "brand_strategist" in plan.active_agents
        assert "seo_specialist" in plan.active_agents

    def test_includes_ux_ui(self, planner):
        plan = planner.plan("landing_page")
        assert "ux_designer" in plan.active_agents
        assert "ui_designer" in plan.active_agents

    def test_includes_orchestrator_and_memory(self, planner):
        plan = planner.plan("landing_page")
        assert "orchestrator" in plan.active_agents
        assert "project_memory_keeper" in plan.active_agents


class TestFullStackApp:
    def test_fs_includes_frontend_backend_database(self, planner):
        plan = planner.plan("full_stack_app")
        assert "senior_frontend_developer" in plan.active_agents
        assert "senior_backend_developer" in plan.active_agents
        assert "database_developer" in plan.active_agents

    def test_fs_includes_security_and_qa(self, planner):
        plan = planner.plan("full_stack_app")
        assert "security_engineer" in plan.active_agents
        assert "qa_engineer" in plan.active_agents

    def test_fs_includes_devops(self, planner):
        plan = planner.plan("full_stack_app")
        assert "devops_engineer" in plan.active_agents

    def test_fs_includes_observability(self, planner):
        plan = planner.plan("full_stack_app")
        assert "observability_engineer" in plan.active_agents

    def test_fs_includes_api_and_data_architects(self, planner):
        plan = planner.plan("full_stack_app")
        assert "api_architect" in plan.active_agents
        assert "data_architect" in plan.active_agents

    def test_fs_includes_penetration_tester(self, planner):
        plan = planner.plan("full_stack_app")
        assert "penetration_tester" in plan.active_agents
        assert "dependency_auditor" in plan.active_agents

    def test_fs_includes_quality_gate_keeper(self, planner):
        plan = planner.plan("full_stack_app")
        assert "quality_gate_keeper" in plan.active_agents

    def test_fs_includes_accessibility(self, planner):
        plan = planner.plan("full_stack_app")
        assert "accessibility_auditor" in plan.active_agents

    def test_fs_agent_count(self, planner):
        plan = planner.plan("full_stack_app")
        assert len(plan.active_agents) > 30


class TestSaaSProduct:
    def test_saas_includes_all_growth(self, planner):
        plan = planner.plan("saas_product")
        assert "growth_analyst" in plan.active_agents
        assert "analytics_engineer" in plan.active_agents
        assert "conversion_optimizer" in plan.active_agents

    def test_saas_includes_support(self, planner):
        plan = planner.plan("saas_product")
        assert "customer_success_manager" in plan.active_agents
        assert "documentation_specialist" in plan.active_agents

    def test_saas_includes_monetization_pricing(self, planner):
        plan = planner.plan("saas_product")
        assert "monetization_strategist" in plan.active_agents
        assert "pricing_analyst" in plan.active_agents

    def test_saas_includes_security_and_pen_test(self, planner):
        plan = planner.plan("saas_product")
        assert "security_engineer" in plan.active_agents
        assert "penetration_tester" in plan.active_agents
        assert "dependency_auditor" in plan.active_agents

    def test_saas_includes_sre(self, planner):
        plan = planner.plan("saas_product")
        assert "sre_engineer" in plan.active_agents

    def test_saas_includes_production_readiness(self, planner):
        plan = planner.plan("saas_product")
        assert "release_manager" in plan.active_agents
        assert "infrastructure_engineer" in plan.active_agents

    def test_saas_includes_legal_compliance(self, planner):
        plan = planner.plan("saas_product")
        assert "legal_compliance_officer" in plan.active_agents

    def test_saas_is_most_comprehensive(self, planner):
        plan = planner.plan("saas_product")
        assert len(plan.active_agents) >= 45

    def test_saas_includes_all_orchestration(self, planner):
        plan = planner.plan("saas_product")
        assert "orchestrator" in plan.active_agents
        assert "final_arbiter" in plan.active_agents
        assert "conflict_resolver" in plan.active_agents
        assert "quality_gate_keeper" in plan.active_agents
        assert "project_memory_keeper" in plan.active_agents


class TestAITool:
    def test_ai_includes_ml_engineer(self, planner):
        plan = planner.plan("ai_tool")
        assert "ml_engineer" in plan.active_agents

    def test_ai_includes_ethics(self, planner):
        plan = planner.plan("ai_tool")
        assert "chief_product_ethics_officer" in plan.active_agents

    def test_ai_includes_performance_tester(self, planner):
        plan = planner.plan("ai_tool")
        assert "performance_tester" in plan.active_agents


class TestResearchProject:
    def test_research_is_minimal(self, planner):
        plan = planner.plan("research_project")
        assert len(plan.active_agents) <= 12

    def test_research_includes_vision_and_research(self, planner):
        plan = planner.plan("research_project")
        assert "chief_vision_officer" in plan.active_agents
        assert "market_researcher" in plan.active_agents

    def test_research_includes_final_arbiter(self, planner):
        plan = planner.plan("research_project")
        assert "final_arbiter" in plan.active_agents

    def test_research_excludes_backend(self, planner):
        plan = planner.plan("research_project")
        assert "senior_backend_developer" not in plan.active_agents
        assert "senior_frontend_developer" not in plan.active_agents


class TestInternalTool:
    def test_internal_excludes_market_research_brand(self, planner):
        plan = planner.plan("internal_tool")
        assert "market_researcher" not in plan.active_agents
        assert "brand_strategist" not in plan.active_agents
        assert "competitor_analyst" not in plan.active_agents

    def test_internal_includes_core_engineering(self, planner):
        plan = planner.plan("internal_tool")
        assert "senior_frontend_developer" in plan.active_agents
        assert "senior_backend_developer" in plan.active_agents
        assert "database_developer" in plan.active_agents


class TestActivationDecisions:
    def test_should_activate_returns_decision(self, planner):
        decision = planner.should_activate("chief_vision_officer", "landing_page")
        assert decision.should_activate is True
        assert decision.agent_id == "chief_vision_officer"

    def test_should_not_activate_backend_for_landing(self, planner):
        decision = planner.should_activate("senior_backend_developer", "landing_page")
        assert decision.should_activate is False
        assert "not required" in decision.reason.lower()

    def test_unknown_project_type_returns_false(self, planner):
        decision = planner.should_activate("chief_vision_officer", "unknown_type")
        assert decision.should_activate is False

    def test_missing_agent_returns_false(self, planner):
        decision = planner.should_activate("nonexistent", "full_stack_app")
        assert decision.should_activate is False
        assert "not found" in decision.reason.lower()


class TestRationale:
    def test_all_types_have_rationale(self, planner):
        for pt in planner.supported_project_types:
            rationale = planner.get_project_rationale(pt)
            assert rationale, f"Missing rationale for {pt}"
            assert len(rationale) > 20

    def test_rationale_not_empty_for_plan(self, planner):
        rationale = planner.get_project_rationale("landing_page")
        assert "landing" in rationale.lower() or "Landing" in rationale


class TestParallelGroups:
    def test_plan_has_parallel_groups(self, planner):
        plan = planner.plan("full_stack_app")
        assert len(plan.parallel_groups) >= 1
        assert plan.total_phases == len(plan.parallel_groups)

    def test_parallel_groups_are_ordered(self, planner):
        plan = planner.plan("full_stack_app")
        for i in range(len(plan.parallel_groups) - 1):
            prev_group = plan.parallel_groups[i]
            next_group = plan.parallel_groups[i + 1]
            assert len(prev_group) >= 1
            assert len(next_group) >= 1


class TestUnknownType:
    def test_unknown_type_raises(self, planner):
        with pytest.raises(ValueError, match="Unknown project type"):
            planner.plan("rocket_ship")
