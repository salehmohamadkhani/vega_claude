"""Agent Council V2 — Planning Context.

Deterministic helpers that convert a CouncilPlanResult into structured
planning context that Ralph Runtime can consume.

Provides:
- build_planning_context_from_council_plan() — convert plan to context dict
- summarize_planning_context() — human-readable context summary
- extract_agent_task_hints() — agent-aware task suggestions
- extract_artifact_task_hints() — artifact-driven task suggestions
- extract_evidence_task_hints() — evidence requirement task suggestions
- extract_risk_task_hints() — risk gate task suggestions

No LLM calls. No network access. All operations are deterministic.
"""

from __future__ import annotations

from .plan import CouncilPlanResult

# ---------------------------------------------------------------------------
# Gate expectations lookup
# ---------------------------------------------------------------------------

# Gate expectations per task role and agent layer — used for prompt injection
_GATE_EXPECTATIONS: dict[str, list[str]] = {
    "doer": [
        "Implementation tasks must prove files exist and are non-empty.",
        "Claim evidence must back any architectural or design claims.",
    ],
    "verifier": [
        "Verification tasks must run deterministic commands (not echo-only).",
        "QA tasks must validate behavior and edge cases, not just file existence.",
        "Security tasks must include concrete checks (dep scan, secret scan, config review, threat model).",
    ],
    "architect": [
        "Architecture decisions should reference Research Corpus patterns where applicable.",
    ],
    "arbiter": [
        "Final Arbiter cannot approve without implementation, verification, QA, and risk evidence.",
    ],
    "security_engineer": [
        "Security evidence must include threat modeling or dependency scanning.",
    ],
    "qa_engineer": [
        "QA evidence must cover behavior, regression, and edge cases.",
    ],
    "final_arbiter": [
        "Final approval gates require evidence from QA, security, and performance testing.",
    ],
}

# Summary block for prompt injection
_GATE_PROMPT_BLOCK = (
    "Evidence Gates:\n"
    "- Implementation tasks must prove files exist and are non-empty.\n"
    "- Verification tasks must run deterministic commands.\n"
    "- QA tasks must validate behavior and edge cases.\n"
    "- Final Arbiter cannot approve without implementation, verification, QA, and risk evidence.\n"
    "- Security tasks must include threat modeling or dependency scanning.\n"
    "- Visual/UI tasks should include visual QA notes when applicable.\n"
    "- Runtime artifacts (.fcc/, .fcc-ralph/, .claude/, env, logs) must not be committed."
)


# ---------------------------------------------------------------------------
# Core context builder
# ---------------------------------------------------------------------------


def build_planning_context_from_council_plan(
    plan: CouncilPlanResult,
) -> dict[str, object]:
    """Build a Ralph-compatible planning context dict from a CouncilPlanResult.

    This is the primary integration point. The returned dict can be passed
    directly to the TaskPlanner or any downstream Ralph consumer.

    Args:
        plan: A complete CouncilPlanResult.

    Returns:
        Dict with string keys and JSON-serializable values, structured for
        Ralph's planning layer.
    """
    return {
        # -- Identity --
        "council_plan_available": True,
        "project_type": plan.project_type,
        "project_goal": plan.project_goal,
        "is_ready_to_execute": plan.is_ready_to_execute,
        "next_action": plan.next_action.value,
        "next_action_label": plan.next_action_label,
        # -- Agents --
        "active_agent_count": plan.total_active_agents,
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
        # -- Execution structure --
        "critical_path": list(plan.critical_path),
        "parallel_groups": [list(g) for g in plan.parallel_groups],
        # -- Artifacts --
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
        "missing_artifact_ids": list(plan.missing_artifacts),
        "artifact_contract_ids": list(plan.artifact_contracts),
        # -- Research & Evidence --
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
                "required_for_artifact": e.required_for_artifact,
                "source_hint": e.source_hint,
                "priority": e.priority,
            }
            for e in plan.evidence_requirements
        ],
        # -- Risks --
        "risks": [
            {
                "risk_id": r.risk_id,
                "description": r.description,
                "severity": r.severity.value,
                "affected_agents": list(r.affected_agents),
                "affected_artifacts": list(r.affected_artifacts),
                "mitigation": r.mitigation,
            }
            for r in plan.risks
        ],
        # -- Meta --
        "warnings": list(plan.warnings),
        "summary": plan.summary,
    }


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------


