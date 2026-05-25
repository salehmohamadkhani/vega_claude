"""Agent and model role definitions for the Ralph Runtime.

Roles are abstract — they do not reference provider names, API keys,
or any FCC-specific configuration. Future phases will map ModelRole
to concrete FCC providers through a ModelRoleRouter.
"""

from __future__ import annotations

import enum
from typing import Final


class AgentRole(enum.Enum):
    """Roles an agent can assume during task execution.

    These are orthogonal to ModelRole: one AgentRole may be backed by
    different ModelRoles depending on the phase and configuration.
    """

    PLANNER = "planner"
    ARCHITECT = "architect"
    DOER = "doer"
    CRITIC = "critic"
    VERIFIER = "verifier"
    DEBUGGER = "debugger"
    ARBITER = "arbiter"
    SUMMARIZER = "summarizer"


class ModelRole(enum.Enum):
    """Abstract model capability roles.

    These describe what the model is used for, not which provider/model
    serves it. The FCC ModelRoleRouter (Phase 2) resolves these to
    concrete provider/model strings via FCC Settings.
    """

    PLANNER = "planner"
    DOER = "doer"
    CRITIC = "critic"
    DEBUGGER = "debugger"
    SUMMARIZER = "summarizer"


# Default mapping: which ModelRole typically backs each AgentRole.
# This is a hint — the ModelRoleRouter may override it.
AGENT_TO_MODEL_ROLE: Final[dict[AgentRole, ModelRole]] = {
    AgentRole.PLANNER: ModelRole.PLANNER,
    AgentRole.ARCHITECT: ModelRole.PLANNER,
    AgentRole.DOER: ModelRole.DOER,
    AgentRole.CRITIC: ModelRole.CRITIC,
    AgentRole.VERIFIER: ModelRole.DOER,
    AgentRole.DEBUGGER: ModelRole.DEBUGGER,
    AgentRole.ARBITER: ModelRole.CRITIC,
    AgentRole.SUMMARIZER: ModelRole.SUMMARIZER,
}

# Human-readable labels for AgentRole values.
AGENT_ROLE_LABELS: Final[dict[AgentRole, str]] = {
    AgentRole.PLANNER: "Planner",
    AgentRole.ARCHITECT: "Architect",
    AgentRole.DOER: "Doer",
    AgentRole.CRITIC: "Critic",
    AgentRole.VERIFIER: "Verifier",
    AgentRole.DEBUGGER: "Debugger",
    AgentRole.ARBITER: "Arbiter",
    AgentRole.SUMMARIZER: "Summarizer",
}
