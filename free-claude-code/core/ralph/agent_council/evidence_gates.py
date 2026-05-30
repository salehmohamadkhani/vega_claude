"""Agent Council V2 — Evidence Gates.

Deterministic evidence gate models and default gate implementations.

Gate purpose: prevent beautiful reports with missing artifacts, fake-pass
tasks, shallow verification, missing files hidden behind summaries, agent
claims without supporting evidence, and final arbiter approvals without
concrete evidence.

No LLM calls. No network access. No shell command execution.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field

from .models import EvidenceItem

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class EvidenceGateSeverity(enum.Enum):
    """Severity of an evidence gate violation or requirement."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class EvidenceGateStatus(enum.Enum):
    """Result status of evaluating an evidence gate."""

    PASSED = "passed"
    WARNING = "warning"
    FAILED = "failed"
    BLOCKED = "blocked"
    NOT_APPLICABLE = "not_applicable"


# ---------------------------------------------------------------------------
# Gate data models
# ---------------------------------------------------------------------------


@dataclass
class EvidenceGateRequirement:
    """A single evidence gate that must be satisfied for completeness.

    Defines what must be checked, what constitutes a pass/fail, and
    which agents/task-roles the gate applies to.
    """

    gate_id: str
    name: str = ""
    description: str = ""
    required_evidence_types: tuple[str, ...] = ()
    required_paths: tuple[str, ...] = ()
    required_artifacts: tuple[str, ...] = ()
    applies_to_agents: tuple[str, ...] = ()
    applies_to_task_roles: tuple[str, ...] = ()
    applies_to_layers: tuple[int, ...] = ()
    blocking: bool = False
    severity: EvidenceGateSeverity = EvidenceGateSeverity.ERROR
    # Config
    min_evidence_count: int = 1
    min_file_size_bytes: int = 1
    exclusive_paths: tuple[str, ...] = ()  # paths that must NOT exist
    exclusive_patterns: tuple[str, ...] = ()  # patterns that must NOT appear


@dataclass
class EvidenceGateFinding:
    """A single finding produced by evaluating a gate."""

    gate_id: str
    status: EvidenceGateStatus = EvidenceGateStatus.NOT_APPLICABLE
    message: str = ""
    details: str = ""
    affected_paths: list[str] = field(default_factory=list)
    affected_artifacts: list[str] = field(default_factory=list)
    required_action: str = ""
    severity: EvidenceGateSeverity = EvidenceGateSeverity.INFO


@dataclass
class EvidenceGateResult:
    """Complete result of running all applicable evidence gates."""

    gate_id: str = ""  # overall result identifier
    findings: list[EvidenceGateFinding] = field(default_factory=list)
    overall_status: EvidenceGateStatus = EvidenceGateStatus.NOT_APPLICABLE
    gates_run: int = 0
    gates_passed: int = 0
    gates_warned: int = 0
    gates_failed: int = 0
    gates_blocked: int = 0
    gates_skipped: int = 0
    blocking_issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    summary: str = ""

    @property
    def is_ready(self) -> bool:
        """True if there are no blocking issues and no failed critical gates."""
        return len(self.blocking_issues) == 0

    @property
    def has_warnings(self) -> bool:
        """True if any gate produced warnings."""
        return len(self.warnings) > 0 or self.gates_warned > 0


# ---------------------------------------------------------------------------
# Gate evaluation context
# ---------------------------------------------------------------------------


@dataclass
class GateEvaluationContext:
    """Context needed to evaluate evidence gates.

    All fields are optional — gates degrade gracefully when data is missing.
    """

    project_type: str = ""
    project_goal: str = ""
    active_agent_ids: tuple[str, ...] = ()
    active_task_roles: tuple[str, ...] = ()
    active_layers: tuple[int, ...] = ()
    required_artifacts: tuple[str, ...] = ()
    missing_artifacts: tuple[str, ...] = ()
    evidence_items: tuple[EvidenceItem, ...] = ()
    available_paths: tuple[str, ...] = ()
    available_file_sizes: dict[str, int] = field(default_factory=dict)
    verification_commands: tuple[str, ...] = ()
    acceptance_criteria: tuple[str, ...] = ()
    research_references: tuple[str, ...] = ()  # repo_ids
    staged_paths: tuple[str, ...] = ()
    strict_mode: bool = False


