"""Agent Council V2 — Gate Runner.

Deterministic runner that evaluates all applicable evidence gates against
a planning context and evidence items.

Provides:
- run_evidence_gates() — evaluate all default gates
- summarize_gate_result() — human-readable summary
- gate_result_to_context() — JSON-serializable dict for Ralph

No shell commands. No network. No LLM calls.
"""

from __future__ import annotations

from .evidence_gates import (
    _DEFAULT_GATE_METADATA,
    EvidenceGateFinding,
    EvidenceGateRequirement,
    EvidenceGateResult,
    EvidenceGateSeverity,
    EvidenceGateStatus,
    GateEvaluationContext,
    get_gate_function,
    list_default_gate_ids,
)
from .models import EvidenceItem

# ---------------------------------------------------------------------------
# Context builder
# ---------------------------------------------------------------------------


def _build_gate_context(
    planning_context: dict[str, object],
    evidence_items: list[EvidenceItem] | None = None,
    available_paths: set[str] | None = None,
    available_file_sizes: dict[str, int] | None = None,
    verification_commands: list[str] | None = None,
    acceptance_criteria: list[str] | None = None,
    research_references: list[str] | None = None,
    staged_paths: set[str] | None = None,
    active_task_roles: list[str] | None = None,
    strict_mode: bool = False,
) -> GateEvaluationContext:
    """Build a GateEvaluationContext from planning context and metadata."""
    # Extract agent IDs
    agents = planning_context.get("active_agents", [])
    agent_ids: list[str] = []
    layers: list[int] = []
    task_roles: list[str] = list(active_task_roles) if active_task_roles else []
    if isinstance(agents, list):
        for a in agents:
            if isinstance(a, dict):
                aid = a.get("agent_id", "")
                if aid:
                    agent_ids.append(aid)
                layer = a.get("layer")
                if isinstance(layer, int):
                    layers.append(layer)

    # Extract required artifacts
    req_arts = planning_context.get("required_artifacts", [])
    required_ids: list[str] = []
    if isinstance(req_arts, list):
        for ra in req_arts:
            if isinstance(ra, dict):
                art_id = ra.get("artifact_id", "")
                if art_id:
                    required_ids.append(art_id)

    # Extract missing artifacts
    missing = planning_context.get("missing_artifact_ids", [])
    missing_ids: list[str] = []
    if isinstance(missing, list):
        missing_ids = [str(m) for m in missing if m]

    # Evidence items
    ev_items = tuple(evidence_items) if evidence_items else ()

    return GateEvaluationContext(
        project_type=str(planning_context.get("project_type", "")),
        project_goal=str(planning_context.get("project_goal", "")),
        active_agent_ids=tuple(sorted(agent_ids)),
        active_task_roles=tuple(sorted(task_roles)),
        active_layers=tuple(sorted(set(layers))),
        required_artifacts=tuple(sorted(required_ids)),
        missing_artifacts=tuple(sorted(missing_ids)),
        evidence_items=ev_items,
        available_paths=tuple(sorted(available_paths)) if available_paths else (),
        available_file_sizes=available_file_sizes or {},
        verification_commands=tuple(verification_commands) if verification_commands else (),
        acceptance_criteria=tuple(acceptance_criteria) if acceptance_criteria else (),
        research_references=tuple(research_references) if research_references else (),
        staged_paths=tuple(sorted(staged_paths)) if staged_paths else (),
        strict_mode=strict_mode,
    )


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------