def summarize_planning_context(context: dict[str, object]) -> str:
    """Produce a concise human-readable summary of planning context.

    Args:
        context: A planning context dict from build_planning_context_from_council_plan().

    Returns:
        Multi-line summary string.
    """
    lines: list[str] = []
    lines.append("--- Agent Council Planning Context ---")

    pt = context.get("project_type", "unknown")
    pg = context.get("project_goal", "unknown")
    lines.append(f"Project: {pg}  (type: {pt})")
    lines.append(f"Ready to execute: {context.get('is_ready_to_execute', False)}")
    lines.append(f"Next action: {context.get('next_action_label', 'unknown')}")

    ac = context.get("active_agent_count", 0)
    ph = context.get("total_phases", 0)
    lines.append(f"Active agents: {ac}  in {ph} phases")

    arts = context.get("required_artifacts", [])
    if isinstance(arts, list):
        lines.append(f"Required artifacts: {len(arts)}")
        critical = [a for a in arts if isinstance(a, dict) and a.get("is_critical")]
        if critical:
            lines.append(
                f"  Critical: {', '.join(a.get('name', '?') for a in critical)}"
            )

    missing = context.get("missing_artifact_ids", [])
    if missing and isinstance(missing, list) and len(missing) > 0:
        lines.append(f"Missing artifacts: {', '.join(str(m) for m in missing)}")

    risks = context.get("risks", [])
    if isinstance(risks, list):
        blocking = [
            r for r in risks if isinstance(r, dict) and r.get("severity") == "blocking"
        ]
        high = [r for r in risks if isinstance(r, dict) and r.get("severity") == "high"]
        lines.append(
            f"Risks: {len(risks)} ({len(blocking)} blocking, {len(high)} high)"
        )

    evidence = context.get("evidence_requirements", [])
    if isinstance(evidence, list):
        lines.append(f"Evidence requirements: {len(evidence)}")

    lines.append("---")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Task hint extractors
# ---------------------------------------------------------------------------


def extract_agent_task_hints(context: dict[str, object]) -> list[str]:
    """Extract agent-aware task hints from planning context.

    Returns a list of strings that describe what each active agent
    is responsible for. These can be used to enrich Ralph task descriptions.

    Args:
        context: Planning context dict.

    Returns:
        List of hint strings like "Layer 7 — Software Architect produces architecture_spec".
    """
    hints: list[str] = []
    agents = context.get("active_agents", [])
    if not isinstance(agents, list):
        return hints

    for agent in agents:
        if not isinstance(agent, dict):
            continue
        agent_id = agent.get("role_name", agent.get("agent_id", ""))
        layer = agent.get("layer", "")
        produces = agent.get("produces_artifacts", [])
        if produces and isinstance(produces, list) and len(produces) > 0:
            artifacts = ", ".join(str(p) for p in produces[:3])
            hints.append(f"Layer {layer} — {agent_id} → produces: {artifacts}")
        else:
            hints.append(f"Layer {layer} — {agent_id}")

    return hints


def extract_artifact_task_hints(context: dict[str, object]) -> list[str]:
    """Extract artifact-driven task hints from planning context.

    Each hint describes an artifact that must be produced and which
    agent is responsible. Pending artifacts suggest implementation tasks.

    Args:
        context: Planning context dict.

    Returns:
        List of hint strings.
    """
    hints: list[str] = []
    artifacts = context.get("required_artifacts", [])
    if not isinstance(artifacts, list):
        return hints

    for art in artifacts:
        if not isinstance(art, dict):
            continue
        name = art.get("name", art.get("artifact_id", "unknown"))
        owner = art.get("owner_agent", "")
        status = art.get("status", "pending")
        is_critical = art.get("is_critical", False)
        label = "[CRITICAL] " if is_critical else ""
        if owner:
            hints.append(f"{label}Artifact '{name}' → owner: {owner} [{status}]")
        elif is_critical:
            hints.append(f"{label}Artifact '{name}' → NO OWNER — must be produced")

    return hints


