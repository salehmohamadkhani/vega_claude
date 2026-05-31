"""Agent selector — evaluates task risk and selects appropriate agents."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from .registry import AgentRole, find_agent_role, get_default_agent_registry

MAX_FANOUT_AGENTS = 3


@dataclass
class TaskProfile:
    task_text: str = ""
    touched_files_count: int = 0
    touches_auth: bool = False
    touches_secrets: bool = False
    touches_networking: bool = False
    touches_deployment: bool = False
    requires_research: bool = False
    user_requested_fanout: bool = False
    direct_attempt_failed: bool = False


@dataclass
class AgentSelectionDecision:
    mode: str = "direct"
    selected_agents: list[AgentRole] = field(default_factory=list)
    reason: str = ""
    estimated_cost_level: str = "low"
    requires_user_approval: bool = False
    proposed_new_agent: str | None = None


def should_escalate_to_fanout(profile: TaskProfile) -> bool:
    criteria_met = 0
    if profile.touched_files_count > 3:
        criteria_met += 1
    if profile.touches_auth or profile.touches_secrets:
        criteria_met += 1
    if profile.touches_networking or profile.touches_deployment:
        criteria_met += 1
    if profile.requires_research:
        criteria_met += 1
    if profile.direct_attempt_failed:
        criteria_met += 1
    if profile.user_requested_fanout:
        criteria_met += 1
    return criteria_met >= 1


def _cost_level(profile: TaskProfile) -> str:
    score = 0
    if profile.touches_auth or profile.touches_secrets:
        score += 2
    if profile.touches_networking or profile.touches_deployment:
        score += 1
    if profile.requires_research:
        score += 1
    if profile.direct_attempt_failed:
        score += 2
    if profile.touched_files_count > 5:
        score += 1
    if score >= 4:
        return "high"
    if score >= 2:
        return "medium"
    return "low"


def select_agents_for_task(profile: TaskProfile) -> AgentSelectionDecision:
    if should_escalate_to_fanout(profile):
        selected: list[AgentRole] = []
        registry = get_default_agent_registry()
        want_security = profile.touches_auth or profile.touches_secrets or profile.touches_networking or profile.touches_deployment

        # Phase 1: pick mandatory conditional agents first
        for role in registry:
            if len(selected) >= MAX_FANOUT_AGENTS:
                break
            if role.name == "security_reviewer" and want_security:
                selected.append(role)
            elif role.name == "research_scanner" and profile.requires_research:
                selected.append(role)
            elif role.name == "guardrail_reviewer" and (profile.direct_attempt_failed or want_security):
                selected.append(role)

        # Phase 2: fill remaining slots with default-enabled agents
        for role in registry:
            if len(selected) >= MAX_FANOUT_AGENTS:
                break
            if role.default_enabled and role not in selected:
                selected.append(role)

        reasons = []
        if profile.touched_files_count > 3:
            reasons.append(f"touches {profile.touched_files_count} modules")
        if profile.touches_auth or profile.touches_secrets:
            reasons.append("auth/secrets involvement")
        if profile.touches_networking or profile.touches_deployment:
            reasons.append("network/deployment change")
        if profile.requires_research:
            reasons.append("research required")
        if profile.direct_attempt_failed:
            reasons.append("direct attempt previously failed")
        if profile.user_requested_fanout:
            reasons.append("user requested fan-out")

        return AgentSelectionDecision(
            mode="fanout_proposed",
            selected_agents=selected,
            reason="Escalation triggered: " + "; ".join(reasons),
            estimated_cost_level=_cost_level(profile),
            requires_user_approval=True,
        )

    default_agents = [r for r in get_default_agent_registry() if r.default_enabled]
    return AgentSelectionDecision(
        mode="direct",
        selected_agents=default_agents[:MAX_FANOUT_AGENTS],
        reason="Low-risk task; direct SEPCC mode sufficient",
        estimated_cost_level=_cost_level(profile),
        requires_user_approval=False,
    )


def propose_new_agent_if_needed(
    profile: TaskProfile,
    registry: list[AgentRole] | None = None,
) -> str | None:
    if registry is None:
        registry = get_default_agent_registry()
    existing_names = {r.name for r in registry}

    if profile.touches_deployment and "deployment_agent" not in existing_names:
        return (
            "Proposed new agent: deployment_agent — reviews deployment "
            "config changes (Docker, Caddy, env, ports). "
            "Would be auto-activated by touches_deployment."
        )
    if profile.touched_files_count > 10 and "coverage_auditor" not in existing_names:
        return (
            "Proposed new agent: coverage_auditor — scans all touched files "
            "for test coverage gaps. Would be auto-activated when >10 files."
        )
    return None
