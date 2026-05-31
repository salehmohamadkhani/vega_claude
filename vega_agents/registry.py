"""Agent registry — defines built-in agent roles and provides lookup."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class AgentRole:
    """One agent role in the Vega agent runtime."""

    name: str
    purpose: str
    default_enabled: bool = True
    activation_keywords: tuple[str, ...] = ()
    risk_level: str = "low"
    max_parallel: int = 1
    estimated_cost_level: str = "low"


def _build_registry() -> list[AgentRole]:
    return [
        AgentRole(
            name="codebase_auditor",
            purpose="Scan the worktree structure, imports, and existing patterns. Read-only.",
            default_enabled=True,
            risk_level="low",
            max_parallel=1,
            estimated_cost_level="low",
        ),
        AgentRole(
            name="implementation_planner",
            purpose="Propose exact file changes combining audit and research findings.",
            default_enabled=True,
            risk_level="medium",
            max_parallel=1,
            estimated_cost_level="medium",
        ),
        AgentRole(
            name="test_planner",
            purpose="Design tests for the proposed implementation. Identify coverage gaps.",
            default_enabled=True,
            risk_level="low",
            max_parallel=1,
            estimated_cost_level="low",
        ),
        AgentRole(
            name="guardrail_reviewer",
            purpose="Validate plan against allowed paths, rules, and secrets.",
            default_enabled=True,
            activation_keywords=("risky", "security", "failed", "blocked"),
            risk_level="low",
            max_parallel=1,
            estimated_cost_level="low",
        ),
        AgentRole(
            name="research_scanner",
            purpose="Read research repos for relevant patterns. Read-only.",
            default_enabled=False,
            activation_keywords=("research", "pattern", "example", "reference"),
            risk_level="low",
            max_parallel=1,
            estimated_cost_level="medium",
        ),
        AgentRole(
            name="security_reviewer",
            purpose="Review for auth, secrets, network, or deployment risks.",
            default_enabled=False,
            activation_keywords=("auth", "secret", "permission", "network", "deploy"),
            risk_level="high",
            max_parallel=1,
            estimated_cost_level="medium",
        ),
    ]


_DEFAULT_REGISTRY: list[AgentRole] | None = None


def get_default_agent_registry() -> list[AgentRole]:
    global _DEFAULT_REGISTRY
    if _DEFAULT_REGISTRY is None:
        _DEFAULT_REGISTRY = _build_registry()
    return list(_DEFAULT_REGISTRY)


def find_agent_role(name: str) -> AgentRole | None:
    for role in get_default_agent_registry():
        if role.name == name:
            return role
    return None


def list_enabled_agents() -> list[AgentRole]:
    return [r for r in get_default_agent_registry() if r.default_enabled]
