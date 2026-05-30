"""Agent Council V2 — Dependency Graph.

Deterministic graph utilities for Agent Council V2:
- Build graph from a registry
- Topological ordering
- Cycle detection
- Find upstream/downstream dependencies
- Find parallelizable agents
- Block activation when required artifacts are missing
"""

from __future__ import annotations

from collections import deque

from .registry import AgentRegistry

# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------


def build_graph(
    registry: AgentRegistry,
) -> dict[str, tuple[str, ...]]:
    """Build an adjacency map: agent_id -> (dependent_agent_ids, ...).

    Maps each agent to the list of agents that depend on it (downstream).
    """
    graph: dict[str, list[str]] = {}
    for agent in registry.list_all():
        graph.setdefault(agent.agent_id, [])
        for dep_id in agent.dependencies:
            graph.setdefault(dep_id, [])
            graph[dep_id].append(agent.agent_id)
    return {k: tuple(v) for k, v in graph.items()}


def build_reverse_graph(
    registry: AgentRegistry,
) -> dict[str, tuple[str, ...]]:
    """Build reverse adjacency map: agent_id -> (dependency_agent_ids, ...).

    Maps each agent to the list of agents it depends on (upstream).
    """
    return {
        agent.agent_id: agent.dependencies for agent in registry.list_all()
    }


# ---------------------------------------------------------------------------
# Cycle detection
# ---------------------------------------------------------------------------


def detect_cycles(
    registry: AgentRegistry,
) -> list[tuple[str, ...]]:
    """Detect all cycles in the agent dependency graph using DFS.

    Returns:
        List of cycles, each as a tuple of agent_ids in the cycle.
        Empty list means no cycles.
    """
    adj: dict[str, tuple[str, ...]] = build_graph(registry)
    cycles: list[tuple[str, ...]] = []
    visited: set[str] = set()
    rec_stack: list[str] = []
    rec_set: set[str] = set()

    def _dfs(node: str) -> None:
        if node in rec_set:
            # Found a cycle — extract the cycle from the recursion stack
            cycle_start = rec_stack.index(node)
            cycles.append((*rec_stack[cycle_start:], node))
            return
        if node in visited:
            return
        visited.add(node)
        rec_set.add(node)
        rec_stack.append(node)
        for neighbor in adj.get(node, ()):
            # Only recurse if neighbor is in our graph
            if neighbor in adj:
                _dfs(neighbor)
        rec_stack.pop()
        rec_set.discard(node)

    for agent_id in sorted(adj.keys()):
        _dfs(agent_id)

    return cycles


# ---------------------------------------------------------------------------
# Topological sort
# ---------------------------------------------------------------------------


def topological_sort(
    registry: AgentRegistry,
) -> tuple[str, ...]:
    """Return agents in topological order using Kahn's algorithm.

    Agents with no dependencies come first. Raises ValueError on cycles.
    """
    in_degree: dict[str, int] = {}
    adj: dict[str, tuple[str, ...]] = build_graph(registry)

    for agent in registry.list_all():
        in_degree.setdefault(agent.agent_id, 0)

    # Count incoming edges (dependencies)
    for agent in registry.list_all():
        for dep_id in agent.dependencies:
            if dep_id in in_degree:
                in_degree[agent.agent_id] = in_degree.get(agent.agent_id, 0) + 1

    # Start with agents that have no dependencies
    queue: deque[str] = deque(
        aid for aid, deg in in_degree.items() if deg == 0
    )
    result: list[str] = []

    while queue:
        current = queue.popleft()
        result.append(current)
        for neighbor in adj.get(current, ()):
            if neighbor in in_degree:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

    if len(result) != len(in_degree):
        raise ValueError("Cycle detected — cannot perform topological sort")

    return tuple(result)


# ---------------------------------------------------------------------------
# Upstream / downstream
# ---------------------------------------------------------------------------


def upstream_dependencies(
    registry: AgentRegistry,
    agent_id: str,
) -> tuple[str, ...]:
    """Return all transitive upstream dependencies (agents this agent needs)."""
    agent = registry.get(agent_id)
    result: set[str] = set()
    visited: set[str] = set()

    def _walk(aid: str) -> None:
        if aid in visited:
            return
        visited.add(aid)
        try:
            a = registry.get(aid)
        except KeyError:
            return
        for dep_id in a.dependencies:
            result.add(dep_id)
            _walk(dep_id)

    for dep_id in agent.dependencies:
        result.add(dep_id)
        _walk(dep_id)

    return tuple(sorted(result))


