"""Agent Council V2 — Runtime Evidence Binding.

Deterministic models and helpers that bind task execution outputs to
Agent Council evidence items.

Provides:
- RuntimeEvidenceSource — enumeration of evidence source types
- RuntimeEvidenceBinding — a single bound evidence observation
- RuntimeTaskEvidenceBundle — all evidence extracted from one task result
- RuntimeEvidenceBindingStatus — outcome of the binding process
- extract_runtime_evidence_from_task_result() — main extraction function

No LLM calls. No shell commands. No network access.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class RuntimeEvidenceSource(enum.Enum):
    """What kind of task output a piece of evidence comes from."""

    FILE_EXISTENCE = "file_existence"
    FILE_NON_EMPTY = "file_non_empty"
    FILE_MODIFIED = "file_modified"
    COMMAND_OUTPUT = "command_output"
    TEST_RESULT = "test_result"
    QA_BEHAVIOR = "qa_behavior"
    SECURITY_CHECK = "security_check"
    VISUAL_QA = "visual_qa"
    RESEARCH_REFERENCE = "research_reference"
    ARBITER_DECISION = "arbiter_decision"
    ACCEPTANCE_CRITERIA = "acceptance_criteria"
    ARTIFACT_PRODUCED = "artifact_produced"
    STAGED_FILE = "staged_file"
    UNKNOWN = "unknown"


class RuntimeEvidenceBindingStatus(enum.Enum):
    """Result status of binding evidence to a task."""

    BOUND = "bound"
    WARNING = "warning"
    FAILED = "failed"
    BLOCKED = "blocked"
    NOT_APPLICABLE = "not_applicable"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class RuntimeEvidenceBinding:
    """A single evidence observation extracted from a task result.

    Each binding records one fact (file exists, command ran, test passed)
    with enough context for evidence gates to evaluate.
    """

    source: RuntimeEvidenceSource = RuntimeEvidenceSource.UNKNOWN
    path: str = ""
    summary: str = ""
    passed: bool = False
    details: str = ""
    is_echo_only: bool = False
    is_empty: bool = False
    severity: str = "info"
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass
class RuntimeTaskEvidenceBundle:
    """All evidence extracted from a single task result.

    Consumed by gate enforcement to determine whether the task has
    enough evidence to pass approval.
    """

    task_id: str = ""
    task_role: str = ""
    task_title: str = ""
    bindings: list[RuntimeEvidenceBinding] = field(default_factory=list)
    status: RuntimeEvidenceBindingStatus = RuntimeEvidenceBindingStatus.NOT_APPLICABLE
    summary: str = ""
    has_files: bool = False
    has_real_commands: bool = False
    has_behavior_evidence: bool = False
    has_security_evidence: bool = False
    has_arbiter_evidence: bool = False
    warnings: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)

    @property
    def binding_count(self) -> int:
        return len(self.bindings)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _safe_getattr(obj: Any, attr: str, default: Any = "") -> Any:
    """Get attribute or dict key safely."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(attr, default)
    return getattr(obj, attr, default)


def _has_echo_only_verification(commands: list[str]) -> bool:
    """Check whether verification commands are echo-only padding."""
    if not commands:
        return False
    real_count = 0
    for cmd in commands:
        stripped = cmd.strip()
        if not stripped.startswith("echo ") or any(
            kw in stripped
            for kw in ("$(", "`", "|", "&&", "||", "test ", "grep ", "pytest", "ruff")
        ):
            real_count += 1
    return real_count == 0 and len(commands) > 0


def _has_real_verification(commands: list[str]) -> bool:
    """Check whether at least one real verification command exists."""
    if not commands:
        return False
    return not _has_echo_only_verification(commands)


def _check_behavior_keywords(texts: list[str]) -> bool:
    """Check for behavior/edge-case-related keywords."""
    behavior_keywords = {
        "edge",
        "regression",
        "coverage",
        "acceptance",
        "behavior",
        "fail",
        "error",
        "corner",
        "boundary",
        "input",
        "output",
        "state",
        "component",
        "integration",
        "e2e",
        "end-to-end",
    }
    combined = " ".join(texts).lower()
    return any(kw in combined for kw in behavior_keywords)


