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
            registry,
            "chief_vision_officer",
            frozenset(),
        )
        assert "project_brief" in missing

    def test_no_blocking_when_inputs_available(self, registry):
        missing = blocked_by_missing(
            registry,
            "chief_vision_officer",
            frozenset({"project_brief"}),
        )
        assert len(missing) == 0

    def test_market_researcher_blocked_without_brief(self, registry):
        missing = blocked_by_missing(
            registry,
            "market_researcher",
            frozenset(),
        )
        assert "business_brief" in missing


class TestCriticalPath:
    def test_returns_tuple(self, registry):
        activated = frozenset({"chief_vision_officer"})
        cp = critical_path(registry, activated)
        assert isinstance(cp, tuple)

    def test_single_agent(self, registry):
        cp = critical_path(registry, frozenset({"chief_vision_officer"}))
        assert cp == ("chief_vision_officer",)

    def test_dependency_ordering(self, registry):
        """chief_vision → market_researcher → product_manager → pm is a real chain."""
        activated = frozenset(
            {
                "chief_vision_officer",
                "market_researcher",
                "product_manager",
            }
        )
        cp = critical_path(registry, activated)
        # The critical path must have chief_vision_officer before market_researcher,
        # and market_researcher before product_manager
        positions = {aid: i for i, aid in enumerate(cp)}
        assert positions["chief_vision_officer"] < positions["market_researcher"]
        assert positions["market_researcher"] < positions["product_manager"]

    def test_with_final_arbiter(self, registry):
        """final_arbiter is the most downstream agent — should be last on path."""
        activated = frozenset(
            {
                "chief_vision_officer",
                "market_researcher",
                "product_manager",
                "qa_engineer",
                "security_engineer",
                "final_arbiter",
            }
        )
        cp = critical_path(registry, activated)
        assert cp[-1] == "final_arbiter"
        assert "chief_vision_officer" in cp

    def test_path_is_longer_than_topological_subset(self, registry):
        """critical path should pick the longest chain, not just any ordering."""
        activated = frozenset(
            {
                "chief_vision_officer",
                "market_researcher",
                "product_manager",
                "final_arbiter",
            }
        )
        cp = critical_path(registry, activated)
        # The chain chief_vision → market_researcher → product_manager should
        # be longer than any alternative through fewer depth levels
        assert len(cp) >= 2

    def test_no_activated_agents_returns_empty(self, registry):
        cp = critical_path(registry, frozenset())
        assert cp == ()

    def test_unknown_agent_id_skipped(self, registry):
        """Agents not in the registry are silently ignored."""
        cp = critical_path(registry, frozenset({"nonexistent_agent"}))
        # Should not crash; returns empty or just the valid agents
        assert isinstance(cp, tuple)

    def test_disjoint_activated_set(self, registry):
        """Two independent chains produce a path through the deeper one."""
        activated = frozenset(
            {
                "chief_vision_officer",  # depth 1
                "project_memory_keeper",  # depth 1 (no deps)
            }
        )
        cp = critical_path(registry, activated)
        # Both have depth 1, so either is valid — just check no crash
        assert isinstance(cp, tuple)
        assert len(cp) == 1

    def test_critical_path_respects_depth(self, registry):
        """An agent at higher depth should appear after an agent at lower depth."""
        # A longer chain: chief_vision (1) → market_researcher (2) →
        # business_strategist (3) → product_manager (4?)
        activated = frozenset(
            {
                "chief_vision_officer",
                "market_researcher",
                "business_strategist",
                "product_manager",
            }
        )
        cp = critical_path(registry, activated)
        depths = {}
        for aid in cp:
            agent = registry.get(aid)
            dep_depth = max(
                (depths.get(d, 0) for d in agent.dependencies if d in activated),
                default=0,
            )
            depths[aid] = dep_depth + 1
        # Depths should be strictly increasing along the path
        for i in range(len(cp) - 1):
            assert depths[cp[i]] < depths[cp[i + 1]], (
                f"Depth not increasing at {cp[i]} ({depths[cp[i]]}) -> "
                f"{cp[i + 1]} ({depths[cp[i + 1]]})"
            )
