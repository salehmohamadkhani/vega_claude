"""Agent Council V2 — Ralph Runtime Adapter.

Shallow integration layer making Agent Council usable by Ralph Runtime
without deeply changing the runtime loop yet.

Provides:
- build_council_plan_for_goal() — quick plan from a goal string
- summarize_council_plan() — human-readable summary
- council_plan_to_context() — dict suitable for Ralph's planning context

Keep integration shallow and safe.
"""

from __future__ import annotations

from .plan import (
    CouncilPlanRequest,
    CouncilPlanResult,
)
from .plan_generator import generate_council_plan


def build_council_plan_for_goal(
    goal: str,
    project_type: str = "",
    strict_mode: bool = False,
) -> CouncilPlanResult:
    """Build a Council Plan for a simple project goal.

    This is the simplest entry point for Ralph Runtime. It constructs
    a minimal request and delegates to the council plan generator.

    Args:
        goal: Human-readable project goal (e.g. "Build a SaaS CRM").
        project_type: Optional project type hint. If empty, inferred from goal.
        strict_mode: If True, missing critical artifacts block execution.

    Returns:
        A CouncilPlanResult with full plan details.

    Example:
        >>> plan = build_council_plan_for_goal("Build a landing page")
        >>> plan.is_ready_to_execute
        True
        >>> plan.total_active_agents > 0
        True
    """
    request = CouncilPlanRequest(
        project_goal=goal,
        project_type=project_type,
        strict_mode=strict_mode,
    )
    return generate_council_plan(request)


def summarize_council_plan(plan: CouncilPlanResult) -> str:
    """Produce a human-readable summary of a Council Plan.

    Args:
        plan: A CouncilPlanResult to summarize.

    Returns:
        Multi-line string with key plan information.

    Example:
        >>> plan = build_council_plan_for_goal("Build a small app")
        >>> summary = summarize_council_plan(plan)
        >>> "Active Agents" in summary
        True
    """
    lines: list[str] = []
    lines.append("=" * 60)
    lines.append("COUNCIL PLAN SUMMARY")
    lines.append("=" * 60)
    lines.append(f"Project Goal:    {plan.project_goal}")
    lines.append(f"Project Type:    {plan.project_type}")
    lines.append(f"Ready to Execute: {'Yes' if plan.is_ready_to_execute else 'No'}")
    lines.append(f"Next Action:     {plan.next_action_label}")

    lines.append("")
    lines.append(f"Active Agents:   {plan.total_active_agents}")
    if plan.active_agents:
        # Group by layer
        by_layer: dict[int, list[str]] = {}
        for agent in plan.active_agents:
            by_layer.setdefault(agent.layer, []).append(agent.role_name)
        for layer_num in sorted(by_layer):
            names = by_layer[layer_num]
            lines.append(f"  Layer {layer_num:2d}: {', '.join(names[:3])}")
            if len(names) > 3:
                lines.append(f"         + {len(names) - 3} more")

    lines.append("")
    lines.append(f"Total Phases:    {plan.total_phases}")
    lines.append(f"Critical Path:   {len(plan.critical_path)} agents")

    lines.append("")
    lines.append(f"Required Artifacts: {len(plan.required_artifacts)}")
    if plan.missing_artifacts:
        lines.append(f"Missing Artifacts:  {len(plan.missing_artifacts)}")
        lines.extend(f"  - {art}" for art in plan.missing_artifacts[:5])
        if len(plan.missing_artifacts) > 5:
            lines.append(f"  ... and {len(plan.missing_artifacts) - 5} more")

    lines.append("")
    lines.append(f"Risks:           {len(plan.risks)}")
    lines.extend(
        f"  [{risk.severity.value.upper()}] {risk.description[:80]}"
        for risk in plan.risks
    )

    lines.append("")
    lines.append(f"Research Refs:   {len(plan.research_references)}")
    lines.append(f"Evidence Reqs:   {len(plan.evidence_requirements)}")

    if plan.warnings:
        lines.append("")
        lines.append("WARNINGS:")
        lines.extend(f"  ! {w}" for w in plan.warnings)

    lines.append("")
    lines.append("=" * 60)
    return "\n".join(lines)


def council_plan_to_context(plan: CouncilPlanResult) -> dict[str, object]:
    """Convert a Council Plan to a dict suitable for Ralph's planning context.

    This provides a structured data format that Ralph Runtime can consume
    without importing Agent Council modules directly.

    Args:
        plan: A CouncilPlanResult.

    Returns:
        Dict with string keys and JSON-serializable values.

    Example:
        >>> plan = build_council_plan_for_goal("Build a test app")
        >>> ctx = council_plan_to_context(plan)
        >>> ctx["project_type"]
        'full_stack_app'
        >>> isinstance(ctx["active_agents"], list)
        True
    """
    return {
        "project_type": plan.project_type,
        "project_goal": plan.project_goal,
        "is_ready_to_execute": plan.is_ready_to_execute,
        "next_action": plan.next_action.value,
        "next_action_label": plan.next_action_label,
        "total_active_agents": plan.total_active_agents,
        "total_phases": plan.total_phases,
        "active_agents": [
            {
                "agent_id": a.agent_id,
                "role_name": a.role_name,
                "layer": a.layer,
                "phase": a.phase,
                "depends_on": list(a.depends_on),
                "produces_artifacts": list(a.produces_artifacts),
                "can_run_parallel": a.can_run_parallel,
            }
            for a in plan.active_agents
        ],
        "critical_path": list(plan.critical_path),
        "parallel_groups": [list(g) for g in plan.parallel_groups],
        "required_artifacts": [
            {
                "artifact_id": a.artifact_id,
                "name": a.name,
                "owner_agent": a.owner_agent,
                "status": a.status,
                "is_critical": a.is_critical,
            }
            for a in plan.required_artifacts
        ],
        "missing_artifacts": list(plan.missing_artifacts),
        "artifact_contracts": list(plan.artifact_contracts),
        "research_references": [
            {
                "repo_id": r.repo_id,
                "category": r.category,
                "relevance_agent": r.relevance_agent,
                "relevance_level": r.relevance_level,
            }
            for r in plan.research_references
        ],
        "evidence_requirements": [
            {
                "requirement_id": e.requirement_id,
                "description": e.description,
                "required_for_agent": e.required_for_agent,
                "priority": e.priority,
            }
            for e in plan.evidence_requirements
        ],
        "risks": [
            {
                "risk_id": r.risk_id,
                "description": r.description,
                "severity": r.severity.value,
                "mitigation": r.mitigation,
            }
            for r in plan.risks
        ],
        "warnings": list(plan.warnings),
        "summary": plan.summary,
    }