def extract_evidence_task_hints(context: dict[str, object]) -> list[str]:
    """Extract evidence-driven task hints from planning context.

    Each hint describes evidence that must be collected during execution.

    Args:
        context: Planning context dict.

    Returns:
        List of hint strings.
    """
    hints: list[str] = []
    evidence_reqs = context.get("evidence_requirements", [])
    if not isinstance(evidence_reqs, list):
        return hints

    for ev in evidence_reqs:
        if not isinstance(ev, dict):
            continue
        desc = ev.get("description", "")
        priority = ev.get("priority", "medium")
        agent = ev.get("required_for_agent", "")
        artifact = ev.get("required_for_artifact", "")
        parts = [f"[{priority.upper()}] Evidence: {desc}"]
        if agent:
            parts.append(f"for agent '{agent}'")
        if artifact:
            parts.append(f"on artifact '{artifact}'")
        hints.append(" ".join(parts))

    return hints


def extract_risk_task_hints(context: dict[str, object]) -> list[str]:
    """Extract risk-gate task hints from planning context.

    Each hint describes a risk that must be mitigated during execution.

    Args:
        context: Planning context dict.

    Returns:
        List of hint strings.
    """
    hints: list[str] = []
    risks = context.get("risks", [])
    if not isinstance(risks, list):
        return hints

    for risk in risks:
        if not isinstance(risk, dict):
            continue
        severity = risk.get("severity", "medium")
        desc = risk.get("description", "")
        mitigation = risk.get("mitigation", "")
        affected = risk.get("affected_agents", [])
        parts = [f"[{severity.upper()}] Risk: {desc}"]
        if affected and isinstance(affected, list):
            parts.append(f"affects: {', '.join(str(a) for a in affected)}")
        if mitigation:
            parts.append(f"→ {mitigation}")
        hints.append(" ".join(parts))

    return hints


# ---------------------------------------------------------------------------
# Gate expectation extractors
# ---------------------------------------------------------------------------


def extract_gate_expectations(context: dict[str, object]) -> list[str]:
    """Extract evidence gate expectations relevant to the planning context.

    Returns gate rules that apply based on active agents and task roles.

    Args:
        context: Planning context dict.

    Returns:
        List of gate expectation strings.
    """
    agents = context.get("active_agents", [])
    if not isinstance(agents, list):
        return []

    seen: set[str] = set()
    expectations: list[str] = []

    # Gate expectations from active agents
    for agent in agents:
        if not isinstance(agent, dict):
            continue
        agent_id = agent.get("agent_id", "")

        # Check by agent_id
        if agent_id in _GATE_EXPECTATIONS:
            for exp in _GATE_EXPECTATIONS[agent_id]:
                if exp not in seen:
                    seen.add(exp)
                    expectations.append(exp)

        # Check by role-like patterns (agent_id often contains role hints)
        # No further role mapping needed — we rely on agent_id directly

    return expectations


def build_gate_context_block(context: dict[str, object]) -> str:
    """Build a concise gate expectations block for prompt injection.

    Args:
        context: Planning context dict.

    Returns:
        Formatted gate block string suitable for inclusion in prompts.
    """
    return _GATE_PROMPT_BLOCK


def add_gate_context_to_planning_dict(
    context: dict[str, object],
) -> dict[str, object]:
    """Enrich a planning context dict with gate-related keys.

    Adds evidence_gate_requirements, blocking_gates, warning_gates,
    gate_summary, and readiness_gate_status.

    Args:
        context: Planning context dict (mutated in place, also returned).

    Returns:
        The enriched context dict.
    """
    expectations = extract_gate_expectations(context)
    block = build_gate_context_block(context)

    context["evidence_gate_expectations"] = expectations
    context["gate_prompt_block"] = block
    context["blocking_gates"] = [
        g
        for g in expectations
        if any(kw in g.lower() for kw in ("must", "cannot", "block"))
    ]
    context["warning_gates"] = [
        g
        for g in expectations
        if not any(kw in g.lower() for kw in ("must", "cannot", "block"))
    ]
    context["gate_summary"] = (
        f"{len(expectations)} gate expectations active "
        f"({len(context['blocking_gates'])} blocking, "
        f"{len(context['warning_gates'])} warning)"
    )
    context["readiness_gate_status"] = "pending"

    return context