def _check_security_keywords(texts: list[str]) -> bool:
    """Check for security-related keywords."""
    security_keywords = {
        "scan",
        "secret",
        "owasp",
        "threat",
        "vulnerability",
        "cve",
        "dependency",
        "penetration",
        "auth",
        "csrf",
        "xss",
        "injection",
        "compliance",
        "gdpr",
        "audit",
    }
    combined = " ".join(texts).lower()
    return any(kw in combined for kw in security_keywords)


# ---------------------------------------------------------------------------
# Main extraction
# ---------------------------------------------------------------------------


def extract_runtime_evidence_from_task_result(
    task_result: object,
    workspace_root: str | None = None,
) -> RuntimeTaskEvidenceBundle:
    """Extract structured evidence bindings from a task execution result.

    Handles Ralph's IterationRunResult, ExecutionResult, QualityGateResult,
    and plain dicts. Degrades gracefully on unknown shapes.

    Args:
        task_result: A task result object (IterationRunResult, ExecutionResult,
                     QualityGateResult, dict, or any object with relevant attrs).
        workspace_root: Optional workspace path for resolving relative paths.

    Returns:
        RuntimeTaskEvidenceBundle with all extracted bindings.
    """
    bindings: list[RuntimeEvidenceBinding] = []
    warnings: list[str] = []
    failures: list[str] = []

    # --- Extract metadata ---
    task_id = _safe_getattr(task_result, "task_id", "")
    task_title = _safe_getattr(task_result, "task_title", "")
    task_role = "doer"

    # --- Extract from ExecutionResult (nested or direct) ---
    exec_result = _safe_getattr(task_result, "execution_result", None)
    if exec_result is None:
        exec_result = task_result  # may be the result directly

    changed_files: list[str] = _safe_getattr(exec_result, "changed_files", [])
    if not isinstance(changed_files, list):
        changed_files = []
    created_files: list[str] = _safe_getattr(exec_result, "created_files", [])
    if not isinstance(created_files, list):
        created_files = []
    all_files = list(set(changed_files + created_files))
    stdout = _safe_getattr(exec_result, "stdout_summary", "")
    stderr = _safe_getattr(exec_result, "stderr_summary", "")

    # --- Extract from QualityGateResult ---
    qg_result = _safe_getattr(task_result, "quality_gate_result", None)
    verification_result = None
    ac_criteria: list[str] = []
    verif_commands: list[str] = []
    arbiter_action = ""
    final_status = ""

    if qg_result is not None:
        verification_result = _safe_getattr(qg_result, "verification_result", None)
        ac_criteria_list = _safe_getattr(qg_result, "acceptance_criteria", None)
        task_obj = _safe_getattr(task_result, "task", None)
        if task_obj is not None:
            ac_criteria = _safe_getattr(task_obj, "acceptance_criteria", [])
            verif_commands = _safe_getattr(task_obj, "verification_commands", [])
            task_role = _safe_getattr(task_obj, "agent_role", "doer")
            if hasattr(task_role, "value"):
                task_role = task_role.value
        if not ac_criteria and ac_criteria_list:
            ac_criteria = ac_criteria_list if isinstance(ac_criteria_list, list) else []
        # Arbiter
        arbiter_decision = _safe_getattr(qg_result, "arbiter_decision", None)
        if arbiter_decision is not None:
            arbiter_action = _safe_getattr(arbiter_decision, "action", "")
            if hasattr(arbiter_action, "value"):
                arbiter_action = arbiter_action.value
        final_status = _safe_getattr(qg_result, "final_status", "")
        if hasattr(final_status, "value"):
            final_status = final_status.value

    # Try to get verification commands from the verification result too
    if verification_result is not None:
        verif_from_result = _safe_getattr(verification_result, "commands", None)
        if verif_from_result and isinstance(verif_from_result, list):
            verif_commands = verif_commands or verif_from_result

    # --- Extract from task (if available) ---
    task = _safe_getattr(task_result, "task", None)
    if task is not None:
        task_role = _safe_getattr(task, "agent_role", task_role)
        if hasattr(task_role, "value"):
            task_role = task_role.value
        task_ac = _safe_getattr(task, "acceptance_criteria", [])
        if task_ac and isinstance(task_ac, list):
            ac_criteria = ac_criteria or task_ac  # prefer task AC
        task_vc = _safe_getattr(task, "verification_commands", [])
        if task_vc and isinstance(task_vc, list):
            verif_commands = verif_commands or task_vc
        task_title = _safe_getattr(task, "title", task_title)

    # --- Bind file evidence ---
    if all_files:
        for f in all_files:
            bindings.append(
                RuntimeEvidenceBinding(
                    source=RuntimeEvidenceSource.FILE_EXISTENCE,
                    path=str(f),
                    summary=f"File produced or modified: {f}",
                    passed=True,
                )
            )
            bindings.append(
                RuntimeEvidenceBinding(
                    source=RuntimeEvidenceSource.FILE_MODIFIED,
                    path=str(f),
                    summary=f"File exists on disk: {f}",
                    passed=True,
                )
            )
    else:
        bindings.append(
            RuntimeEvidenceBinding(
                source=RuntimeEvidenceSource.FILE_EXISTENCE,
                summary="No files were produced or modified.",
                passed=False,
            )
        )

    # --- Bind command evidence ---
    if verif_commands:
        is_echo = _has_echo_only_verification(verif_commands)
        for cmd in verif_commands:
            stripped = cmd.strip()
            echo_only = stripped.startswith("echo ") and not any(
                kw in stripped
                for kw in (
                    "$(",
                    "`",
                    "|",
                    "&&",
                    "||",
                    "test ",
                    "grep ",
                    "pytest",
                    "ruff",
                )
            )
            bindings.append(
                RuntimeEvidenceBinding(
                    source=RuntimeEvidenceSource.COMMAND_OUTPUT,
                    summary=f"Verification command: {stripped[:80]}",
                    passed=not echo_only,
                    is_echo_only=echo_only,
                    details=f"Command: {stripped[:120]}",
                )
            )
        if is_echo:
            failures.append(
                "All verification commands are echo-only. Real checks required."
            )

    # --- Bind test result evidence ---
    verif_plan = None
    if verification_result is not None:
        verif_plan = _safe_getattr(verification_result, "verification_plan", None)
    if verif_plan is not None or qg_result is not None:
        bindings.append(
            RuntimeEvidenceBinding(
                source=RuntimeEvidenceSource.TEST_RESULT,
                summary=f"Verification gate status: {final_status or 'unknown'}",
                passed=final_status in ("passed", "PASSED"),
            )
        )

    # --- Bind QA behavior evidence ---
    ac_texts = [*ac_criteria, stdout, stderr]
    has_behavior = _check_behavior_keywords(ac_texts)
    if task_role in ("verifier", "qa_engineer"):
        bindings.append(
            RuntimeEvidenceBinding(
                source=RuntimeEvidenceSource.QA_BEHAVIOR,
                summary="QA behavior check: "
                + (
                    "behavior/edge-case checks detected."
                    if has_behavior
                    else "no behavior/edge-case checks found."
                ),
                passed=has_behavior,
            )
        )
        if not has_behavior:
            warnings.append("QA/verification task lacks behavior or edge-case checks.")

    # --- Bind security evidence ---
    if task_role in ("security_engineer", "verifier"):
        sec_texts = ac_texts + verif_commands
        has_sec = _check_security_keywords(sec_texts)
        bindings.append(
            RuntimeEvidenceBinding(
                source=RuntimeEvidenceSource.SECURITY_CHECK,
                summary="Security check: "
                + (
                    "security-focused checks detected."
                    if has_sec
                    else "no security checks found."
                ),
                passed=has_sec,
            )
        )
        if not has_sec:
            warnings.append(
                "Security task lacks concrete security verification checks."
            )

    # --- Bind acceptance criteria evidence ---
    if ac_criteria:
        bindings.append(
            RuntimeEvidenceBinding(
                source=RuntimeEvidenceSource.ACCEPTANCE_CRITERIA,
                summary=f"{len(ac_criteria)} acceptance criteria defined.",
                passed=len(ac_criteria) > 0,
            )
        )

    # --- Bind arbiter evidence ---
    if arbiter_action:
        bindings.append(
            RuntimeEvidenceBinding(
                source=RuntimeEvidenceSource.ARBITER_DECISION,
                summary=f"Arbiter decision: {arbiter_action}",
                passed=arbiter_action in ("approve", "retry"),
            )
        )

    # --- Determine overall status ---
    has_files = len(all_files) > 0
    has_real_cmds = _has_real_verification(verif_commands)
    has_behavior_ev = _check_behavior_keywords([*ac_criteria, stdout, stderr])
    has_security_ev = _check_security_keywords(
        ac_criteria + verif_commands + [stdout, stderr]
    )
    has_arbiter_ev = bool(arbiter_action)

    all_passed = all(b.passed for b in bindings)
    if (
        not all_passed
        and task_role in ("verifier", "qa_engineer")
        and _has_echo_only_verification(verif_commands)
    ):
        overall = RuntimeEvidenceBindingStatus.BLOCKED
    elif failures:
        overall = RuntimeEvidenceBindingStatus.FAILED
    elif warnings:
        overall = RuntimeEvidenceBindingStatus.WARNING
    elif all_passed or bindings:
        overall = RuntimeEvidenceBindingStatus.BOUND
    else:
        overall = RuntimeEvidenceBindingStatus.NOT_APPLICABLE

    summary_parts = [f"task={task_id or 'unknown'}"]
    if has_files:
        summary_parts.append(f"files={len(all_files)}")
    else:
        summary_parts.append("no-files")
    summary_parts.append(
        f"cmds={'real' if has_real_cmds else 'echo-only' if verif_commands else 'none'}"
    )
    summary_parts.append(f"status={overall.value}")

    return RuntimeTaskEvidenceBundle(
        task_id=str(task_id),
        task_role=str(task_role),
        task_title=str(task_title),
        bindings=bindings,
        status=overall,
        summary=" | ".join(summary_parts),
        has_files=has_files,
        has_real_commands=has_real_cmds,
        has_behavior_evidence=has_behavior_ev,
        has_security_evidence=has_security_ev,
        has_arbiter_evidence=has_arbiter_ev,
        warnings=warnings,
        failures=failures,
    )


def summarize_runtime_evidence_bundle(bundle: RuntimeTaskEvidenceBundle) -> str:
    """Produce a human-readable summary of extracted runtime evidence."""
    lines: list[str] = []
    lines.append(f"Task Evidence: {bundle.task_id} ({bundle.task_role})")
    lines.append(f"Status: {bundle.status.value.upper()}")
    lines.append(f"Bindings: {bundle.binding_count}")
    lines.append(f"  Files: {'yes' if bundle.has_files else 'no'}")
    lines.append(f"  Real Commands: {'yes' if bundle.has_real_commands else 'no'}")
    lines.append(
        f"  Behavior Evidence: {'yes' if bundle.has_behavior_evidence else 'no'}"
    )
    lines.append(
        f"  Security Evidence: {'yes' if bundle.has_security_evidence else 'no'}"
    )
    lines.append(
        f"  Arbiter Evidence: {'yes' if bundle.has_arbiter_evidence else 'no'}"
    )

    if bundle.warnings:
        lines.append("WARNINGS:")
        lines.extend(f"  ! {w}" for w in bundle.warnings)
    if bundle.failures:
        lines.append("FAILURES:")
        lines.extend(f"  !! {f}" for f in bundle.failures)
    return "\n".join(lines)
