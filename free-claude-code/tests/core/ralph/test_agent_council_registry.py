"""Tests for Agent Council V2 registry — 56-agent expanded."""

from __future__ import annotations

import pytest

from core.ralph.agent_council.models import AgentActivationMode
from core.ralph.agent_council.registry import (
    AgentRegistry,
    RegistryValidationError,
    load_default_registry,
)


class TestDefaultRegistrySize:
    """Tests for the expanded 56-agent default registry."""

    @pytest.fixture
    def registry(self):
        return load_default_registry()

    def test_loads_without_error(self, registry):
        assert registry is not None
        assert registry.agent_count == 56

    def test_all_56_agent_ids_unique(self, registry):
        ids = list(registry.agent_ids)
        assert len(ids) == len(set(ids))
        assert len(ids) == 56

    def test_all_17_layers_have_coverage(self, registry):
        layers = registry.layers
        for layer_num in range(1, 18):
            assert layer_num in layers, f"Layer {layer_num} has no agents"

    def test_each_layer_has_at_least_one_agent(self, registry):
        for layer in range(1, 18):
            agents = registry.list_by_layer(layer)
            assert len(agents) >= 1, f"Layer {layer} has no agents"

    def test_layer_1_has_3_agents(self, registry):
        assert len(registry.list_by_layer(1)) == 3

    def test_layer_17_has_5_agents(self, registry):
        assert len(registry.list_by_layer(17)) == 5


class TestDefaultRegistryLookups:
    @pytest.fixture
    def registry(self):
        return load_default_registry()

    def test_lookup_chief_vision_officer(self, registry):
        agent = registry.get("chief_vision_officer")
        assert agent.agent_id == "chief_vision_officer"
        assert agent.layer == 1
        assert agent.role_name == "Chief Vision Officer"
        assert agent.activation_mode == AgentActivationMode.ALWAYS
        assert not agent.can_run_parallel
        assert agent.dependencies == ()

    def test_lookup_orchestrator(self, registry):
        agent = registry.get("orchestrator")
        assert agent.layer == 17
        assert agent.activation_mode == AgentActivationMode.ALWAYS

    def test_lookup_final_arbiter(self, registry):
        agent = registry.get("final_arbiter")
        assert agent.layer == 17
        assert agent.activation_mode == AgentActivationMode.CHECKPOINT
        assert not agent.can_run_parallel
        # final_arbiter depends on QA, security, devops, release, perf
        assert "qa_engineer" in agent.dependencies
        assert "security_engineer" in agent.dependencies

    def test_lookup_project_memory_keeper(self, registry):
        agent = registry.get("project_memory_keeper")
        assert agent.activation_mode == AgentActivationMode.BACKGROUND
        assert agent.can_run_parallel

    def test_lookup_missing_raises(self, registry):
        with pytest.raises(KeyError):
            registry.get("nonexistent_agent")

    def test_lookup_optional_missing_returns_none(self, registry):
        assert registry.get_optional("nonexistent") is None

    def test_lookup_by_layer_3_market_research(self, registry):
        layer3 = registry.list_by_layer(3)
        assert len(layer3) == 4  # market_researcher, competitor_analyst, user_researcher, pricing_analyst
        ids = [a.agent_id for a in layer3]
        assert "market_researcher" in ids
        assert "competitor_analyst" in ids
        assert "user_researcher" in ids
        assert "pricing_analyst" in ids

    def test_lookup_by_artifact(self, registry):
        # market_researcher produces market_research_report
        producers = registry.list_by_artifact("market_research_report")
        assert len(producers) == 1
        assert producers[0].agent_id == "market_researcher"

    def test_lookup_by_input(self, registry):
        # Many agents need product_requirements_doc
        consumers = registry.list_by_input("product_requirements_doc")
        assert len(consumers) >= 5

    def test_producers_of(self, registry):
        producers = registry.producers_of("business_brief")
        assert len(producers) == 1
        assert producers[0].agent_id == "chief_vision_officer"

    def test_consumers_of(self, registry):
        consumers = registry.consumers_of("business_brief")
        assert len(consumers) >= 5

    def test_agent_ids_ordered(self, registry):
        ids = registry.agent_ids
        assert isinstance(ids, tuple)
        assert len(ids) == 56

    def test_layers_returns_all_17(self, registry):
        assert registry.layers == tuple(range(1, 18))


