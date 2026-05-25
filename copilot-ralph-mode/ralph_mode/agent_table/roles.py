"""Agent roles for the deliberation protocol.

Provides the default three-agent triangle (Doer, Critic, Arbiter) and a
registry that allows custom roles for N-agent tables.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

# ---------------------------------------------------------------------------
# Role Constants (backwards-compatible)
# ---------------------------------------------------------------------------

ROLE_DOER = "doer"
ROLE_CRITIC = "critic"
ROLE_ARBITER = "arbiter"

ALL_ROLES = (ROLE_DOER, ROLE_CRITIC, ROLE_ARBITER)


# ---------------------------------------------------------------------------
# AgentRole Dataclass
# ---------------------------------------------------------------------------


@dataclass
class AgentRole:
    """Describes an agent's role and capabilities.

    Attributes:
        name: Unique role identifier (e.g. "doer", "critic").
        display_name: Human-readable name.
        emoji: Display emoji for logs.
        description: What this agent does.
        can_plan: Whether the role can submit plans.
        can_critique: Whether the role can submit critiques.
        can_decide: Whether the role has decision authority.
        can_implement: Whether the role can submit implementations.
        can_vote: Whether the role can participate in consensus voting.
        trust_weight: Base trust weight for consensus scoring (0.0-1.0).
        tags: Arbitrary tags for filtering.
    """

    name: str
    display_name: str = ""
    emoji: str = ""
    description: str = ""
    can_plan: bool = False
    can_critique: bool = False
    can_decide: bool = False
    can_implement: bool = False
    can_vote: bool = True
    trust_weight: float = 1.0
    tags: Set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        if not self.display_name:
            self.display_name = self.name.title()


# ---------------------------------------------------------------------------
# Default Roles
# ---------------------------------------------------------------------------

DOER_ROLE = AgentRole(
    name=ROLE_DOER,
    display_name="Doer",
    emoji="🛠️",
    description="Implements tasks, writes code, and executes changes.",
    can_plan=True,
    can_implement=True,
    can_vote=True,
    trust_weight=0.8,
    tags={"implementation", "execution"},
)

CRITIC_ROLE = AgentRole(
    name=ROLE_CRITIC,
    display_name="Critic",
    emoji="🔍",
    description="Reviews plans and code, provides constructive critique.",
    can_critique=True,
    can_vote=True,
    trust_weight=0.9,
    tags={"review", "quality"},
)

ARBITER_ROLE = AgentRole(
    name=ROLE_ARBITER,
    display_name="Arbiter",
    emoji="⚖️",
    description="Makes final decisions and resolves disputes.",
    can_decide=True,
    can_vote=True,
    trust_weight=1.0,
    tags={"decision", "authority"},
)

DEFAULT_ROLES: Dict[str, AgentRole] = {
    ROLE_DOER: DOER_ROLE,
    ROLE_CRITIC: CRITIC_ROLE,
    ROLE_ARBITER: ARBITER_ROLE,
}


# ---------------------------------------------------------------------------
# RoleRegistry
# ---------------------------------------------------------------------------


class RoleRegistry:
    """Registry of all available agent roles.

    Allows custom roles to be added for N-agent tables while
    ensuring backwards compatibility with the default 3 roles.
    """

    def __init__(self) -> None:
        self._roles: Dict[str, AgentRole] = dict(DEFAULT_ROLES)

    def register(self, role: AgentRole) -> None:
        """Register a new agent role."""
        self._roles[role.name] = role

    def get(self, name: str) -> Optional[AgentRole]:
        """Get a role by name."""
        return self._roles.get(name)

    def get_or_raise(self, name: str) -> AgentRole:
        """Get a role by name or raise ValueError."""
        role = self._roles.get(name)
        if role is None:
            available = ", ".join(sorted(self._roles.keys()))
            raise ValueError(f"Unknown role: '{name}'. Available roles: {available}")
        return role

    def all_roles(self) -> List[AgentRole]:
        """Return all registered roles."""
        return list(self._roles.values())

    def role_names(self) -> List[str]:
        """Return all registered role names."""
        return list(self._roles.keys())

    def has(self, name: str) -> bool:
        """Check if a role is registered."""
        return name in self._roles

    def emoji_for(self, name: str) -> str:
        """Get the emoji for a role, or empty string."""
        role = self._roles.get(name)
        return role.emoji if role else ""

    def remove(self, name: str) -> bool:
        """Remove a custom role. Cannot remove default roles."""
        if name in DEFAULT_ROLES:
            raise ValueError(f"Cannot remove default role: {name}")
        return self._roles.pop(name, None) is not None

    def __len__(self) -> int:
        return len(self._roles)

    def __contains__(self, name: str) -> bool:
        return name in self._roles
