"""Tests for Agent Council V2 registry."""

from __future__ import annotations

import pytest

from core.ralph.agent_council.models import AgentActivationMode, AgentProfile
from core.ralph.agent_council.registry import (
    AgentRegistry,
    RegistryValidationError,
    load_default_registry,
)


class TestDefaultRegistry:
    """Tests against the default 17-agent registry."""

    @pytest.fixture
    def registry(self):
        return load_default_registry()

    def test_loads_without_error(self, registry):
        assert registry is not None
        assert registry.agent_count == 17

    def test_all_17_layers_have_coverage(self, registry):
        layers = registry.layers
        for layer_num in range(1, 18):
            assert layer_num in layers, f"Layer {layer_num} has no agents"

    def test_no_duplicate_agent_ids(self, registry):
        ids = list(registry.agent_ids)
        assert len(ids) == len(set(ids))

    def test_each_layer_has_at_least_one_agent(self, registry):
        for layer in range(1, 18):
            agents = registry.list_by_layer(layer)
            assert len(agents) >= 1, f"Layer {layer} has no agents"

    def test_lookup_by_id(self, registry):
        agent = registry.get("executive_vision_agent")
        assert agent.agent_id == "executive_vision_agent"
        assert agent.layer == 1
        assert agent.role_name == "Executive Vision Agent"

    def test_lookup_missing_raises(self, registry):
        with pytest.raises(KeyError):
            registry.get("nonexistent_agent")

    def test_lookup_optional_missing_returns_none(self, registry):
        assert registry.get_optional("nonexistent") is None

    def test_lookup_by_layer(self, registry):
        layer1 = registry.list_by_layer(1)
        assert len(layer1) >= 1
        assert any(a.agent_id == "executive_vision_agent" for a in layer1)

    def test_lookup_by_artifact(self, registry):
        producers = registry.list_by_artifact("business_brief")
        assert len(producers) >= 1
        assert any(a.agent_id == "executive_vision_agent" for a in producers)

    def test_lookup_by_input(self, registry):
        consumers = registry.list_by_input("business_brief")
        assert len(consumers) >= 1
        assert any(a.agent_id in ("business_strategy_agent", "market_research_agent") for a in consumers)

    def test_specific_agents_exist(self, registry):
        """Verify all 17 layer-level agents exist."""
        expected = [
            "executive_vision_agent",
            "business_strategy_agent",
            "market_research_agent",
            "product_manager_agent",
            "brand_content_agent",
            "ux_ui_product_design_agent",
            "software_architect_agent",
            "senior_frontend_developer_agent",
            "senior_backend_developer_agent",
            "database_developer_agent",
            "qa_verification_agent",
            "security_compliance_agent",
            "devops_infrastructure_agent",
            "observability_reliability_agent",
            "growth_analytics_agent",
            "support_operations_agent",
            "final_arbiter_agent",
        ]
        for eid in expected:
            agent = registry.get(eid)
            assert agent is not None, f"Missing agent: {eid}"

    def test_executive_vision_agent_always_activated(self, registry):
        agent = registry.get("executive_vision_agent")
        assert agent.activation_mode == AgentActivationMode.ALWAYS

    def test_final_arbiter_runs_last(self, registry):
        agent = registry.get("final_arbiter_agent")
        assert agent.can_run_parallel is False
        assert "qa_verification_agent" in agent.dependencies
        assert "security_compliance_agent" in agent.dependencies


class TestRegistryValidation:
    def test_duplicate_ids_raise(self):
        agents = (
            AgentProfile(agent_id="dup", role_name="A", layer=1, purpose="p"),
            AgentProfile(agent_id="dup", role_name="B", layer=2, purpose="q"),
        )
        with pytest.raises(RegistryValidationError, match="Duplicate"):
            AgentRegistry(agents)

    def test_self_dependency_raises(self):
        agents = (
            AgentProfile(
                agent_id="self_ref", role_name="S", layer=1, purpose="p",
                dependencies=("self_ref",),
            ),
        )
        with pytest.raises(RegistryValidationError, match="cannot depend on itself"):
            AgentRegistry(agents)

    def test_unknown_dependency_raises(self):
        agents = (
            AgentProfile(
                agent_id="dep_missing", role_name="D", layer=1, purpose="p",
                dependencies=("nonexistent_dep",),
            ),
        )
        with pytest.raises(RegistryValidationError, match="not found"):
            AgentRegistry(agents)

    def test_unknown_reviewer_raises(self):
        agents = (
            AgentProfile(
                agent_id="bad_reviewer", role_name="B", layer=1, purpose="p",
                reviewers=("no_such_reviewer",),
            ),
        )
        with pytest.raises(RegistryValidationError, match="not found"):
            AgentRegistry(agents)

    def test_invalid_layer_raises(self):
        agents = (
            AgentProfile(agent_id="bad_layer", role_name="B", layer=99, purpose="p"),
        )
        with pytest.raises(RegistryValidationError, match="must be 1-17"):
            AgentRegistry(agents)


class TestRegistryLookups:
    @pytest.fixture
    def registry(self):
        return load_default_registry()

    def test_producers_of(self, registry):
        producers = registry.producers_of("business_brief")
        assert len(producers) >= 1

    def test_consumers_of(self, registry):
        consumers = registry.consumers_of("business_brief")
        assert len(consumers) >= 1

    def test_agent_count(self, registry):
        assert registry.agent_count == 17

    def test_agent_ids_ordered(self, registry):
        ids = registry.agent_ids
        assert isinstance(ids, tuple)
        assert len(ids) == 17

    def test_layers_returns_all_17(self, registry):
        assert registry.layers == tuple(range(1, 18))