# ---------------------------------------------------------------------------
# Default gate implementations
# ---------------------------------------------------------------------------


def _gate_artifact_exists(ctx: GateEvaluationContext) -> EvidenceGateFinding:
    """Gate: Required output artifacts must exist or be explicitly marked unavailable."""
    missing: list[str] = []
    for art in ctx.required_artifacts:
        if art not in ctx.available_paths and art not in ctx.missing_artifacts:
            missing.append(art)

    if not ctx.required_artifacts:
        return EvidenceGateFinding(
            gate_id="artifact_exists_gate",
            status=EvidenceGateStatus.NOT_APPLICABLE,
            message="No required artifacts to check.",
        )

    if missing:
        if ctx.strict_mode:
            return EvidenceGateFinding(
                gate_id="artifact_exists_gate",
                status=EvidenceGateStatus.BLOCKED,
                message=f"Missing required artifacts: {', '.join(missing)}",
                affected_artifacts=missing,
                required_action="Produce the missing artifacts or mark them as explicitly unavailable.",
                severity=EvidenceGateSeverity.CRITICAL,
            )
        return EvidenceGateFinding(
            gate_id="artifact_exists_gate",
            status=EvidenceGateStatus.WARNING,
            message=f"Missing required artifacts (non-strict): {', '.join(missing)}",
            affected_artifacts=missing,
            severity=EvidenceGateSeverity.WARNING,
        )

    return EvidenceGateFinding(
        gate_id="artifact_exists_gate",
        status=EvidenceGateStatus.PASSED,
        message=f"All {len(ctx.required_artifacts)} required artifacts accounted for.",
    )


def _gate_artifact_non_empty(ctx: GateEvaluationContext) -> EvidenceGateFinding:
    """Gate: Required text/code/report artifacts must not be empty."""
    empty_files: list[str] = []
    checked = 0
    for path, size in ctx.available_file_sizes.items():
        if path in ctx.required_artifacts or any(
            path.endswith(ext) for ext in (".md", ".py", ".json", ".txt", ".yaml", ".html", ".css", ".js")
        ):
            checked += 1
            if size == 0:
                empty_files.append(path)

    if checked == 0:
        return EvidenceGateFinding(
            gate_id="artifact_non_empty_gate",
            status=EvidenceGateStatus.NOT_APPLICABLE,
            message="No artifact files available for non-empty check.",
        )

    if empty_files:
        return EvidenceGateFinding(
            gate_id="artifact_non_empty_gate",
            status=EvidenceGateStatus.FAILED,
            message=f"Empty artifact files detected: {', '.join(empty_files[:5])}",
            affected_paths=empty_files,
            required_action="Populate or regenerate empty artifact files.",
            severity=EvidenceGateSeverity.ERROR,
        )

    return EvidenceGateFinding(
        gate_id="artifact_non_empty_gate",
        status=EvidenceGateStatus.PASSED,
        message=f"All {checked} checked files are non-empty.",
    )


def _gate_claim_has_evidence(ctx: GateEvaluationContext) -> EvidenceGateFinding:
    """Gate: Important claims must have at least one EvidenceItem backing them."""
    if not ctx.evidence_items:
        return EvidenceGateFinding(
            gate_id="claim_has_evidence_gate",
            status=EvidenceGateStatus.WARNING,
            message="No evidence items provided for claims.",
            required_action="Attach evidence items to agent claims before proceeding.",
            severity=EvidenceGateSeverity.WARNING,
        )

    # Validate each evidence item
    valid_count = sum(1 for e in ctx.evidence_items if e.is_valid())
    total = len(ctx.evidence_items)

    if valid_count == 0:
        return EvidenceGateFinding(
            gate_id="claim_has_evidence_gate",
            status=EvidenceGateStatus.FAILED,
            message=f"No valid evidence items out of {total} provided.",
            required_action="Provide at least one valid evidence item with source_path and claim.",
            severity=EvidenceGateSeverity.ERROR,
        )

    return EvidenceGateFinding(
        gate_id="claim_has_evidence_gate",
        status=EvidenceGateStatus.PASSED,
        message=f"{valid_count}/{total} evidence items are valid.",
    )