def run_evidence_gates(
    planning_context: dict[str, object],
    evidence_items: list[EvidenceItem] | None = None,
    available_paths: set[str] | None = None,
    available_file_sizes: dict[str, int] | None = None,
    verification_commands: list[str] | None = None,
    acceptance_criteria: list[str] | None = None,
    research_references: list[str] | None = None,
    staged_paths: set[str] | None = None,
    active_task_roles: list[str] | None = None,
    strict_mode: bool = False,
    gate_ids: list[str] | None = None,
) -> EvidenceGateResult:
    """Run all applicable evidence gates against the given context.

    Args:
        planning_context: Planning context dict (from council plan or planner).
        evidence_items: Optional evidence items collected so far.
        available_paths: Optional set of filesystem paths that exist.
        available_file_sizes: Optional dict of path -> file size in bytes.
        verification_commands: Optional list of verification commands.
        acceptance_criteria: Optional list of acceptance criteria strings.
        research_references: Optional list of research repo_ids.
        staged_paths: Optional set of paths staged for git commit.
        strict_mode: If True, missing critical evidence blocks.
        gate_ids: Optional list of specific gate IDs to run. If None, all.

    Returns:
        EvidenceGateResult with findings, counts, and blocking issues.
    """
    ctx = _build_gate_context(
        planning_context=planning_context,
        evidence_items=evidence_items,
        available_paths=available_paths,
        available_file_sizes=available_file_sizes,
        verification_commands=verification_commands,
        acceptance_criteria=acceptance_criteria,
        research_references=research_references,
        staged_paths=staged_paths,
        active_task_roles=active_task_roles,
        strict_mode=strict_mode,
    )

    # Resolve which gates to run
    run_ids = gate_ids if gate_ids else list(list_default_gate_ids())
    findings: list[EvidenceGateFinding] = []

    for gid in run_ids:
        fn = get_gate_function(gid)
        if fn is None:
            continue
        try:
            finding = fn(ctx)
        except Exception as exc:
            finding = EvidenceGateFinding(
                gate_id=gid,
                status=EvidenceGateStatus.BLOCKED,
                message=f"Gate crashed: {exc}",
                severity=EvidenceGateSeverity.CRITICAL,
            )
        findings.append(finding)

    # Aggregate
    passed = sum(1 for f in findings if f.status == EvidenceGateStatus.PASSED)
    warned = sum(1 for f in findings if f.status == EvidenceGateStatus.WARNING)
    failed = sum(1 for f in findings if f.status == EvidenceGateStatus.FAILED)
    blocked = sum(1 for f in findings if f.status == EvidenceGateStatus.BLOCKED)
    skipped = sum(1 for f in findings if f.status == EvidenceGateStatus.NOT_APPLICABLE)

    blocking_issues: list[str] = []
    all_warnings: list[str] = []

    # Check gate metadata for blocking requirements
    meta_map: dict[str, EvidenceGateRequirement] = {
        r.gate_id: r for r in _DEFAULT_GATE_METADATA
    }
    for f in findings:
        meta = meta_map.get(f.gate_id)
        if meta and meta.blocking:
            if f.status in (EvidenceGateStatus.FAILED, EvidenceGateStatus.BLOCKED):
                blocking_issues.append(f.message)
        if f.status == EvidenceGateStatus.WARNING:
            all_warnings.append(f.message)

    # Determine overall status
    has_critical_failures = any(
        meta_map.get(f.gate_id, EvidenceGateRequirement(gate_id=f.gate_id)).blocking
        and f.status in (EvidenceGateStatus.FAILED, EvidenceGateStatus.BLOCKED)
        for f in findings
    )

    if blocked > 0 or (has_critical_failures and strict_mode):
        overall = EvidenceGateStatus.BLOCKED
    elif failed > 0:
        overall = EvidenceGateStatus.FAILED
    elif warned > 0:
        overall = EvidenceGateStatus.WARNING
    elif passed + skipped == len(findings):
        overall = EvidenceGateStatus.PASSED
    else:
        overall = EvidenceGateStatus.WARNING

    # Build summary
    parts = [f"gates={passed}/{len(findings)} passed"]
    if blocked > 0:
        parts.append(f"{blocked} blocked")
    if failed > 0:
        parts.append(f"{failed} failed")
    if warned > 0:
        parts.append(f"{warned} warned")
    if skipped > 0:
        parts.append(f"{skipped} skipped")
    if blocking_issues:
        parts.append(f"{len(blocking_issues)} blocking")
    parts.append(f"overall={overall.value}")

    return EvidenceGateResult(
        gate_id="council_evidence_gates",
        findings=findings,
        overall_status=overall,
        gates_run=len(findings),
        gates_passed=passed,
        gates_warned=warned,
        gates_failed=failed,
        gates_blocked=blocked,
        gates_skipped=skipped,
        blocking_issues=blocking_issues,
        warnings=all_warnings,
        summary=" | ".join(parts),
    )