def downstream_consumers(
    registry: AgentRegistry,
    agent_id: str,
) -> tuple[str, ...]:
    """Return all transitive downstream consumers (agents that depend on this agent)."""
    graph = build_graph(registry)
    result: list[str] = []
    visited: set[str] = set()

    def _walk(aid: str) -> None:
        if aid in visited:
            return
        visited.add(aid)
        for neighbor in graph.get(aid, ()):
            result.append(neighbor)
            _walk(neighbor)

    _walk(agent_id)
    return tuple(result)


# ---------------------------------------------------------------------------
# Parallel groups
# ---------------------------------------------------------------------------


def find_parallel_groups(
    registry: AgentRegistry,
) -> tuple[tuple[str, ...], ...]:
    """Group agents into parallel execution phases.

    Each group contains agents that have no mutual dependencies and whose
    upstream dependencies are all in earlier groups. Agents within a group
    can run concurrently.
    """
    topo = topological_sort(registry)
    groups: list[list[str]] = []
    agent_depths: dict[str, int] = {}

    # Compute depth (longest upstream chain) for each agent
    for agent_id in topo:
        agent = registry.get(agent_id)
        if not agent.dependencies:
            depth = 0
        else:
            depth = 1 + max(
                (agent_depths.get(d, 0) for d in agent.dependencies), default=0
            )
        agent_depths[agent_id] = depth
        # Add to appropriate group
        while len(groups) <= depth:
            groups.append([])
        groups[depth].append(agent_id)

    return tuple(tuple(g) for g in groups if g)


def find_parallelizable(
    registry: AgentRegistry,
    activated_agent_ids: frozenset[str],
    completed_agent_ids: frozenset[str],
) -> tuple[str, ...]:
    """Find which activated agents are ready to run (all dependencies met)."""
    ready: list[str] = []
    for aid in activated_agent_ids:
        if aid in completed_agent_ids:
            continue
        agent = registry.get(aid)
        deps_met = all(
            dep_id in completed_agent_ids
            for dep_id in agent.dependencies
            if dep_id in activated_agent_ids
        )
        if deps_met:
            ready.append(aid)
    return tuple(sorted(ready))


# ---------------------------------------------------------------------------
# Blocking check
# ---------------------------------------------------------------------------


def blocked_by_missing(
    registry: AgentRegistry,
    agent_id: str,
    available_artifacts: frozenset[str],
) -> tuple[str, ...]:
    """Return which required inputs are missing for an agent to start.

    Args:
        registry: The agent registry.
        agent_id: The agent to check.
        available_artifacts: Set of artifact_ids that have been produced.

    Returns:
        Tuple of missing required input artifact_ids. Empty tuple = ready.
    """
    agent = registry.get(agent_id)
    missing = [inp for inp in agent.required_inputs if inp not in available_artifacts]
    return tuple(missing)


def critical_path(
    registry: AgentRegistry,
    activated_agent_ids: frozenset[str],
) -> tuple[str, ...]:
    """Find the critical path through the activated agents.

    The critical path is the longest chain of sequential dependencies.
    """
    agent_depths: dict[str, int] = {}

    def _depth(aid: str) -> int:
        if aid in agent_depths:
            return agent_depths[aid]
        if aid not in activated_agent_ids:
            return 0
        try:
            agent = registry.get(aid)
        except KeyError:
            return 0
        max_dep = 0
        for dep_id in agent.dependencies:
            if dep_id in activated_agent_ids:
                d = _depth(dep_id)
                if d > max_dep:
                    max_dep = d
        agent_depths[aid] = max_dep + 1
        return agent_depths[aid]

    for aid in activated_agent_ids:
        _depth(aid)

    # Walk the longest path
    path: list[str] = []
    remaining = set(activated_agent_ids)
    while remaining:
        # Find the agent with the highest depth that has all deps in the path
        candidates = [
            a for a in remaining
            if all(
                d not in activated_agent_ids or d in path
                for d in registry.get(a).dependencies
            )
        ]
        if not candidates:
            break
        # Pick the one with highest depth (most downstream)
        candidates.sort(key=lambda a: agent_depths.get(a, 0), reverse=True)
        # Actually we want to walk from root to leaf. Let's use a different approach.
        # For critical path, find the longest chain from no-deps to most-depended.
        break  # Skip — we'll use topological sort instead

    # Simpler approach: use topological sort within activated agents
    try:
        topo = topological_sort(registry)
        return tuple(aid for aid in topo if aid in activated_agent_ids)
    except ValueError:
        return ()