def _gate_implementation_file(ctx: GateEvaluationContext) -> EvidenceGateFinding:
    """Gate: Implementation tasks must produce or modify expected files."""
    doer_roles = {"doer"}
    if ctx.active_task_roles and not any(r in doer_roles for r in ctx.active_task_roles):
        return EvidenceGateFinding(
            gate_id="implementation_file_gate",
            status=EvidenceGateStatus.NOT_APPLICABLE,
            message="No doer tasks active — implementation file gate skipped.",
        )

    if not ctx.available_paths:
        return EvidenceGateFinding(
            gate_id="implementation_file_gate",
            status=EvidenceGateStatus.WARNING,
            message="No implementation output files detected.",
            required_action="Implementation tasks must produce at least one output file.",
            severity=EvidenceGateSeverity.WARNING,
        )

    return EvidenceGateFinding(
        gate_id="implementation_file_gate",
        status=EvidenceGateStatus.PASSED,
        message=f"{len(ctx.available_paths)} file(s) available for review.",
    )


def _gate_verification_command(ctx: GateEvaluationContext) -> EvidenceGateFinding:
    """Gate: Verification must include real commands, not echo-only padding."""
    verifier_types = {"verifier", "qa_engineer"}
    if ctx.active_task_roles and not any(r in verifier_types for r in ctx.active_task_roles):
        return EvidenceGateFinding(
            gate_id="verification_command_gate",
            status=EvidenceGateStatus.NOT_APPLICABLE,
            message="No verifier/QA tasks active — verification command gate skipped.",
        )

    if not ctx.verification_commands:
        return EvidenceGateFinding(
            gate_id="verification_command_gate",
            status=EvidenceGateStatus.FAILED,
            message="No verification commands defined for verifier tasks.",
            required_action="Add at least one deterministic verification command.",
            severity=EvidenceGateSeverity.ERROR,
        )

    # Detect echo-only commands
    echo_only: list[str] = []
    real_commands: list[str] = []
    for cmd in ctx.verification_commands:
        stripped = cmd.strip()
        if stripped.startswith("echo ") and not any(
            kw in stripped for kw in ("$(", "`", "|", "&&", "||", "test ", "grep ", "pytest", "ruff")
        ):
            echo_only.append(stripped[:60])
        else:
            real_commands.append(stripped[:60])

    if not real_commands and echo_only:
        return EvidenceGateFinding(
            gate_id="verification_command_gate",
            status=EvidenceGateStatus.FAILED,
            message=f"All {len(echo_only)} verification commands are echo-only. Real checks required.",
            details=f"Echo-only commands: {'; '.join(echo_only)}",
            required_action="Add verification commands that check real behavior (test, grep, pytest, ruff, etc.).",
            severity=EvidenceGateSeverity.ERROR,
        )

    if echo_only:
        return EvidenceGateFinding(
            gate_id="verification_command_gate",
            status=EvidenceGateStatus.WARNING,
            message=f"{len(echo_only)} echo-only command(s) alongside {len(real_commands)} real check(s).",
            required_action="Replace echo-only commands with real checks, or remove them.",
            severity=EvidenceGateSeverity.WARNING,
        )

    return EvidenceGateFinding(
        gate_id="verification_command_gate",
        status=EvidenceGateStatus.PASSED,
        message=f"All {len(real_commands)} verification command(s) appear substantive.",
    )


def _gate_qa_behavior(ctx: GateEvaluationContext) -> EvidenceGateFinding:
    """Gate: QA must check behavior, edge cases, or AC, not just file existence."""
    if "qa_engineer" not in ctx.active_agent_ids and "verifier" not in ctx.active_task_roles:
        return EvidenceGateFinding(
            gate_id="qa_behavior_gate",
            status=EvidenceGateStatus.NOT_APPLICABLE,
            message="No QA or verifier agents active.",
        )

    behavior_keywords = {"edge", "regression", "coverage", "acceptance", "behavior",
                         "fail", "error", "corner", "boundary", "input", "output",
                         "state", "component", "integration", "e2e", "end-to-end"}
    ac_text = " ".join(ctx.acceptance_criteria).lower()
    vc_text = " ".join(ctx.verification_commands).lower()

    has_behavior_checks = any(kw in ac_text for kw in behavior_keywords) or \
                          any(kw in vc_text for kw in behavior_keywords)

    if not has_behavior_checks:
        return EvidenceGateFinding(
            gate_id="qa_behavior_gate",
            status=EvidenceGateStatus.WARNING,
            message="QA/verification lacks behavior/edge-case checks in acceptance criteria or commands.",
            required_action="Add behavior-focused acceptance criteria (edge cases, regression, coverage).",
            severity=EvidenceGateSeverity.WARNING,
        )

    return EvidenceGateFinding(
        gate_id="qa_behavior_gate",
        status=EvidenceGateStatus.PASSED,
        message="QA/verification includes behavior, edge-case, or acceptance criteria checks.",
    )


