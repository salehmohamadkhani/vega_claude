"""Agent Council V2 — Council Plan Models.

Deterministic data models for Council Plan generation.
A Council Plan answers all 10 questions required before execution:

1. What project type is this?
2. Which agents should activate?
3. Which agents are on the critical path?
4. Which agents can run in parallel?
5. Which artifacts are required?
6. Which artifacts are missing?
7. Which research references are relevant?
8. Which evidence must be collected?
9. Which risks should block execution?
10. What should Ralph do next?

No LLM calls. No network access. Pure deterministic planning data.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class CouncilPlanNextAction(enum.Enum):
    """What Ralph Runtime should do after receiving the Council Plan."""

    READY_FOR_RUNTIME_PLANNING = "ready_for_runtime_planning"
    NEEDS_MISSING_ARTIFACTS = "needs_missing_artifacts"
    NEEDS_SCOPE_CLARIFICATION = "needs_scope_clarification"
    BLOCKED_BY_DEPENDENCY_CYCLE = "blocked_by_dependency_cycle"
    BLOCKED_BY_UNKNOWN_PROJECT_TYPE = "blocked_by_unknown_project_type"
    BLOCKED_BY_MISSING_REQUIRED_AGENT = "blocked_by_missing_required_agent"


class RiskSeverity(enum.Enum):
    """Severity of a planning risk."""

    BLOCKING = "blocking"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CouncilPlanAgentNode:
    """A single agent within a Council Plan.

    Contains just enough data for Ralph to understand the agent's role
    in the execution plan without pulling in the full AgentProfile.
    """

    agent_id: str
    role_name: str
    layer: int
    phase: int  # 0-based execution phase (parallel group index)
    depends_on: tuple[str, ...] = ()
    produces_artifacts: tuple[str, ...] = ()
    can_run_parallel: bool = True


@dataclass(frozen=True)
class CouncilPlanArtifactNode:
    """An artifact in the Council Plan.

    Tracks whether the artifact is available, produced by an agent,
    or missing (no producer active).
    """

    artifact_id: str
    name: str
    owner_agent: str = ""
    status: str = "pending"  # pending | available | missing
    consumers: tuple[str, ...] = ()
    is_critical: bool = False


@dataclass(frozen=True)
class CouncilPlanRisk:
    """A risk detected during council planning."""

    risk_id: str
    description: str
    severity: RiskSeverity = RiskSeverity.MEDIUM
    affected_agents: tuple[str, ...] = ()
    affected_artifacts: tuple[str, ...] = ()
    mitigation: str = ""


@dataclass(frozen=True)
class CouncilPlanEvidenceRequirement:
    """Evidence that must be collected before or during execution."""

    requirement_id: str
    description: str
    required_for_agent: str = ""
    required_for_artifact: str = ""
    source_hint: str = ""  # e.g. research repo or agent output
    priority: str = "medium"  # high | medium | low


@dataclass(frozen=True)
class CouncilPlanResearchReference:
    """A lightweight research reference for the council plan."""

    repo_id: str
    category: str = ""
    relevance_agent: str = ""
    relevance_level: str = "medium"
    patterns: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# Request
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CouncilPlanRequest:
    """A deterministic request to generate a Council Plan.

    Minimum fields as specified in the phase requirements.
    """

    project_goal: str
    project_type: str = ""
    constraints: tuple[str, ...] = ()
    available_artifacts: tuple[str, ...] = ()
    requested_agents: tuple[str, ...] = ()
    excluded_agents: tuple[str, ...] = ()
    research_root: str = ""
    strict_mode: bool = False


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CouncilPlanResult:
    """A complete Council Plan — the answer to all 10 planning questions.

    Minimum fields as specified in the phase requirements.
    """

    project_type: str
    project_goal: str
    active_agents: tuple[CouncilPlanAgentNode, ...]
    critical_path: tuple[str, ...]
    parallel_groups: tuple[tuple[str, ...], ...]
    required_artifacts: tuple[CouncilPlanArtifactNode, ...]
    missing_artifacts: tuple[str, ...]
    artifact_contracts: tuple[str, ...]
    research_references: tuple[CouncilPlanResearchReference, ...]
    evidence_requirements: tuple[CouncilPlanEvidenceRequirement, ...]
    risks: tuple[CouncilPlanRisk, ...]
    next_action: CouncilPlanNextAction
    is_ready_to_execute: bool
    summary: str = ""
    warnings: tuple[str, ...] = ()
    total_phases: int = 0
    total_active_agents: int = 0

    @property
    def is_blocked(self) -> bool:
        """True if the plan is blocked from execution."""
        return not self.is_ready_to_execute

    @property
    def next_action_label(self) -> str:
        """Human-readable next action label."""
        _labels: dict[CouncilPlanNextAction, str] = {
            CouncilPlanNextAction.READY_FOR_RUNTIME_PLANNING: (
                "Ready — proceed to runtime task planning"
            ),
            CouncilPlanNextAction.NEEDS_MISSING_ARTIFACTS: (
                "Blocked — missing required artifacts must be produced first"
            ),
            CouncilPlanNextAction.NEEDS_SCOPE_CLARIFICATION: (
                "Blocked — project scope needs clarification"
            ),
            CouncilPlanNextAction.BLOCKED_BY_DEPENDENCY_CYCLE: (
                "Blocked — dependency cycle detected"
            ),
            CouncilPlanNextAction.BLOCKED_BY_UNKNOWN_PROJECT_TYPE: (
                "Blocked — unknown project type"
            ),
            CouncilPlanNextAction.BLOCKED_BY_MISSING_REQUIRED_AGENT: (
                "Blocked — required agent not available"
            ),
        }
        return _labels.get(self.next_action, str(self.next_action.value))

    @property
    def agent_count_by_layer(self) -> dict[int, int]:
        """Count of active agents per layer."""
        counts: dict[int, int] = {}
        for agent in self.active_agents:
            counts[agent.layer] = counts.get(agent.layer, 0) + 1
        return counts
