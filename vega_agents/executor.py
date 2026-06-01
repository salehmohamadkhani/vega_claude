"""Agent execution interface — builds and summarizes execution plans.

Builds on the registry/selector layer from U7 to produce actionable
execution plans that SEPCC can inspect, approve, or reject before any
LLM fan-out occurs.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .registry import AgentRole
from .selector import (
    AgentSelectionDecision,
    TaskProfile,
    propose_new_agent_if_needed,
    select_agents_for_task,
)


# ── Dataclasses ────────────────────────────────────────────────────────────────────


@dataclass
class AgentExecutionStep:
    """One step in an execution plan — maps to one selected agent role."""

    agent_name: str
    purpose: str
    mode: str
    requires_llm: bool
    estimated_calls: int
    approval_required: bool


@dataclass
class AgentExecutionPlan:
    """A complete execution plan produced by the planning phase.

    Describes which agents should run, in what mode, with what budget,
    and whether user approval is required before executing.
    """

    mode: str
    steps: list[AgentExecutionStep] = field(default_factory=list)
    estimated_total_calls: int = 0
    requires_user_approval: bool = False
    reason: str = ""
    proposed_new_agent: str | None = None


# ── Helpers ─────────────────────────────────────────────────────────────────────────


def _agent_requires_llm(agent: AgentRole, profile: TaskProfile) -> bool:
    """Determine whether a specific agent role needs LLM calls."""
    if agent.name == "research_scanner":
        return profile.requires_research
    if agent.name in ("guardrail_reviewer", "security_reviewer"):
        return False  # can run static/no-LLM by default
    return True


def _agent_estimated_calls(agent: AgentRole, profile: TaskProfile) -> int:
    """Estimate the number of LLM calls this agent step would consume."""
    if agent.name == "research_scanner":
        return 1 if profile.requires_research else 0
    if agent.name in ("guardrail_reviewer", "security_reviewer"):
        return 0  # static analysis — no LLM calls
    # Map cost level to call estimate
    level_map = {"low": 1, "medium": 2, "high": 4}
    return level_map.get(agent.estimated_cost_level, 1)


def _agent_approval_required(agent: AgentRole) -> bool:
    """Whether this agent step should require explicit user approval."""
    return agent.risk_level == "high"


# ── Public API ──────────────────────────────────────────────────────────────────────


def build_execution_plan(profile: TaskProfile) -> AgentExecutionPlan:
    """Build an execution plan from a task profile.

    Delegates to the selector to determine mode and agent selection,
    then wraps each selected agent into an execution step with
    estimated resource consumption.

    No network calls, no file writes, no LLM calls.
    """
    decision = select_agents_for_task(profile)

    if decision.mode == "direct":
        # Direct mode — single lightweight step only
        step = AgentExecutionStep(
            agent_name="seppc_direct",
            purpose="SEPCC plans and executes the task directly",
            mode="direct",
            requires_llm=False,
            estimated_calls=0,
            approval_required=False,
        )
        # Also surface proposed new agent from selector if any
        proposed = (
            decision.proposed_new_agent
            or propose_new_agent_if_needed(profile)
        )
        return AgentExecutionPlan(
            mode="direct",
            steps=[step],
            estimated_total_calls=0,
            requires_user_approval=False,
            reason=decision.reason,
            proposed_new_agent=proposed,
        )

    # Fanout proposed mode — one step per selected agent
    steps: list[AgentExecutionStep] = []
    total_calls = 0

    for agent in decision.selected_agents:
        llm_needed = _agent_requires_llm(agent, profile)
        calls = _agent_estimated_calls(agent, profile)
        approval = _agent_approval_required(agent)

        step = AgentExecutionStep(
            agent_name=agent.name,
            purpose=agent.purpose,
            mode="fanout",
            requires_llm=llm_needed,
            estimated_calls=calls,
            approval_required=approval,
        )
        steps.append(step)
        total_calls += calls

    proposed = (
        decision.proposed_new_agent
        or propose_new_agent_if_needed(profile)
    )
    return AgentExecutionPlan(
        mode="fanout_proposed",
        steps=steps,
        estimated_total_calls=total_calls,
        requires_user_approval=True,
        reason=decision.reason,
        proposed_new_agent=proposed,
    )


def summarize_execution_plan(plan: AgentExecutionPlan) -> str:
    """Return a concise human-readable summary of an execution plan."""
    lines: list[str] = []
    lines.append(f"Execution Plan [{plan.mode}]")
    lines.append(f"  Reason: {plan.reason}")
    lines.append(f"  Estimated LLM calls: {plan.estimated_total_calls}")
    lines.append(f"  User approval required: {'yes' if plan.requires_user_approval else 'no'}")

    if plan.steps:
        lines.append("  Selected agents:")
        for s in plan.steps:
            llm_flag = "[LLM]" if s.requires_llm else "[static]"
            lines.append(
                f"    - {s.agent_name} ({llm_flag}, ~{s.estimated_calls} calls, "
                f"approval={s.approval_required})"
            )

    if plan.proposed_new_agent:
        lines.append(f"  Proposed new agent: {plan.proposed_new_agent}")

    return "\n".join(lines)


def should_execute_fanout(plan: AgentExecutionPlan, user_approved: bool) -> bool:
    """Gate: should the fan-out execution proceed?

    Returns True only when:
      - plan is in fanout_proposed mode
      - plan requires user approval
      - user has explicitly approved
    """
    if plan.mode != "fanout_proposed":
        return False
    if not plan.requires_user_approval:
        return False
    return user_approved is True