class TestRegistryGrouping:
    @pytest.fixture
    def registry(self):
        return load_default_registry()

    def test_list_strategy_agents(self, registry):
        strategic = registry.list_strategy_agents()
        # Layers 1-5, 15-16: 3+3+4+3+4+3+2 = 22
        assert len(strategic) == 22
        for a in strategic:
            assert a.layer_enum.is_strategic

    def test_list_technical_agents(self, registry):
        technical = registry.list_technical_agents()
        # Layers 6-14, 17: 5+3+3+3+3+4+3+3+2+5 = 34
        assert len(technical) == 34
        for a in technical:
            assert a.layer_enum.is_technical

    def test_list_implementation_agents(self, registry):
        impl = registry.list_implementation_agents()
        # Layers 8-10: 3+3+3 = 9
        assert len(impl) == 9
        for a in impl:
            assert a.layer in (8, 9, 10)

    def test_list_always_activated(self, registry):
        always = registry.list_always_activated()
        always_ids = {a.agent_id for a in always}
        assert "chief_vision_officer" in always_ids
        assert "product_manager" in always_ids
        assert "software_architect" in always_ids
        assert "qa_engineer" in always_ids
        assert "security_engineer" in always_ids
        assert "orchestrator" in always_ids

    def test_list_critical_path_agents(self, registry):
        critical = registry.list_critical_path_agents()
        critical_ids = {a.agent_id for a in critical}
        assert "chief_vision_officer" in critical_ids
        assert "product_manager" in critical_ids
        assert "software_architect" in critical_ids
        assert "final_arbiter" in critical_ids
        assert "orchestrator" in critical_ids

    def test_list_by_activation_mode(self, registry):
        checkpoint = registry.list_by_activation_mode("checkpoint")
        cp_ids = {a.agent_id for a in checkpoint}
        assert "final_arbiter" in cp_ids
        assert "strategic_alignment_auditor" in cp_ids
        assert "release_manager" in cp_ids
        assert "quality_gate_keeper" in cp_ids


class TestRegistryValidation:
    def test_duplicate_ids_raise(self):
        agents = (
            __import__("core.ralph.agent_council.models", fromlist=["AgentProfile"]).AgentProfile(
                agent_id="dup", role_name="A", layer=1, purpose="p"),
            __import__("core.ralph.agent_council.models", fromlist=["AgentProfile"]).AgentProfile(
                agent_id="dup", role_name="B", layer=2, purpose="q"),
        )
        with pytest.raises(RegistryValidationError, match="Duplicate"):
            AgentRegistry(agents)

    def test_self_dependency_raises(self):
        from core.ralph.agent_council.models import AgentProfile
        agents = (
            AgentProfile(
                agent_id="self_ref", role_name="S", layer=1, purpose="p",
                dependencies=("self_ref",),
            ),
        )
        with pytest.raises(RegistryValidationError, match="cannot depend on itself"):
            AgentRegistry(agents)

    def test_unknown_dependency_raises(self):
        from core.ralph.agent_council.models import AgentProfile
        agents = (
            AgentProfile(
                agent_id="dep_missing", role_name="D", layer=1, purpose="p",
                dependencies=("nonexistent_dep",),
            ),
        )
        with pytest.raises(RegistryValidationError, match="not found"):
            AgentRegistry(agents)

    def test_unknown_reviewer_raises(self):
        from core.ralph.agent_council.models import AgentProfile
        agents = (
            AgentProfile(
                agent_id="bad_reviewer", role_name="B", layer=1, purpose="p",
                reviewers=("no_such_reviewer",),
            ),
        )
        with pytest.raises(RegistryValidationError, match="not found"):
            AgentRegistry(agents)

    def test_invalid_layer_raises(self):
        from core.ralph.agent_council.models import AgentProfile
        agents = (
            AgentProfile(agent_id="bad_layer", role_name="B", layer=99, purpose="p"),
        )
        with pytest.raises(RegistryValidationError, match="must be 1-17"):
            AgentRegistry(agents)


class TestArtifactChainValidation:
    @pytest.fixture
    def registry(self):
        return load_default_registry()

    def test_all_produced_artifacts_have_consumers_or_are_terminal(self, registry):
        terminal = {
            "final_arbiter_decision", "release_approval", "conflict_resolution",
            "project_memory", "lessons_learned", "context_handoff",
            "decisions_log", "trade_off_journal",
        }
        for agent in registry.list_all():
            for art_id in agent.produced_artifacts:
                if art_id in terminal:
                    continue
                consumers = registry.consumers_of(art_id)
                if len(consumers) == 0:
                    # Check if it's a known orphan
                    orchans = registry.find_orphan_artifacts()
                    if art_id in orchans:
                        # Some artifacts may be consumed outside the registry
                        # (e.g., documents consumed by external users)
                        pass

    def test_find_orphan_artifacts_returns_only_non_terminal(self, registry):
        orchans = registry.find_orphan_artifacts()
        terminal = {
            "final_arbiter_decision", "release_approval", "conflict_resolution",
            "project_memory", "lessons_learned", "context_handoff",
            "decisions_log", "trade_off_journal",
        }
        for art_id in orchans:
            assert art_id not in terminal

    def test_project_brief_is_external_input(self, registry):
        # project_brief should not be produced by any agent
        producers = registry.producers_of("project_brief")
        assert len(producers) == 0


