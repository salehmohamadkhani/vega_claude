"""FCC-native agent profile templates.

Defines default agent role profiles without copying ``.github/agents``.
Profiles describe intent, responsibilities, and constraints — no model
calls, no provider calls, no network access.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .models import _new_id
from .roles import AgentRole
from .workspace import RalphWorkspace


class AgentProfileError(Exception):
    """Base error for agent profile operations."""


@dataclass
class AgentProfile:
    """Template defining an agent role's intent and constraints."""

    id: str = field(default_factory=_new_id)
    agent_role: str = "doer"
    model_role: str = "doer"
    name: str = ""
    description: str = ""
    responsibilities: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    prompt_template: str = ""


# Default profile templates — deterministic, no external data.
_DEFAULT_PROFILES_DATA: list[dict[str, Any]] = [
    {
        "agent_role": "planner",
        "model_role": "planner",
        "name": "Planner",
        "description": "Analyses goals and generates structured task plans.",
        "responsibilities": [
            "Break high-level goals into concrete tasks",
            "Identify dependencies and risks",
            "Define acceptance criteria",
        ],
        "constraints": [
            "Do not implement any task",
            "Do not write code",
        ],
        "prompt_template": (
            "You are the Planner. Analyse the goal and produce a task plan "
            "with clear acceptance criteria and verification steps."
        ),
    },
    {
        "agent_role": "architect",
        "model_role": "planner",
        "name": "Architect",
        "description": "Maps codebase context and designs implementation approach.",
        "responsibilities": [
            "Map relevant codebase areas",
            "Document existing patterns",
            "Design implementation approach",
        ],
        "constraints": [
            "Do not implement changes directly",
            "Document all assumptions",
        ],
        "prompt_template": (
            "You are the Architect. Analyse the codebase and design the "
            "implementation approach for the assigned tasks."
        ),
    },
    {
        "agent_role": "doer",
        "model_role": "doer",
        "name": "Doer",
        "description": "Implements task changes in the codebase.",
        "responsibilities": [
            "Write implementation code",
            "Write tests for new code",
            "Fix identified issues",
        ],
        "constraints": [
            "All code must pass linting",
            "Tests must pass before marking complete",
        ],
        "prompt_template": (
            "You are the Doer. Implement the changes required by the task "
            "following the architecture guidance."
        ),
    },
    {
        "agent_role": "critic",
        "model_role": "critic",
        "name": "Critic",
        "description": "Reviews implementation quality and verification results.",
        "responsibilities": [
            "Review verification command results",
            "Check acceptance criteria are met",
            "Flag quality concerns",
        ],
        "constraints": [
            "Do not modify code",
            "Be objective and specific in feedback",
        ],
        "prompt_template": (
            "You are the Critic. Review the implementation and verification "
            "results against acceptance criteria."
        ),
    },
    {
        "agent_role": "verifier",
        "model_role": "doer",
        "name": "Verifier",
        "description": "Runs verification commands and smoke tests.",
        "responsibilities": [
            "Execute verification commands",
            "Run smoke tests",
            "Report pass/fail results",
        ],
        "constraints": [
            "Do not modify implementation",
            "Report all failures accurately",
        ],
        "prompt_template": (
            "You are the Verifier. Execute verification commands and report "
            "results against the task's acceptance criteria."
        ),
    },
    {
        "agent_role": "debugger",
        "model_role": "debugger",
        "name": "Debugger",
        "description": "Diagnoses and fixes failing tasks.",
        "responsibilities": [
            "Diagnose root cause of failures",
            "Apply targeted fixes",
            "Re-run verification after fixes",
        ],
        "constraints": [
            "Change only what is necessary to fix the issue",
            "Document root cause in summary",
        ],
        "prompt_template": (
            "You are the Debugger. Diagnose the failure, apply targeted fixes, "
            "and verify the resolution."
        ),
    },
    {
        "agent_role": "arbiter",
        "model_role": "critic",
        "name": "Arbiter",
        "description": "Resolves disputes between Doer and Critic.",
        "responsibilities": [
            "Evaluate critic feedback against implementation",
            "Decide approve/retry/escalate",
            "Track iteration limits",
        ],
        "constraints": [
            "Do not implement changes",
            "Base decisions on objective evidence",
        ],
        "prompt_template": (
            "You are the Arbiter. Evaluate the critic's feedback against the "
            "implementation and decide the next action."
        ),
    },
    {
        "agent_role": "summarizer",
        "model_role": "summarizer",
        "name": "Summarizer",
        "description": "Documents results and generates reports.",
        "responsibilities": [
            "Summarise task outcomes",
            "Document decisions made",
            "Generate readable reports",
        ],
        "constraints": [
            "Do not modify implementation",
            "Be concise and accurate",
        ],
        "prompt_template": (
            "You are the Summarizer. Document the task outcome, key decisions, "
            "and any remaining issues."
        ),
    },
]


class AgentProfileRegistry:
    """Registry of FCC-native agent role profiles.

    Profiles are deterministic — no external data, no network calls,
    no provider configuration.
    """

    def __init__(self, workspace: RalphWorkspace | None = None) -> None:
        self._workspace = workspace or RalphWorkspace()
        self._profiles: dict[str, AgentProfile] = {}
        self._load_defaults()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def default_profiles(self) -> list[AgentProfile]:
        """Return all default agent profiles."""
        return list(self._profiles.values())

    def get_profile(self, agent_role: AgentRole) -> AgentProfile:
        """Get the profile for a given agent role."""
        role_str = agent_role.value
        profile = self._profiles.get(role_str)
        if profile is None:
            raise AgentProfileError(f"No profile found for agent role: {role_str}")
        return profile

    def list_profiles(self) -> list[AgentProfile]:
        """List all registered profiles (default + any added)."""
        return list(self._profiles.values())

    def save_profiles(self, profiles: list[AgentProfile] | None = None) -> list[Path]:
        """Persist profiles as JSON files under ``.fcc-ralph/agents/``.

        If ``profiles`` is None, saves all default profiles.
        """
        to_save = profiles or self.default_profiles()
        saved: list[Path] = []
        for profile in to_save:
            data: dict[str, Any] = {
                "id": profile.id,
                "agent_role": profile.agent_role,
                "model_role": profile.model_role,
                "name": profile.name,
                "description": profile.description,
                "responsibilities": list(profile.responsibilities),
                "constraints": list(profile.constraints),
                "prompt_template": profile.prompt_template,
            }
            relative = f"agents/{profile.agent_role}.json"
            saved.append(self._workspace.write_json(relative, data))
        return saved

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_defaults(self) -> None:
        """Load default profile templates into the registry."""
        for data in _DEFAULT_PROFILES_DATA:
            role_str = data["agent_role"]
            model_role_str = data["model_role"]
            profile = AgentProfile(
                id=f"profile-{role_str}",
                agent_role=role_str,
                model_role=model_role_str,
                name=data["name"],
                description=data["description"],
                responsibilities=list(data["responsibilities"]),
                constraints=list(data["constraints"]),
                prompt_template=data["prompt_template"],
            )
            self._profiles[role_str] = profile
