"""Agent Council V2 — Planner Integration.

Shallow bridge between Agent Council plans and Ralph Runtime's TaskPlanner.

Provides:
- build_agent_council_task_context() — one-call: goal → Ralph-ready context
- format_agent_council_context_for_prompt() — format context for prompt injection

Degrade gracefully if Agent Council planning fails.
No LLM calls. No network access.
"""

from __future__ import annotations

from .planning_context import (
    add_gate_context_to_planning_dict,
    build_planning_context_from_council_plan,
)
from .runtime_adapter import build_council_plan_for_goal

# ---------------------------------------------------------------------------
# Graceful degradation
# ---------------------------------------------------------------------------


def _degraded_context(
    reason: str = "Agent Council planning unavailable",
) -> dict[str, object]:
    """Return a minimal context dict when Agent Council is unavailable."""
    return {
        "council_plan_available": False,
        "error": reason,
        "project_type": "unknown",
        "project_goal": "",
        "is_ready_to_execute": False,
        "next_action": "needs_scope_clarification",
        "next_action_label": "Blocked — Agent Council plan could not be generated",
        "active_agent_count": 0,
        "total_phases": 0,
        "active_agents": [],
        "critical_path": [],
        "parallel_groups": [],
        "required_artifacts": [],
        "missing_artifact_ids": [],
        "artifact_contract_ids": [],
        "research_references": [],
        "evidence_requirements": [],
        "risks": [
            {
                "risk_id": "council_plan_failed",
                "description": f"Agent Council planning failed: {reason}",
                "severity": "high",
                "affected_agents": [],
                "affected_artifacts": [],
                "mitigation": "Proceed with standard Ralph planning (no Agent Council context).",
            }
        ],
        "warnings": [f"Agent Council planning degraded: {reason}"],
        "summary": f"Council plan not available ({reason}). Falling back to standard planning.",
    }


# ---------------------------------------------------------------------------
# Main integration entry point
# ---------------------------------------------------------------------------


def build_agent_council_task_context(
    goal: str,
    project_type: str | None = None,
    strict_mode: bool = False,
    available_artifacts: set[str] | None = None,
) -> dict[str, object]:
    """Build a Ralph-compatible task planning context from a goal.

    This is the primary integration entry point for Ralph Runtime.
    It constructs a Council Plan and converts it to a context dict that
    Ralph's TaskPlanner can consume directly.

    Args:
        goal: Human-readable project goal description.
        project_type: Optional project type hint. If None, inferred from goal.
        strict_mode: If True, missing critical artifacts will block.
        available_artifacts: Optional set of pre-existing artifact IDs.

    Returns:
        A dict with council_plan_available, project_type, active_agents,
        required_artifacts, evidence_requirements, risks, and more.

    Example:
        >>> ctx = build_agent_council_task_context("Build a SaaS CRM")
        >>> ctx["council_plan_available"]
        True
        >>> isinstance(ctx["active_agents"], list)
        True
    """
    try:
        plan = build_council_plan_for_goal(
            goal=goal,
            project_type=project_type or "",
            strict_mode=strict_mode,
        )

        if not plan.is_ready_to_execute and strict_mode:
            # Plan is blocked — return the context anyway so Ralph knows why
            return add_gate_context_to_planning_dict(
                build_planning_context_from_council_plan(plan)
            )

        ctx = build_planning_context_from_council_plan(plan)
        return add_gate_context_to_planning_dict(ctx)

    except Exception as exc:
        return _degraded_context(str(exc))


# ---------------------------------------------------------------------------
# Prompt formatting
# ---------------------------------------------------------------------------


def format_agent_council_context_for_prompt(
    context: dict[str, object],
    *,
    max_agents: int = 8,
    max_risks: int = 5,
    max_evidence: int = 4,
) -> str:
    """Format Agent Council context for injection into Ralph task planning prompts.

    Produces a concise, structured text block suitable for prepending to
    Claude Code prompts or Ralph planning instruction blocks.

    Args:
        context: Planning context dict.
        max_agents: Maximum agent entries to include.
        max_risks: Maximum risk entries to include.
        max_evidence: Maximum evidence entries to include.

    Returns:
        Concise formatted string.

    Example:
        >>> ctx = build_agent_council_task_context("Build a CRM", "full_stack_app")
        >>> prompt = format_agent_council_context_for_prompt(ctx)
        >>> "Agent Council" in prompt
        True
    """
    if not context.get("council_plan_available"):
        return (
            "[Agent Council planning unavailable — "
            f"{context.get('error', 'unknown reason')}]\n"
        )

    lines: list[str] = []
    lines.append("## Agent Council Context")
    lines.append(f"Project Type: {context.get('project_type', 'unknown')}")
    lines.append(f"Ready: {context.get('is_ready_to_execute', False)}")
    lines.append(f"Next: {context.get('next_action_label', '')}")

    # Active agents (top N)
    agents = context.get("active_agents", [])
    if isinstance(agents, list) and agents:
        lines.append(
            f"\n### Active Agents ({len(agents)} total, showing top {max_agents})"
        )
        for a in agents[:max_agents]:
            if isinstance(a, dict):
                deps = a.get("depends_on", [])
                dep_str = f" depends on [{', '.join(deps)}]" if deps else ""
                lines.append(
                    f"- [{a.get('phase', '?')}] {a.get('role_name', a.get('agent_id', '?'))} "
                    f"(layer {a.get('layer', '?')}){dep_str}"
                )

    # Critical path
    cp = context.get("critical_path", [])
    if cp and isinstance(cp, list):
        lines.append(f"\n### Critical Path ({len(cp)} agents)")
        lines.append(
            f"{' → '.join(str(a) for a in cp[:8])}" + ("..." if len(cp) > 8 else "")
        )

    # Missing artifacts
    missing = context.get("missing_artifact_ids", [])
    if missing and isinstance(missing, list) and len(missing) > 0:
        lines.append(f"\n### Missing Critical Artifacts ({len(missing)})")
        lines.extend(f"- {m}" for m in missing)

    # Risks (top N)
    risks = context.get("risks", [])
    if isinstance(risks, list) and risks:
        blocking = [
            r for r in risks if isinstance(r, dict) and r.get("severity") == "blocking"
        ]
        high = [r for r in risks if isinstance(r, dict) and r.get("severity") == "high"]
        lines.append(
            f"\n### Risks ({len(risks)} total — {len(blocking)} blocking, {len(high)} high)"
        )
        for r in risks[:max_risks]:
            if isinstance(r, dict):
                lines.append(
                    f"- [{r.get('severity', '?').upper()}] {r.get('description', '?')}"
                )
                mitigation = r.get("mitigation", "")
                if mitigation:
                    lines.append(f"  → {mitigation}")

    # Evidence requirements (top N)
    evidence = context.get("evidence_requirements", [])
    if isinstance(evidence, list) and evidence:
        lines.append(f"\n### Evidence Requirements ({len(evidence)} total)")
        lines.extend(
            f"- [{e.get('priority', 'medium').upper()}] {e.get('description', '')}"
            for e in evidence[:max_evidence]
            if isinstance(e, dict)
        )

    # Gate expectations
    gate_block = context.get("gate_prompt_block", "")
    if gate_block:
        lines.append(f"\n### {gate_block}")

    return "\n".join(lines)
