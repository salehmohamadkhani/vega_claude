"""Agent Council V2 — Data Models.

Pure dataclass models for Agent Council V2. No LLM calls, no network access.
Based on AGENT_COUNCIL_V2_TAXONOMY.md and AGENT_COUNCIL_V2_ARTIFACT_CONTRACTS.md.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class AgentLayer(enum.Enum):
    """The 17 layers of Agent Council V2."""

    EXECUTIVE_VISION = 1
    BUSINESS_STRATEGY = 2
    MARKET_RESEARCH = 3
    PRODUCT_MANAGEMENT = 4
    BRAND_CONTENT_MARKETING = 5
    UX_UI_PRODUCT_DESIGN = 6
    SOFTWARE_ARCHITECTURE = 7
    FRONTEND_ENGINEERING = 8
    BACKEND_ENGINEERING = 9
    DATABASE_DATA_ENGINEERING = 10
    QA_TESTING_VERIFICATION = 11
    SECURITY_COMPLIANCE = 12
    DEVOPS_INFRASTRUCTURE = 13
    OBSERVABILITY_RELIABILITY = 14
    GROWTH_ANALYTICS = 15
    SUPPORT_OPERATIONS = 16
    ORCHESTRATION_ARBITRATION = 17

    @property
    def label(self) -> str:
        """Human-readable layer name."""
        _labels = {
            1: "Executive / Vision",
            2: "Business Strategy",
            3: "Market Research",
            4: "Product Management",
            5: "Brand / Content / Marketing",
            6: "UX / UI / Product Design",
            7: "Software Architecture",
            8: "Frontend Engineering",
            9: "Backend Engineering",
            10: "Database / Data Engineering",
            11: "QA / Testing / Verification",
            12: "Security / Compliance",
            13: "DevOps / Infrastructure",
            14: "Observability / Reliability",
            15: "Growth / Analytics",
            16: "Support / Operations",
            17: "Orchestration / Arbitration / Project Memory",
        }
        return _labels[self.value]

    @property
    def is_strategic(self) -> bool:
        """True for layers that primarily produce business/strategy artifacts."""
        return self.value in (1, 2, 3, 4, 5, 16)

    @property
    def is_technical(self) -> bool:
        """True for layers that primarily produce technical artifacts."""
        return self.value in (6, 7, 8, 9, 10, 11, 12, 13, 14, 17)


class AgentActivationMode(enum.Enum):
    """How an agent is activated."""

    ALWAYS = "always"
    TRIGGERED = "triggered"
    ON_DEMAND = "on_demand"
    CHECKPOINT = "checkpoint"
    BACKGROUND = "background"


class ArtifactStatus(enum.Enum):
    """Lifecycle status of an artifact."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    PRODUCED = "produced"
    VALIDATED = "validated"
    REJECTED = "rejected"
    BLOCKED = "blocked"


class EvidenceType(enum.Enum):
    """Type of evidence backing a claim or decision."""

    REPO_PATTERN = "repo_pattern"
    REPO_COMPARISON = "repo_comparison"
    ARCHITECTURAL_REFERENCE = "architectural_reference"
    TEST_RESULT = "test_result"
    AGENT_OUTPUT = "agent_output"
    RESEARCH_NOTE = "research_note"
    EXTERNAL_REFERENCE = "external_reference"


# ---------------------------------------------------------------------------
# Core data classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AgentProfile:
    """Defines a single agent in Agent Council V2.

    Mirrors the taxonomy entries in AGENT_COUNCIL_V2_TAXONOMY.md.
    """

    agent_id: str
    role_name: str
    layer: int  # 1-17
    purpose: str
    required_inputs: tuple[str, ...] = ()
    produced_artifacts: tuple[str, ...] = ()
    reviewers: tuple[str, ...] = ()
    fail_conditions: tuple[str, ...] = ()
    activation_triggers: tuple[str, ...] = ()
    activation_mode: AgentActivationMode = AgentActivationMode.ALWAYS
    can_run_parallel: bool = True
    dependencies: tuple[str, ...] = ()  # agent_ids that must complete first
    research_categories: tuple[str, ...] = ()

    def __hash__(self) -> int:
        return hash(self.agent_id)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, AgentProfile):
            return self.agent_id == other.agent_id
        if isinstance(other, str):
            return self.agent_id == other
        return False

    @property
    def layer_enum(self) -> AgentLayer:
        return AgentLayer(self.layer)


@dataclass(frozen=True)
class AgentDependency:
    """A directed edge from one agent to another.

    ``depends_on`` must complete before ``agent_id`` can start.
    """

    agent_id: str
    depends_on: str
    artifact_required: str = ""  # specific artifact needed from depends_on


@dataclass(frozen=True)
class ArtifactContract:
    """Defines a shared artifact that agents pass between each other.

    Based on AGENT_COUNCIL_V2_ARTIFACT_CONTRACTS.md.
    """

    artifact_id: str
    name: str
    owner_agent: str
    description: str = ""
    required_fields: tuple[str, ...] = ()
    consumers: tuple[str, ...] = ()  # agent_ids that consume this artifact
    validation_method: str = ""
    pass_criteria: tuple[str, ...] = ()
    fail_criteria: tuple[str, ...] = ()

    def __hash__(self) -> int:
        return hash(self.artifact_id)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, ArtifactContract):
            return self.artifact_id == other.artifact_id
        if isinstance(other, str):
            return self.artifact_id == other
        return False


@dataclass(frozen=True)
class AgentCouncilPlan:
    """A deterministic plan for which agents to activate and in what order."""

    project_type: str
    active_agents: tuple[str, ...]  # agent_ids to activate
    required_artifacts: tuple[str, ...]  # artifact_ids needed
    parallel_groups: tuple[tuple[str, ...], ...]  # groups of agents that can run together
    critical_path: tuple[str, ...]  # longest dependency chain
    missing_prerequisites: tuple[str, ...] = ()  # agents/artifacts that are needed but unavailable
    total_phases: int = 0  # computed from parallel_groups


@dataclass(frozen=True)
class AgentActivationDecision:
    """Result of asking whether an agent should activate for a project."""

    agent_id: str
    should_activate: bool
    reason: str = ""
    required_artifacts_available: bool = False
    activation_phase: int = -1  # which parallel group this agent runs in
    blocked_by: tuple[str, ...] = ()  # agent_ids or artifact_ids that block activation


@dataclass(frozen=True)
class ResearchReference:
    """A reference to a research corpus repo or pattern relevant to an agent."""

    repo_id: str
    repo_name: str = ""
    category: str = ""
    patterns: tuple[str, ...] = ()
    relevance_agent: str = ""
    relevance_level: str = "medium"  # high / medium / low
    important_files: tuple[str, ...] = ()


@dataclass(frozen=True)
class EvidenceItem:
    """A single piece of evidence supporting a claim, decision, or artifact."""

    evidence_id: str = ""
    source_path: str = ""  # e.g., "research/repos/facebook-react" or agent output path
    claim: str = ""
    evidence_type: EvidenceType = EvidenceType.REPO_PATTERN
    agent_source: str = ""  # agent_id that produced this evidence
    quality: str = "unvalidated"  # unvalidated / validated / rejected
    notes: str = ""

    def is_valid(self) -> bool:
        """Evidence is valid if it has a source, claim, and type."""
        return bool(self.source_path and self.claim and self.evidence_type.value)