def _gate_security_evidence(ctx: GateEvaluationContext) -> EvidenceGateFinding:
    """Gate: Security must include concrete checks (scan, secret, config, threat)."""
    security_layers = {12}  # Security / Compliance
    security_agents = {"security_engineer", "penetration_tester", "dependency_auditor"}

    has_security = bool(set(ctx.active_agent_ids) & security_agents) or \
                   bool(set(ctx.active_layers) & security_layers)

    if not has_security:
        return EvidenceGateFinding(
            gate_id="security_evidence_gate",
            status=EvidenceGateStatus.NOT_APPLICABLE,
            message="No security agents active.",
        )

    security_keywords = {"scan", "secret", "owasp", "threat", "vulnerability",
                         "cve", "dependency", "penetration", "auth", "csrf",
                         "xss", "injection", "compliance", "gdpr", "audit"}
    vc_text = " ".join(ctx.verification_commands).lower()
    ac_text = " ".join(ctx.acceptance_criteria).lower()
    combined = vc_text + " " + ac_text

    has_checks = any(kw in combined for kw in security_keywords)
    has_security_artifacts = any(
        art in ctx.required_artifacts
        for art in ("security_requirements", "threat_model", "pentest_report",
                    "dependency_audit_report", "security_review")
    )

    if not has_checks and not has_security_artifacts:
        status = EvidenceGateStatus.BLOCKED if ctx.strict_mode else EvidenceGateStatus.FAILED
        return EvidenceGateFinding(
            gate_id="security_evidence_gate",
            status=status,
            message="Security agents active but no security-focused checks or artifacts defined.",
            required_action="Add security verification commands (dependency scan, secret scan, threat model).",
            severity=EvidenceGateSeverity.ERROR,
        )

    if not has_checks:
        return EvidenceGateFinding(
            gate_id="security_evidence_gate",
            status=EvidenceGateStatus.WARNING,
            message="Security artifacts present but no explicit security verification commands.",
            required_action="Add concrete security verification commands.",
            severity=EvidenceGateSeverity.WARNING,
        )

    return EvidenceGateFinding(
        gate_id="security_evidence_gate",
        status=EvidenceGateStatus.PASSED,
        message="Security evidence checks are defined.",
    )


def _gate_visual_evidence(ctx: GateEvaluationContext) -> EvidenceGateFinding:
    """Gate: Visual/UI tasks should include visual QA notes or reference checks."""
    visual_agents = {"ui_designer", "ux_designer", "visual_qa_engineer", "accessibility_auditor"}
    if not set(ctx.active_agent_ids) & visual_agents:
        return EvidenceGateFinding(
            gate_id="visual_evidence_gate",
            status=EvidenceGateStatus.NOT_APPLICABLE,
            message="No visual/UI agents active.",
        )

    visual_keywords = {"visual", "design", "ui", "color", "contrast", "wcag",
                       "responsive", "layout", "screen", "pixel", "animation",
                       "component", "dark mode"}
    ac_text = " ".join(ctx.acceptance_criteria).lower()
    vc_text = " ".join(ctx.verification_commands).lower()
    has_checks = any(kw in (ac_text + " " + vc_text) for kw in visual_keywords)

    has_artifacts = any(
        art in ctx.required_artifacts
        for art in ("visual_QA_report", "UI_spec", "design_system",
                    "accessibility_audit_report", "design_fidelity_audit")
    )

    if not has_checks and not has_artifacts:
        return EvidenceGateFinding(
            gate_id="visual_evidence_gate",
            status=EvidenceGateStatus.WARNING,  # warn, not block (screenshots not always available)
            message="Visual/UI agents active but no visual QA checks or artifacts defined.",
            required_action="Add visual QA notes or ensure visual artifacts are tracked.",
            severity=EvidenceGateSeverity.WARNING,
        )

    return EvidenceGateFinding(
        gate_id="visual_evidence_gate",
        status=EvidenceGateStatus.PASSED,
        message="Visual/UI evidence is captured via checks or artifact expectations.",
    )


