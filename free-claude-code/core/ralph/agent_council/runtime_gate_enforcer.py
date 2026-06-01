"""Agent Council V2 — Runtime Gate Enforcer.

Deterministic adapter that enforces evidence gates against runtime task
results. Connects the evidence gate infrastructure from Phase 9.16E to
actual task execution outcomes.

Provides:
- enforce_runtime_evidence_gates() — main enforcement entry point
- should_block_task_approval() — gate-based approval decision
- summarize_runtime_gate_enforcement() — human-readable enforcement summary
- runtime_gate_result_to_metadata() — JSON-serializable metadata for task results

No shell commands. No network. No LLM calls.
"""

from __future__ import annotations

from .evidence_gates import EvidenceGateResult, EvidenceGateStatus
from .gate_runner import (
    gate_result_to_context,
    run_evidence_gates,
    summarize_gate_result,
)
from .runtime_evidence import (
    RuntimeEvidenceBinding,
    RuntimeTaskEvidenceBundle,
    extract_runtime_evidence_from_task_result,
    summarize_runtime_evidence_bundle,
)

# ---------------------------------------------------------------------------
# Main enforcement
# ---------------------------------------------------------------------------


def enforce_runtime_evidence_gates(
    task_result: object,
    planning_context: dict[str, object] | None = None,
    workspace_root: str | None = None,
    strict_mode: bool = False,
) -> EvidenceGateResult:
    """Enforce Agent Council evidence gates against a task execution result.

    Extracts runtime evidence from the task result, builds a gate evaluation
    context, and runs all default evidence gates.

    Args:
        task_result: An IterationRunResult, ExecutionResult, QualityGateResult,
                     dict, or any object with relevant execution fields.
        planning_context: Optional Agent Council planning context dict.
                          If None, gates still run but some will be NA.
        workspace_root: Optional workspace path.
        strict_mode: If True, blocking gate failures prevent approval.

    Returns:
        EvidenceGateResult with findings and blocking issues.
    """
    # Extract evidence from task result
    bundle = extract_runtime_evidence_from_task_result(
        task_result,
        workspace_root=workspace_root,
    )

    # Build or inherit planning context
    ctx = _build_enforcement_context(bundle, planning_context)

    # Collect staged path violations from the bundle
    staged_violations: set[str] = _extract_staged_violations(bundle)

    # Determine active task roles from the bundle
    task_roles = [bundle.task_role] if bundle.task_role else []

    # Run gates with evidence extracted from the task
    result = run_evidence_gates(
        planning_context=ctx,
        evidence_items=_bindings_to_evidence_items(bundle.bindings),
        available_paths=_extract_file_paths(bundle),
        verification_commands=_extract_verification_commands(task_result),
        acceptance_criteria=_extract_acceptance_criteria(task_result),
        staged_paths=staged_violations,
        active_task_roles=task_roles,
        strict_mode=strict_mode,
    )

    return result


# ---------------------------------------------------------------------------
# Approval decision
# ---------------------------------------------------------------------------


def should_block_task_approval(gate_result: EvidenceGateResult) -> bool:
    """Determine whether task approval should be blocked based on gate results.

    Returns True if:
    - Overall gate status is BLOCKED
    - Any finding is BLOCKED
    - There are blocking issues
    """
    if gate_result.overall_status == EvidenceGateStatus.BLOCKED:
        return True
    if any(f.status == EvidenceGateStatus.BLOCKED for f in gate_result.findings):
        return True
    return bool(gate_result.blocking_issues)


# ---------------------------------------------------------------------------
# Summary and serialization
# ---------------------------------------------------------------------------


def summarize_runtime_gate_enforcement(
    bundle: RuntimeTaskEvidenceBundle,
    gate_result: EvidenceGateResult,
) -> str:
    """Produce a human-readable enforcement summary.

    Combines runtime evidence extraction results with gate enforcement.
    """
    lines: list[str] = []
    lines.append("=" * 60)
    lines.append("RUNTIME EVIDENCE ENFORCEMENT")
    lines.append("=" * 60)
    lines.append("")
    lines.append(summarize_runtime_evidence_bundle(bundle))
    lines.append("")
    lines.append(summarize_gate_result(gate_result))
    lines.append("")
    lines.append(
        f"APPROVAL BLOCKED: {'YES' if should_block_task_approval(gate_result) else 'NO'}"
    )
    lines.append("=" * 60)
    return "\n".join(lines)