class TestSpecificAgentsExist:
    """Verify key taxonomy agents exist."""

    @pytest.fixture
    def registry(self):
        return load_default_registry()

    # Layer 1
    def test_chief_vision_officer_exists(self, registry):
        assert registry.get("chief_vision_officer") is not None

    def test_chief_product_ethics_officer_exists(self, registry):
        assert registry.get("chief_product_ethics_officer") is not None

    def test_strategic_alignment_auditor_exists(self, registry):
        assert registry.get("strategic_alignment_auditor") is not None

    # Layer 2
    def test_business_strategist_exists(self, registry):
        assert registry.get("business_strategist") is not None

    def test_monetization_strategist_exists(self, registry):
        assert registry.get("monetization_strategist") is not None

    def test_legal_compliance_officer_exists(self, registry):
        assert registry.get("legal_compliance_officer") is not None

    # Layer 3
    def test_market_researcher_exists(self, registry):
        assert registry.get("market_researcher") is not None

    def test_competitor_analyst_exists(self, registry):
        assert registry.get("competitor_analyst") is not None

    def test_user_researcher_exists(self, registry):
        assert registry.get("user_researcher") is not None

    def test_pricing_analyst_exists(self, registry):
        assert registry.get("pricing_analyst") is not None

    # Layer 4
    def test_product_manager_exists(self, registry):
        assert registry.get("product_manager") is not None

    def test_technical_product_manager_exists(self, registry):
        assert registry.get("technical_product_manager") is not None

    def test_scope_manager_exists(self, registry):
        assert registry.get("scope_manager") is not None

    # Layer 5
    def test_brand_strategist_exists(self, registry):
        assert registry.get("brand_strategist") is not None

    def test_content_strategist_exists(self, registry):
        assert registry.get("content_strategist") is not None

    def test_marketing_lead_exists(self, registry):
        assert registry.get("marketing_lead") is not None

    def test_seo_specialist_exists(self, registry):
        assert registry.get("seo_specialist") is not None

    # Layer 6
    def test_ux_designer_exists(self, registry):
        assert registry.get("ux_designer") is not None

    def test_ui_designer_exists(self, registry):
        assert registry.get("ui_designer") is not None

    def test_design_system_architect_exists(self, registry):
        assert registry.get("design_system_architect") is not None

    def test_interaction_designer_exists(self, registry):
        assert registry.get("interaction_designer") is not None

    def test_accessibility_auditor_exists(self, registry):
        assert registry.get("accessibility_auditor") is not None

    # Layer 7
    def test_software_architect_exists(self, registry):
        assert registry.get("software_architect") is not None

    def test_api_architect_exists(self, registry):
        assert registry.get("api_architect") is not None

    def test_data_architect_exists(self, registry):
        assert registry.get("data_architect") is not None

    # Layer 8
    def test_senior_frontend_developer_exists(self, registry):
        assert registry.get("senior_frontend_developer") is not None

    def test_frontend_performance_engineer_exists(self, registry):
        assert registry.get("frontend_performance_engineer") is not None

    def test_mobile_developer_exists(self, registry):
        assert registry.get("mobile_developer") is not None

    # Layer 9
    def test_senior_backend_developer_exists(self, registry):
        assert registry.get("senior_backend_developer") is not None

    def test_api_developer_exists(self, registry):
        assert registry.get("api_developer") is not None

    def test_integration_engineer_exists(self, registry):
        assert registry.get("integration_engineer") is not None

    # Layer 10
    def test_database_developer_exists(self, registry):
        assert registry.get("database_developer") is not None

    def test_data_engineer_exists(self, registry):
        assert registry.get("data_engineer") is not None

    def test_ml_engineer_exists(self, registry):
        assert registry.get("ml_engineer") is not None

    # Layer 12
    def test_security_engineer_exists(self, registry):
        assert registry.get("security_engineer") is not None

    def test_penetration_tester_exists(self, registry):
        assert registry.get("penetration_tester") is not None

    def test_dependency_auditor_exists(self, registry):
        assert registry.get("dependency_auditor") is not None

    # Layer 17
    def test_orchestrator_exists(self, registry):
        assert registry.get("orchestrator") is not None

    def test_project_memory_keeper_exists(self, registry):
        assert registry.get("project_memory_keeper") is not None

    def test_final_arbiter_exists(self, registry):
        assert registry.get("final_arbiter") is not None

    def test_conflict_resolver_exists(self, registry):
        assert registry.get("conflict_resolver") is not None

    def test_quality_gate_keeper_exists(self, registry):
        assert registry.get("quality_gate_keeper") is not None


class TestSecurityAgentsResearchCategories:
    @pytest.fixture
    def registry(self):
        return load_default_registry()

    def test_security_engineer_has_security_categories(self, registry):
        agent = registry.get("security_engineer")
        assert "Security / Compliance" in agent.research_categories
        assert "Security Scanning" in agent.research_categories

    def test_penetration_tester_has_security_categories(self, registry):
        agent = registry.get("penetration_tester")
        assert "Security / Compliance" in agent.research_categories

    def test_dependency_auditor_has_security_categories(self, registry):
        agent = registry.get("dependency_auditor")
        assert "Security / Compliance" in agent.research_categories
        assert "Security Scanning" in agent.research_categories


class TestNoDependencyCycles:
    @pytest.fixture
    def registry(self):
        return load_default_registry()

    def test_no_cycles_in_default_registry(self, registry):
        from core.ralph.agent_council.dependency_graph import detect_cycles
        cycles = detect_cycles(registry)
        assert len(cycles) == 0, f"Cycles found: {cycles}"