def _gate_research_reference(ctx: GateEvaluationContext) -> EvidenceGateFinding:
    """Gate: Agent decisions citing external patterns should reference Research Corpus."""
    research_agents = {
        a for a in ctx.active_agent_ids
        if a in ("software_architect", "senior_frontend_developer", "senior_backend_developer",
                 "security_engineer", "data_architect", "api_architect", "database_developer",
                 "devops_engineer", "qa_engineer", "ml_engineer")
    }

    if not research_agents:
        return EvidenceGateFinding(
            gate_id="research_reference_gate",
            status=EvidenceGateStatus.NOT_APPLICABLE,
            message="No research-relevant agents active.",
        )

    if not ctx.research_references:
        return EvidenceGateFinding(
            gate_id="research_reference_gate",
            status=EvidenceGateStatus.WARNING,
            message=f"Research-relevant agents ({len(research_agents)}) active but no research references provided.",
            required_action="Attach Research Corpus references to agent decisions where applicable.",
            severity=EvidenceGateSeverity.WARNING,
        )

    return EvidenceGateFinding(
        gate_id="research_reference_gate",
        status=EvidenceGateStatus.PASSED,
        message=f"{len(ctx.research_references)} research references available.",
    )


def _gate_final_arbiter(ctx: GateEvaluationContext) -> EvidenceGateFinding:
    """Gate: Final approval needs impl, verification, QA, and risk evidence present."""
    if "final_arbiter" not in ctx.active_agent_ids:
        return EvidenceGateFinding(
            gate_id="final_arbiter_gate",
            status=EvidenceGateStatus.NOT_APPLICABLE,
            message="Final Arbiter not active — gate skipped.",
        )

    required_evidence_types = {"test_result", "agent_output"}
    has_types = {e.evidence_type.value for e in ctx.evidence_items}

    # Check that we have evidence from core verification agents
    core_agents = {"qa_engineer", "security_engineer", "performance_tester"}
    evidence_agents = {e.agent_source for e in ctx.evidence_items if e.agent_source}
    missing_agents = core_agents - evidence_agents

    # Check required artifacts for final arbiter
    arbiter_inputs = {"QA_report", "security_review", "performance_report",
                      "release_readiness_report", "deployment_plan"}
    missing_inputs = arbiter_inputs - set(ctx.required_artifacts)

    issues: list[str] = []
    if missing_agents:
        issues.append(f"Missing evidence from: {', '.join(sorted(missing_agents))}")
    if missing_inputs:
        issues.append(f"Missing arbiter input artifacts: {', '.join(sorted(missing_inputs))}")
    if not bool(required_evidence_types & has_types):
        issues.append("No test_result or agent_output evidence items present.")

    if issues:
        status = EvidenceGateStatus.BLOCKED if ctx.strict_mode else EvidenceGateStatus.FAILED
        return EvidenceGateFinding(
            gate_id="final_arbiter_gate",
            status=status,
            message="Final Arbiter cannot approve: " + "; ".join(issues),
            required_action="Collect evidence from QA, security, performance testing, and release readiness before final approval.",
            severity=EvidenceGateSeverity.CRITICAL,
        )

    return EvidenceGateFinding(
        gate_id="final_arbiter_gate",
        status=EvidenceGateStatus.PASSED,
        message="Final Arbiter evidence requirements are satisfied.",
    )


