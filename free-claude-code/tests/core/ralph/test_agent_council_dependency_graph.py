"""Tests for Agent Council V2 dependency graph — updated for 56-agent registry."""

from __future__ import annotations

import pytest

from core.ralph.agent_council.dependency_graph import (
    blocked_by_missing,
    build_graph,
    build_reverse_graph,
    critical_path,
    detect_cycles,
    downstream_consumers,
    find_parallel_groups,
    find_parallelizable,
    topological_sort,
    upstream_dependencies,
)
from core.ralph.agent_council.registry import load_default_registry


@pytest.fixture
def registry():
    return load_default_registry()


class TestGraphConstruction:
    def test_build_graph_returns_all_agents(self, registry):
        graph = build_graph(registry)
        for agent in registry.list_all():
            assert agent.agent_id in graph

    def test_reverse_graph_maps_dependencies(self, registry):
        rev = build_reverse_graph(registry)
        pm = registry.get("product_manager")
        assert rev[pm.agent_id] == pm.dependencies

    def test_market_researcher_in_chief_vision_graph(self, registry):
        graph = build_graph(registry)
        # chief_vision_officer -> market_researcher (downstream consumer)
        assert "market_researcher" in graph["chief_vision_officer"]


class TestTopologicalSort:
    def test_topological_sort_returns_all_agents(self, registry):
        topo = topological_sort(registry)
        assert len(topo) == 56

    def test_dependencies_before_dependents(self, registry):
        topo = topological_sort(registry)
        positions = {aid: i for i, aid in enumerate(topo)}
        # product_manager depends on market_researcher and user_researcher
        assert positions["market_researcher"] < positions["product_manager"]
        assert positions["user_researcher"] < positions["product_manager"]
        # senior_frontend_developer depends on ui_designer
        assert positions["ui_designer"] < positions["senior_frontend_developer"]

    def test_chief_vision_early(self, registry):
        topo = topological_sort(registry)
        # chief_vision_officer has no deps, should be very early
        pos = topo.index("chief_vision_officer")
        assert pos < 10

    def test_final_arbiter_late(self, registry):
        topo = topological_sort(registry)
        pos = topo.index("final_arbiter")
        # Should be in the last quarter
        assert pos > len(topo) * 0.6

    def test_qa_before_final_arbiter(self, registry):
        topo = topological_sort(registry)
        positions = {aid: i for i, aid in enumerate(topo)}
        assert positions["qa_engineer"] < positions["final_arbiter"]
        assert positions["security_engineer"] < positions["final_arbiter"]


class TestCycleDetection:
    def test_no_cycles_in_default_registry(self, registry):
        cycles = detect_cycles(registry)
        assert len(cycles) == 0, f"Unexpected cycles: {cycles}"


class TestUpstreamDependencies:
    def test_product_manager_has_upstream(self, registry):
        deps = upstream_dependencies(registry, "product_manager")
        assert "chief_vision_officer" in deps
        assert "market_researcher" in deps
        assert "user_researcher" in deps

    def test_final_arbiter_has_many_upstream(self, registry):
        deps = upstream_dependencies(registry, "final_arbiter")
        assert len(deps) >= 10
        assert "qa_engineer" in deps
        assert "security_engineer" in deps

    def test_chief_vision_has_no_upstream(self, registry):
        deps = upstream_dependencies(registry, "chief_vision_officer")
        assert len(deps) == 0

    def test_returns_sorted_tuple(self, registry):
        deps = upstream_dependencies(registry, "product_manager")
        assert isinstance(deps, tuple)
        assert deps == tuple(sorted(deps))


class TestDownstreamConsumers:
    def test_chief_vision_has_many_downstream(self, registry):
        deps = downstream_consumers(registry, "chief_vision_officer")
        assert len(deps) >= 10

    def test_market_research_consumed_by_product(self, registry):
        deps = downstream_consumers(registry, "market_researcher")
        assert "product_manager" in deps
        assert "business_strategist" in deps

    def test_final_arbiter_has_no_downstream(self, registry):
        deps = downstream_consumers(registry, "final_arbiter")
        # final_arbiter is terminal, may have very few downstream consumers
        assert len(deps) <= 5


class TestParallelGroups:
    def test_returns_groups(self, registry):
        groups = find_parallel_groups(registry)
        assert len(groups) >= 1

    def test_chief_vision_in_first_group(self, registry):
        groups = find_parallel_groups(registry)
        assert "chief_vision_officer" in groups[0]

    def test_all_agents_in_some_group(self, registry):
        groups = find_parallel_groups(registry)
        all_in_groups = set()
        for g in groups:
            all_in_groups.update(g)
        assert all_in_groups == set(registry.agent_ids)


class TestFindParallelizable:
    def test_no_deps_ready_immediately(self, registry):
        activated = frozenset(registry.agent_ids)
        completed: frozenset[str] = frozenset()
        ready = find_parallelizable(registry, activated, completed)
        # Agents with no dependencies should be ready
        assert "chief_vision_officer" in ready
        assert "project_memory_keeper" in ready

    def test_with_deps_blocked(self, registry):
        activated = frozenset(registry.agent_ids)
        completed = frozenset({"chief_vision_officer"})
        ready = find_parallelizable(registry, activated, completed)
        # market_researcher only depends on chief_vision_officer -> ready
        assert "market_researcher" in ready
        # product_manager needs more -> not ready
        assert "product_manager" not in ready

    def test_agents_not_in_activated_ignored(self, registry):
        activated = frozenset({"chief_vision_officer", "market_researcher"})
        completed: frozenset[str] = frozenset()
        ready = find_parallelizable(registry, activated, completed)
        assert "chief_vision_officer" in ready
        assert "market_researcher" not in ready  # needs chief_vision


class TestBlockedByMissing:
    def test_chief_vision_blocked_by_missing_project_brief(self, registry):
        missing = blocked_by_missing(
            registry, "chief_vision_officer", frozenset(),
        )
        assert "project_brief" in missing

    def test_no_blocking_when_inputs_available(self, registry):
        missing = blocked_by_missing(
            registry, "chief_vision_officer", frozenset({"project_brief"}),
        )
        assert len(missing) == 0

    def test_market_researcher_blocked_without_brief(self, registry):
        missing = blocked_by_missing(
            registry, "market_researcher", frozenset(),
        )
        assert "business_brief" in missing


class TestCriticalPath:
    def test_critical_path_includes_activated(self, registry):
        activated = frozenset({
            "chief_vision_officer", "market_researcher",
            "product_manager", "final_arbiter",
        })
        cp = critical_path(registry, activated)
        assert "chief_vision_officer" in cp
        assert "final_arbiter" in cp