# ---------------------------------------------------------------------------
# Summary and serialization
# ---------------------------------------------------------------------------


def summarize_gate_result(result: EvidenceGateResult) -> str:
    """Produce a human-readable summary of gate results.

    Args:
        result: EvidenceGateResult from run_evidence_gates().

    Returns:
        Multi-line summary string.
    """
    lines: list[str] = []
    lines.append("=" * 60)
    lines.append("EVIDENCE GATE RESULTS")
    lines.append("=" * 60)
    lines.append(f"Overall Status: {result.overall_status.value.upper()}")
    lines.append(f"Gates Run: {result.gates_run}")
    lines.append(f"  Passed:  {result.gates_passed}")
    lines.append(f"  Warned:  {result.gates_warned}")
    lines.append(f"  Failed:  {result.gates_failed}")
    lines.append(f"  Blocked: {result.gates_blocked}")
    lines.append(f"  Skipped: {result.gates_skipped}")

    if result.blocking_issues:
        lines.append("")
        lines.append("BLOCKING ISSUES:")
        for bi in result.blocking_issues:
            lines.append(f"  !! {bi}")

    # Per-gate findings
    lines.append("")
    lines.append("GATE DETAILS:")
    for f in result.findings:
        icon = {
            EvidenceGateStatus.PASSED: "PASS",
            EvidenceGateStatus.WARNING: "WARN",
            EvidenceGateStatus.FAILED: "FAIL",
            EvidenceGateStatus.BLOCKED: "BLOCK",
            EvidenceGateStatus.NOT_APPLICABLE: "  NA",
        }.get(f.status, "????")
        lines.append(f"  [{icon}] {f.gate_id}: {f.message[:100]}")
        if f.required_action:
            lines.append(f"         → {f.required_action[:100]}")

    lines.append("")
    lines.append("=" * 60)
    return "\n".join(lines)


def gate_result_to_context(result: EvidenceGateResult) -> dict[str, object]:
    """Convert gate result to a JSON-serializable dict for Ralph's context.

    Args:
        result: EvidenceGateResult from run_evidence_gates().

    Returns:
        Dict with string keys and JSON-serializable values.
    """
    return {
        "gate_id": result.gate_id,
        "overall_status": result.overall_status.value,
        "is_ready": result.is_ready,
        "has_warnings": result.has_warnings,
        "gates_run": result.gates_run,
        "gates_passed": result.gates_passed,
        "gates_warned": result.gates_warned,
        "gates_failed": result.gates_failed,
        "gates_blocked": result.gates_blocked,
        "gates_skipped": result.gates_skipped,
        "blocking_issues": result.blocking_issues,
        "warnings": result.warnings,
        "summary": result.summary,
        "findings": [
            {
                "gate_id": f.gate_id,
                "status": f.status.value,
                "message": f.message,
                "details": f.details,
                "affected_paths": f.affected_paths,
                "affected_artifacts": f.affected_artifacts,
                "required_action": f.required_action,
                "severity": f.severity.value,
            }
            for f in result.findings
        ],
    }


# ---------------------------------------------------------------------------
# Convenience
# ---------------------------------------------------------------------------


def run_all_gates(
    planning_context: dict[str, object],
    *,
    evidence_items: list[EvidenceItem] | None = None,
    strict_mode: bool = False,
) -> EvidenceGateResult:
    """Convenience: run all default gates with minimal parameters."""
    return run_evidence_gates(
        planning_context=planning_context,
        evidence_items=evidence_items,
        strict_mode=strict_mode,
    )