def _gate_no_fake_echo(ctx: GateEvaluationContext) -> EvidenceGateFinding:
    """Gate: Verification must not rely only on echo keyword padding."""
    suspicious_patterns = [
        "echo \"Verified",
        "echo 'Verified",
        "echo Verified",
    ]
    for cmd in ctx.verification_commands:
        for pat in suspicious_patterns:
            if pat in cmd:
                # Check if there's also a real check in the same command
                has_real = any(kw in cmd for kw in ("test ", "grep ", "pytest", "ruff", "curl", "python"))
                if not has_real:
                    return EvidenceGateFinding(
                        gate_id="no_fake_echo_gate",
                        status=EvidenceGateStatus.FAILED,
                        message=f"Verification command appears to be echo-only padding: {cmd[:80]}",
                        required_action="Replace echo verification with real path/tool checks.",
                        severity=EvidenceGateSeverity.ERROR,
                    )

    if not ctx.verification_commands:
        return EvidenceGateFinding(
            gate_id="no_fake_echo_gate",
            status=EvidenceGateStatus.NOT_APPLICABLE,
            message="No verification commands to check.",
        )

    return EvidenceGateFinding(
        gate_id="no_fake_echo_gate",
        status=EvidenceGateStatus.PASSED,
        message="No fake-echo verification commands detected.",
    )


def _gate_runtime_artifact_exclusion(ctx: GateEvaluationContext) -> EvidenceGateFinding:
    """Gate: Runtime artifacts must not be staged for commit."""
    forbidden_patterns = (
        ".fcc/", ".fcc-ralph/", ".claude/", ".env",
        ".git-credentials", "secrets", "credentials",
        "raw_research_repos", "/opt/vega-cloud/research/repos",
        "server_tracker", "logs/",
    )

    violations: list[str] = []
    for path in ctx.staged_paths:
        for pattern in forbidden_patterns:
            if pattern in path:
                violations.append(path)
                break

    if violations:
        return EvidenceGateFinding(
            gate_id="runtime_artifact_exclusion_gate",
            status=EvidenceGateStatus.BLOCKED,
            message=f"Forbidden runtime artifacts staged: {', '.join(violations[:10])}",
            affected_paths=violations,
            required_action="Remove forbidden runtime artifacts from staging area before committing.",
            severity=EvidenceGateSeverity.CRITICAL,
        )

    if not ctx.staged_paths:
        return EvidenceGateFinding(
            gate_id="runtime_artifact_exclusion_gate",
            status=EvidenceGateStatus.NOT_APPLICABLE,
            message="No staged paths to check.",
        )

    return EvidenceGateFinding(
        gate_id="runtime_artifact_exclusion_gate",
        status=EvidenceGateStatus.PASSED,
        message="No forbidden runtime artifacts in staging area.",
    )


# ---------------------------------------------------------------------------
# Gate registry
# ---------------------------------------------------------------------------


_DEFAULT_GATE_FUNCTIONS: dict[str, object] = {
    "artifact_exists_gate": _gate_artifact_exists,
    "artifact_non_empty_gate": _gate_artifact_non_empty,
    "claim_has_evidence_gate": _gate_claim_has_evidence,
    "implementation_file_gate": _gate_implementation_file,
    "verification_command_gate": _gate_verification_command,
    "qa_behavior_gate": _gate_qa_behavior,
    "security_evidence_gate": _gate_security_evidence,
    "visual_evidence_gate": _gate_visual_evidence,
    "research_reference_gate": _gate_research_reference,
    "final_arbiter_gate": _gate_final_arbiter,
    "no_fake_echo_gate": _gate_no_fake_echo,
    "runtime_artifact_exclusion_gate": _gate_runtime_artifact_exclusion,
}

