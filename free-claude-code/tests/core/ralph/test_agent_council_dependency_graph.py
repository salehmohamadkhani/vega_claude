"""Tests for Agent Council V2 dependency graph."""

from __future__ import annotations

import pytest

from core.ralph.agent_council.dependency_graph import (
    blocked_by_missing,
    build_graph,
    build_reverse_graph,
    detect_cycles,
    downstream_consumers,
    find_parallel_groups,
    find_parallelizable,
    topological_sort,
    upstream_dependencies,
)
from core.ralph.agent_council.models import AgentProfile
from core.ralph.agent_council.registry import (
    AgentRegistry,
    RegistryValidationError,
    load_default_registry,
)


class TestBuildGraph:
    @pytest.fixture
    def registry(self):
        return load_default_registry()

    def test_build_graph_has_all_agents(self, registry):
        graph = build_graph(registry)
        assert len(graph) == 17
        for agent in registry.list_all():
            assert agent.agent_id in graph

    def test_executive_vision_has_downstream(self, registry):
        graph = build_graph(registry)
        downstream = graph["executive_vision_agent"]
        # business_strategy_agent depends on executive_vision_agent
        assert len(downstream) >= 1

    def test_build_reverse_graph(self, registry):
        rev = build_reverse_graph(registry)
        # final_arbiter_agent depends on qa, security, devops
        assert len(rev["final_arbiter_agent"]) >= 3


class TestTopologicalSort:
    @pytest.fixture
    def registry(self):
        return load_default_registry()

    def test_returns_all_agents(self, registry):
        topo = topological_sort(registry)
        assert len(topo) == 17

    def test_dependencies_come_before_consumers(self, registry):
        topo = topological_sort(registry)
        positions = {aid: i for i, aid in enumerate(topo)}
        for agent in registry.list_all():
            for dep_id in agent.dependencies:
                assert positions[dep_id] < positions[agent.agent_id], (
                    f"{dep_id} must come before {agent.agent_id}"
                )

    def test_executive_vision_first_or_early(self, registry):
        topo = topological_sort(registry)
        # Executive vision has no dependencies, should be early
        pos = topo.index("executive_vision_agent")
        assert pos <= 2, "executive_vision_agent should be among first 3"

    def test_final_arbiter_last_or_late(self, registry):
        topo = topological_sort(registry)
        pos = topo.index("final_arbiter_agent")
        assert pos >= 12, "final_arbiter_agent should be among last 5"


class TestCycleDetection:
    @pytest.fixture
    def registry(self):
        return load_default_registry()

    def test_no_cycles_in_default_registry(self, registry):
        cycles = detect_cycles(registry)
        assert cycles == [], f"Unexpected cycles: {cycles}"

    def test_detects_simple_cycle(self):
        """A -> B -> A creates a cycle."""
        agents = (
            AgentProfile(
                agent_id="a", role_name="A", layer=1, purpose="p",
                dependencies=("b",),
            ),
            AgentProfile(
                agent_id="b", role_name="B", layer=2, purpose="q",
                dependencies=("a",),
            ),
        )
        registry = AgentRegistry(agents)
        cycles = detect_cycles(registry)
        assert len(cycles) >= 1

    def test_self_cycle_not_allowed(self):
        """Self-dependencies are caught by registry validation."""
        with pytest.raises(RegistryValidationError):
            agents = (
                AgentProfile(
                    agent_id="a", role_name="A", layer=1, purpose="p",
                    dependencies=("a",),
                ),
            )
            AgentRegistry(agents)


class TestUpstreamDependencies:
    @pytest.fixture
    def registry(self):
        return load_default_registry()

    def test_exec_vision_has_no_upstream(self, registry):
        deps = upstream_dependencies(registry, "executive_vision_agent")
        assert deps == ()

    def test_product_manager_has_upstream(self, registry):
        deps = upstream_dependencies(registry, "product_manager_agent")
        assert "executive_vision_agent" in deps
        assert "market_research_agent" in deps


class TestDownstreamConsumers:
    @pytest.fixture
    def registry(self):
        return load_default_registry()

    def test_exec_vision_has_many_consumers(self, registry):
        consumers = downstream_consumers(registry, "executive_vision_agent")
        assert len(consumers) >= 2

    def test_final_arbiter_has_no_downstream(self, registry):
        consumers = downstream_consumers(registry, "final_arbiter_agent")
        assert consumers == ()


class TestParallelGroups:
    @pytest.fixture
    def registry(self):
        return load_default_registry()

    def test_returns_groups(self, registry):
        groups = find_parallel_groups(registry)
        assert len(groups) >= 1
        # Each group should have at least one agent
        for g in groups:
            assert len(g) >= 1

    def test_first_group_contains_no_dep_agents(self, registry):
        groups = find_parallel_groups(registry)
        first = set(groups[0])
        # Agents with no dependencies should be in group 0
        for agent in registry.list_all():
            if not agent.dependencies:
                assert agent.agent_id in first, (
                    f"{agent.agent_id} has no deps but is not in group 0"
                )

    def test_final_arbiter_in_last_group(self, registry):
        groups = find_parallel_groups(registry)
        last = set(groups[-1])
        assert "final_arbiter_agent" in last or len(groups) <= 2


class TestFindParallelizable:
    @pytest.fixture
    def registry(self):
        return load_default_registry()

    def test_all_ready_when_none_completed(self, registry):
        all_ids = frozenset(registry.agent_ids)
        ready = find_parallelizable(registry, all_ids, frozenset())
        # Only agents with no dependencies should be ready
        for aid in ready:
            agent = registry.get(aid)
            deps_in_set = [d for d in agent.dependencies if d in all_ids]
            assert len(deps_in_set) == 0, f"{aid} has unmet deps: {deps_in_set}"

    def test_more_ready_as_deps_complete(self, registry):
        all_ids = frozenset(registry.agent_ids)
        # Complete executive_vision_agent
        completed = frozenset({"executive_vision_agent"})
        ready = find_parallelizable(registry, all_ids, completed)
        # Now agents that only depend on exec_vision should be ready
        assert len(ready) >= 1

    def test_all_ready_when_all_completed(self, registry):
        all_ids = frozenset(registry.agent_ids)
        ready = find_parallelizable(registry, all_ids, all_ids)
        assert ready == ()  # none left to run


class TestBlockedByMissing:
    @pytest.fixture
    def registry(self):
        return load_default_registry()

    def test_nothing_blocked_when_all_artifacts_available(self, registry):
        agent = registry.get("product_manager_agent")
        all_arts = frozenset(agent.required_inputs)
        blocked = blocked_by_missing(registry, "product_manager_agent", all_arts)
        assert blocked == ()

    def test_all_blocked_when_no_artifacts(self, registry):
        blocked = blocked_by_missing(registry, "product_manager_agent", frozenset())
        assert len(blocked) >= 2  # needs business_brief and market research

    def test_some_blocked_when_partial_artifacts(self, registry):
        blocked = blocked_by_missing(
            registry, "product_manager_agent",
            frozenset({"business_brief"}),
        )
        assert len(blocked) >= 1
        assert "business_brief" not in blocked