def runtime_gate_result_to_metadata(
    gate_result: EvidenceGateResult,
) -> dict[str, object]:
    """Convert gate enforcement result to task metadata dict.

    Suitable for attaching to Ralph task results, iteration results,
    or quality gate outputs.
    """
    gate_ctx = gate_result_to_context(gate_result)
    return {
        "agent_council_gate_enforcement": {
            "enabled": True,
            "overall_status": gate_result.overall_status.value,
            "is_ready": gate_result.is_ready,
            "approval_blocked": should_block_task_approval(gate_result),
            "gates_run": gate_result.gates_run,
            "gates_passed": gate_result.gates_passed,
            "gates_warned": gate_result.gates_warned,
            "gates_failed": gate_result.gates_failed,
            "gates_blocked": gate_result.gates_blocked,
            "blocking_issues": gate_result.blocking_issues,
            "warnings": gate_result.warnings,
            "summary": gate_result.summary,
            "findings": gate_ctx.get("findings", []),
        },
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _build_enforcement_context(
    bundle: RuntimeTaskEvidenceBundle,
    planning_context: dict[str, object] | None = None,
) -> dict[str, object]:
    """Build a planning context from runtime evidence when no existing context."""
    if planning_context and planning_context.get("council_plan_available"):
        return planning_context
    # Minimal context from the bundle
    return {
        "council_plan_available": True,
        "project_type": "runtime_enforcement",
        "project_goal": f"Task: {bundle.task_id or 'unknown'}",
        "is_ready_to_execute": False,
        "next_action": "ready_for_runtime_planning",
        "next_action_label": "Runtime enforcement",
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
        "risks": [],
        "warnings": [],
        "summary": f"Runtime enforcement for task {bundle.task_id}",
    }


def _bindings_to_evidence_items(
    bindings: list[RuntimeEvidenceBinding],
) -> list:
    """Convert RuntimeEvidenceBindings to EvidenceItems for gate evaluation."""
    from .evidence import create_evidence
    from .models import EvidenceType

    items = []
    for b in bindings:
        ev_type = EvidenceType.AGENT_OUTPUT
        if b.source.value == "file_existence":
            ev_type = EvidenceType.REPO_PATTERN
        elif b.source.value == "test_result" or b.source.value == "command_output":
            ev_type = EvidenceType.TEST_RESULT

        try:
            item = create_evidence(
                source_path=b.path or f"task:{b.summary[:40]}",
                claim=b.summary,
                evidence_type=ev_type,
                notes=b.details,
            )
            items.append(item)
        except Exception:
            # Skip invalid evidence items
            pass
    return items


def _extract_file_paths(bundle: RuntimeTaskEvidenceBundle) -> set[str]:
    """Extract file paths from bindings."""
    paths: set[str] = set()
    for b in bundle.bindings:
        if b.path:
            paths.add(b.path)
    return paths


def _extract_verification_commands(task_result: object) -> list[str]:
    """Try to extract verification commands from various task result shapes."""
    from .runtime_evidence import _safe_getattr

    # Try task.verification_commands
    task = _safe_getattr(task_result, "task", None)
    if task is not None:
        vc = _safe_getattr(task, "verification_commands", [])
        if vc and isinstance(vc, list):
            return [str(c) for c in vc]

    # Try quality gate's verification plan
    qg = _safe_getattr(task_result, "quality_gate_result", None)
    if qg is not None:
        vp = _safe_getattr(qg, "verification_plan", None)
        if vp is not None:
            vc = _safe_getattr(vp, "verification_commands", [])
            if vc and isinstance(vc, list):
                return [str(c) for c in vc]
        vc = _safe_getattr(qg, "verification_commands", [])
        if vc and isinstance(vc, list):
            return [str(c) for c in vc]

    return []


def _extract_acceptance_criteria(task_result: object) -> list[str]:
    """Try to extract acceptance criteria from various task result shapes."""
    from .runtime_evidence import _safe_getattr

    task = _safe_getattr(task_result, "task", None)
    if task is not None:
        ac = _safe_getattr(task, "acceptance_criteria", [])
        if ac and isinstance(ac, list):
            return [str(c) for c in ac]

    ac = _safe_getattr(task_result, "acceptance_criteria", [])
    if ac and isinstance(ac, list):
        return [str(c) for c in ac]

    return []


def _extract_staged_violations(bundle: RuntimeTaskEvidenceBundle) -> set[str]:
    """Find file paths that look like runtime artifacts (.fcc/, .env, logs)."""
    violations: set[str] = set()
    forbidden_patterns = (
        ".fcc/",
        ".fcc-ralph/",
        ".claude/",
        ".env",
        ".git-credentials",
        "secrets",
        "credentials",
        "raw_research_repos",
        "/opt/vega-cloud/research/repos",
        "server_tracker",
        "logs/",
    )
    for b in bundle.bindings:
        if b.path:
            for pat in forbidden_patterns:
                if pat in b.path:
                    violations.add(b.path)
                    break
    return violations