_DEFAULT_GATE_METADATA: tuple[EvidenceGateRequirement, ...] = (
    EvidenceGateRequirement(
        gate_id="artifact_exists_gate",
        name="Artifact Existence Check",
        description="Required output artifacts must exist or be explicitly marked unavailable.",
        applies_to_agents=("chief_vision_officer", "product_manager", "software_architect",
                           "qa_engineer", "security_engineer"),
        applies_to_task_roles=("architect", "doer"),
        blocking=True,
        severity=EvidenceGateSeverity.CRITICAL,
    ),
    EvidenceGateRequirement(
        gate_id="artifact_non_empty_gate",
        name="Artifact Non-Empty Check",
        description="Text/code/report artifacts must not be empty.",
        applies_to_task_roles=("doer", "summarizer", "verifier"),
        blocking=False,
        severity=EvidenceGateSeverity.ERROR,
    ),
    EvidenceGateRequirement(
        gate_id="claim_has_evidence_gate",
        name="Claim Evidence Requirement",
        description="Important claims must have at least one EvidenceItem backing them.",
        applies_to_agents=("final_arbiter", "orchestrator"),
        blocking=False,
        severity=EvidenceGateSeverity.ERROR,
        min_evidence_count=1,
    ),
    EvidenceGateRequirement(
        gate_id="implementation_file_gate",
        name="Implementation File Gate",
        description="Implementation tasks must produce or modify expected files.",
        applies_to_task_roles=("doer",),
        blocking=False,
        severity=EvidenceGateSeverity.WARNING,
    ),
    EvidenceGateRequirement(
        gate_id="verification_command_gate",
        name="Verification Command Gate",
        description="Verification must include real commands or deterministic checks.",
        applies_to_task_roles=("verifier",),
        applies_to_layers=(11,),  # QA / Testing / Verification
        blocking=True,
        severity=EvidenceGateSeverity.ERROR,
    ),
    EvidenceGateRequirement(
        gate_id="qa_behavior_gate",
        name="QA Behavior Gate",
        description="QA must check behavior, edge cases, or acceptance criteria, not just file existence.",
        applies_to_agents=("qa_engineer",),
        applies_to_task_roles=("verifier",),
        applies_to_layers=(11,),
        blocking=False,
        severity=EvidenceGateSeverity.WARNING,
    ),
    EvidenceGateRequirement(
        gate_id="security_evidence_gate",
        name="Security Evidence Gate",
        description="Security must include concrete checks (dep scan, secret scan, config review, threat model).",
        applies_to_agents=("security_engineer", "penetration_tester", "dependency_auditor"),
        applies_to_layers=(12,),
        blocking=True,
        severity=EvidenceGateSeverity.ERROR,
    ),
    EvidenceGateRequirement(
        gate_id="visual_evidence_gate",
        name="Visual Evidence Gate",
        description="Visual/UI tasks should include visual QA notes or screenshots when applicable.",
        applies_to_agents=("ui_designer", "ux_designer", "visual_qa_engineer", "accessibility_auditor"),
        applies_to_layers=(6,),
        blocking=False,  # warn, not block (screenshots not always available)
        severity=EvidenceGateSeverity.WARNING,
    ),
    EvidenceGateRequirement(
        gate_id="research_reference_gate",
        name="Research Reference Gate",
        description="Agent decisions citing external patterns should reference Research Corpus.",
        applies_to_agents=("software_architect", "senior_frontend_developer", "senior_backend_developer",
                           "security_engineer", "data_architect"),
        blocking=False,
        severity=EvidenceGateSeverity.WARNING,
    ),
    EvidenceGateRequirement(
        gate_id="final_arbiter_gate",
        name="Final Arbiter Gate",
        description="Final approval requires implementation, verification, QA, and risk evidence.",
        applies_to_agents=("final_arbiter",),
        applies_to_layers=(17,),
        blocking=True,
        severity=EvidenceGateSeverity.CRITICAL,
    ),
    EvidenceGateRequirement(
        gate_id="no_fake_echo_gate",
        name="No Fake Echo Gate",
        description="Verification must not rely only on echo keyword padding.",
        applies_to_task_roles=("verifier", "doer"),
        blocking=True,
        severity=EvidenceGateSeverity.ERROR,
    ),
    EvidenceGateRequirement(
        gate_id="runtime_artifact_exclusion_gate",
        name="Runtime Artifact Exclusion Gate",
        description="Runtime artifacts (.fcc/, .fcc-ralph/, .claude/, env, logs, raw research repos) must not be staged for commit.",
        applies_to_task_roles=(),
        blocking=True,
        severity=EvidenceGateSeverity.CRITICAL,
        exclusive_paths=(".fcc/", ".fcc-ralph/", ".claude/", ".env",
                         "raw_research_repos", "logs/"),
    ),
)


def get_default_gate_requirements() -> tuple[EvidenceGateRequirement, ...]:
    """Return the 12 default evidence gate requirements."""
    return _DEFAULT_GATE_METADATA


def get_gate_function(gate_id: str):
    """Return the default gate function for a gate ID, or None."""
    fn = _DEFAULT_GATE_FUNCTIONS.get(gate_id)
    if fn is None:
        return None
    if callable(fn):
        return fn
    return None


def list_default_gate_ids() -> tuple[str, ...]:
    """Return all default gate IDs."""
    return tuple(_DEFAULT_GATE_FUNCTIONS.keys())
