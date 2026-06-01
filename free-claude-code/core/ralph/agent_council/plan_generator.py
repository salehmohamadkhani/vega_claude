"""Agent Council V2 — Council Plan Generator.

Deterministic plan generator that produces a complete CouncilPlanResult
from a CouncilPlanRequest.

The generator uses:
- Default agent registry (56 agents)
- Default artifact contracts (33 contracts)
- Activation planner (8 project types)
- Dependency graph (topological sort, cycle detection, parallel groups)
- Research map (when available)
- Evidence model (basic requirements generation)

No LLM calls. No network access. No execution of agents.
"""

from __future__ import annotations

from .activation import ActivationPlanner
from .artifact_contracts import ContractRegistry, load_default_contracts
from .dependency_graph import detect_cycles
from .plan import (
    CouncilPlanAgentNode,
    CouncilPlanArtifactNode,
    CouncilPlanEvidenceRequirement,
    CouncilPlanNextAction,
    CouncilPlanRequest,
    CouncilPlanResearchReference,
    CouncilPlanResult,
    CouncilPlanRisk,
    RiskSeverity,
)
from .registry import AgentRegistry, load_default_registry
from .research_map import ResearchMap

# ---------------------------------------------------------------------------
# Known project types (mirrors activation.py)
# ---------------------------------------------------------------------------

_KNOWN_PROJECT_TYPES: frozenset[str] = frozenset(
    {
        "landing_page",
        "static_site",
        "frontend_app",
        "full_stack_app",
        "saas_product",
        "ai_tool",
        "internal_tool",
        "research_project",
    }
)

# Critical artifacts that must exist for execution to proceed
_CRITICAL_ARTIFACTS: frozenset[str] = frozenset(
    {
        "business_brief",
        "product_requirements_doc",
        "security_requirements",
        "architecture_spec",
        "test_plan",
        "deployment_plan",
    }
)

# Agents that are considered "required" for most project types
_REQUIRED_AGENTS: frozenset[str] = frozenset(
    {
        "chief_vision_officer",
        "orchestrator",
        "product_manager",
    }
)


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------


class CouncilPlanGenerator:
    """Deterministic generator for Council Plans.

    Given a CouncilPlanRequest, produces a complete CouncilPlanResult
    answering all 10 council planning questions.
    """

    def __init__(
        self,
        registry: AgentRegistry | None = None,
        contracts: ContractRegistry | None = None,
        planner: ActivationPlanner | None = None,
        research_map: ResearchMap | None = None,
    ) -> None:
        self._registry = registry or load_default_registry()
        self._contracts = contracts or load_default_contracts(self._registry)
        self._planner = planner or ActivationPlanner(self._registry)
        self._research = research_map

    # -- Properties -----------------------------------------------------------

    @property
    def registry(self) -> AgentRegistry:
        return self._registry

    @property
    def contracts(self) -> ContractRegistry:
        return self._contracts

    @property
    def planner(self) -> ActivationPlanner:
        return self._planner

    # -- Main entry point -----------------------------------------------------

    def generate(self, request: CouncilPlanRequest) -> CouncilPlanResult:
        """Generate a complete Council Plan from a request.

        Args:
            request: A CouncilPlanRequest with project goal, type, and options.

        Returns:
            A CouncilPlanResult answering all 10 planning questions.
        """
        warnings: list[str] = []

        # ---- 1. Resolve project type ------------------------------------
        project_type = self._resolve_project_type(request, warnings)

        # ---- 2. Detect dependency cycles -------------------------------
        cycles = detect_cycles(self._registry)
        if cycles:
            return self._blocked(
                request=request,
                project_type=project_type,
                next_action=CouncilPlanNextAction.BLOCKED_BY_DEPENDENCY_CYCLE,
                reason=f"Dependency cycle(s) detected: {cycles[0]}",
                warnings=tuple(warnings),
            )

        # ---- 3. Get activation plan ------------------------------------
        plan = self._planner.plan(project_type)

        # ---- 4. Apply requested/excluded agent overrides ----------------
        active_agent_ids: frozenset[str] = self._apply_agent_overrides(
            plan.active_agents, request
        )

        # ---- 5. Check for missing required agents ----------------------
        if request.strict_mode:
            missing_required = self._check_required_agents(active_agent_ids)
            if missing_required:
                return self._blocked(
                    request=request,
                    project_type=project_type,
                    next_action=CouncilPlanNextAction.BLOCKED_BY_MISSING_REQUIRED_AGENT,
                    reason=f"Required agents missing: {', '.join(sorted(missing_required))}",
                    warnings=tuple(warnings),
                )

        # ---- 6. Build agent nodes --------------------------------------
        agent_nodes = self._build_agent_nodes(active_agent_ids, plan.parallel_groups)

        # ---- 7. Build artifact nodes -----------------------------------
        artifact_nodes = self._build_artifact_nodes(
            active_agent_ids, request.available_artifacts
        )

        # ---- 8. Identify missing artifacts -----------------------------
        missing = self._identify_missing_artifacts(
            artifact_nodes, project_type, request
        )

        # ---- 9. Generate risks -----------------------------------------
        risks = self._generate_risks(project_type, missing, request, warnings, cycles)

        # ---- 10. Research references -----------------------------------
        research_refs = self._collect_research_references(active_agent_ids, request)

        # ---- 11. Evidence requirements ---------------------------------
        evidence_reqs = self._generate_evidence_requirements(
            project_type, missing, active_agent_ids
        )

        # ---- 12. Determine next action ---------------------------------
        next_action, is_ready = self._determine_next_action(
            project_type=project_type,
            missing_artifacts=missing,
            risks=risks,
            request=request,
            cycles=cycles,
            active_agent_ids=active_agent_ids,
            warnings=warnings,
        )

        # ---- 13. Build critical path -----------------------------------
        cp = list(plan.critical_path) if plan.critical_path else list(active_agent_ids)

        # ---- 14. Build summary -----------------------------------------
        summary = self._build_summary(
            project_type=project_type,
            request=request,
            active_agent_ids=active_agent_ids,
            missing=missing,
            risks=risks,
            next_action=next_action,
            is_ready=is_ready,
        )

        # ---- 15. Contract IDs ------------------------------------------
        contract_ids = tuple(
            sorted(
                c.artifact_id
                for c in self._contracts.list_all()
                if c.artifact_id in plan.required_artifacts
            )
        )

        return CouncilPlanResult(
            project_type=project_type,
            project_goal=request.project_goal,
            active_agents=agent_nodes,
            critical_path=tuple(cp),
            parallel_groups=self._filter_parallel_groups(
                plan.parallel_groups, active_agent_ids
            ),
            required_artifacts=artifact_nodes,
            missing_artifacts=tuple(sorted(missing)),
            artifact_contracts=contract_ids,
            research_references=research_refs,
            evidence_requirements=evidence_reqs,
            risks=tuple(risks),
            next_action=next_action,
            is_ready_to_execute=is_ready,
            summary=summary,
            warnings=tuple(warnings),
            total_phases=len(plan.parallel_groups),
            total_active_agents=len(active_agent_ids),
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_project_type(
        self,
        request: CouncilPlanRequest,
        warnings: list[str],
    ) -> str:
        """Resolve the project type, handling unknowns gracefully."""
        ptype = request.project_type.strip().lower() if request.project_type else ""

        if not ptype:
            # Try to infer from goal (simple heuristic)
            ptype = self._infer_project_type(request.project_goal)

        if ptype not in _KNOWN_PROJECT_TYPES:
            warnings.append(
                f"Project type '{ptype}' is not in the known set: "
                f"{', '.join(sorted(_KNOWN_PROJECT_TYPES))}. "
                f"Falling back to 'full_stack_app'."
            )
            # Fall back to full_stack_app if strict_mode is False
            if not request.strict_mode:
                return "full_stack_app"
            return ptype  # Caller handles the unknown type

        return ptype

    @staticmethod
    def _infer_project_type(goal: str) -> str:
        """Simple keyword-based project type inference. Never fails.

        Most-specific match wins — e.g. 'saas' beats 'full stack' even though
        CRM-like goals often contain words that match both.
        """
        goal_lower = goal.lower()
        # Order matters: check more specific types first
        ordered_types: list[tuple[str, list[str]]] = [
            (
                "saas_product",
                [
                    "saas",
                    "subscription",
                    "multi-tenant",
                    "b2b saas",
                    "software as a service",
                ],
            ),
            (
                "ai_tool",
                [
                    "ai ",
                    "ai-",
                    " ml ",
                    "machine learning",
                    "llm",
                    "gpt",
                    "neural network",
                    "chatbot",
                ],
            ),
            (
                "landing_page",
                [
                    "landing page",
                    "landing",
                    "one-page",
                    "single page",
                    "splash",
                    "coming soon",
                ],
            ),
            (
                "static_site",
                ["static site", "blog", "portfolio", "docs site", "documentation site"],
            ),
            (
                "frontend_app",
                ["spa", "single page app", "frontend only", "client-side"],
            ),
            (
                "internal_tool",
                ["internal tool", "admin tool", "internal dashboard", "back office"],
            ),
            (
                "research_project",
                [
                    "research paper",
                    "research analysis",
                    "research study",
                    "investigation",
                ],
            ),
            (
                "full_stack_app",
                [
                    "full stack",
                    "full-stack",
                    "web app",
                    "web application",
                    "crm",
                    "dashboard",
                ],
            ),
        ]
        for ptype, kws in ordered_types:
            if any(kw in goal_lower for kw in kws):
                return ptype
        return "full_stack_app"  # safe default

    def _apply_agent_overrides(
        self,
        active_agents: tuple[str, ...],
        request: CouncilPlanRequest,
    ) -> frozenset[str]:
        """Apply requested_agents and excluded_agents overrides."""
        agent_set = set(active_agents)

        # Add explicitly requested agents (if they exist in registry)
        for agent_id in request.requested_agents:
            if self._registry.get_optional(agent_id) is not None:
                agent_set.add(agent_id)

        # Remove explicitly excluded agents
        for agent_id in request.excluded_agents:
            agent_set.discard(agent_id)

        return frozenset(agent_set)

    @staticmethod
    def _check_required_agents(
        active_agent_ids: frozenset[str],
    ) -> set[str]:
        """Check which required agents are missing from activation set."""
        return set(_REQUIRED_AGENTS) - set(active_agent_ids)

    def _build_agent_nodes(
        self,
        active_agent_ids: frozenset[str],
        parallel_groups: tuple[tuple[str, ...], ...],
    ) -> tuple[CouncilPlanAgentNode, ...]:
        """Build CouncilPlanAgentNode for each active agent."""
        # Build phase lookup
        phase_map: dict[str, int] = {}
        for i, group in enumerate(parallel_groups):
            for aid in group:
                if aid in active_agent_ids:
                    phase_map[aid] = i

        nodes: list[CouncilPlanAgentNode] = []
        for aid in sorted(active_agent_ids):
            agent = self._registry.get_optional(aid)
            if agent is None:
                continue
            # Filter dependencies to only active agents
            active_deps = tuple(d for d in agent.dependencies if d in active_agent_ids)
            nodes.append(
                CouncilPlanAgentNode(
                    agent_id=agent.agent_id,
                    role_name=agent.role_name,
                    layer=agent.layer,
                    phase=phase_map.get(aid, 0),
                    depends_on=active_deps,
                    produces_artifacts=agent.produced_artifacts,
                    can_run_parallel=agent.can_run_parallel,
                )
            )

        return tuple(nodes)

    def _build_artifact_nodes(
        self,
        active_agent_ids: frozenset[str],
        available_artifacts: tuple[str, ...],
    ) -> tuple[CouncilPlanArtifactNode, ...]:
        """Build CouncilPlanArtifactNode for all artifacts in scope."""
        available_set = frozenset(available_artifacts)

        # Collect all artifacts produced by active agents
        produced_by_active: dict[str, str] = {}  # artifact_id -> owner_agent_id
        for agent in self._registry.list_all():
            if agent.agent_id in active_agent_ids:
                for art_id in agent.produced_artifacts:
                    produced_by_active[art_id] = agent.agent_id

        nodes: list[CouncilPlanArtifactNode] = []
        for art_id, owner in sorted(produced_by_active.items()):
            contract = self._contracts.get_optional(art_id)
            name = contract.name if contract else art_id
            is_critical = art_id in _CRITICAL_ARTIFACTS

            status = "available" if art_id in available_set else "pending"

            nodes.append(
                CouncilPlanArtifactNode(
                    artifact_id=art_id,
                    name=name,
                    owner_agent=owner,
                    status=status,
                    consumers=contract.consumers if contract else (),
                    is_critical=is_critical,
                )
            )

        return tuple(nodes)

    def _identify_missing_artifacts(
        self,
        artifact_nodes: tuple[CouncilPlanArtifactNode, ...],
        project_type: str,
        request: CouncilPlanRequest,
    ) -> list[str]:
        """Identify which required artifacts are truly missing.

        An artifact is only "missing" if it is NOT already available AND
        no active agent in the plan produces it. Artifacts that active
        agents WILL produce are not missing — they are pending.

        In non-strict mode, returns empty list (warnings only).
        In strict mode, missing critical artifacts block execution.
        """
        if not request.strict_mode:
            return []

        available_set = frozenset(request.available_artifacts)
        produced_by_active = {n.artifact_id for n in artifact_nodes}

        missing = [
            art_id
            for art_id in _CRITICAL_ARTIFACTS
            if art_id not in available_set and art_id not in produced_by_active
        ]

        return missing

    def _generate_risks(
        self,
        project_type: str,
        missing_artifacts: list[str],
        request: CouncilPlanRequest,
        warnings: list[str],
        _cycles: list[tuple[str, ...]],
    ) -> list[CouncilPlanRisk]:
        """Generate risks based on project context."""
        risks: list[CouncilPlanRisk] = []

        # Missing critical artifacts
        if missing_artifacts:
            risks.append(
                CouncilPlanRisk(
                    risk_id="missing_critical_artifacts",
                    description=(
                        f"Critical artifacts missing: {', '.join(sorted(missing_artifacts))}"
                    ),
                    severity=RiskSeverity.BLOCKING
                    if request.strict_mode
                    else RiskSeverity.HIGH,
                    affected_artifacts=tuple(sorted(missing_artifacts)),
                    mitigation="Produce the missing artifacts before execution or relax strict_mode.",
                )
            )

        # Unknown project type warning
        if project_type not in _KNOWN_PROJECT_TYPES and request.strict_mode:
            risks.append(
                CouncilPlanRisk(
                    risk_id="unknown_project_type",
                    description=f"Project type '{project_type}' is not in the known set.",
                    severity=RiskSeverity.BLOCKING,
                    mitigation="Select a known project type or disable strict_mode.",
                )
            )

        # Warnings as low-severity risks
        for i, w in enumerate(warnings):
            risks.append(
                CouncilPlanRisk(
                    risk_id=f"warning_{i}",
                    description=w,
                    severity=RiskSeverity.LOW,
                )
            )

        # SaaS-specific risks
        if project_type == "saas_product":
            risks.append(
                CouncilPlanRisk(
                    risk_id="saas_complexity",
                    description="SaaS products have high complexity with 50+ agents activated across all 17 layers.",
                    severity=RiskSeverity.MEDIUM,
                    mitigation="Ensure artifact contracts are validated at each quality gate.",
                )
            )

        # AI tool ethics risk
        if project_type == "ai_tool":
            risks.append(
                CouncilPlanRisk(
                    risk_id="ml_ethics_required",
                    description="AI tools require ethics audit. Chief Product Ethics Officer must be activated.",
                    severity=RiskSeverity.HIGH,
                    affected_agents=("chief_product_ethics_officer",),
                    mitigation="Ensure ethics_audit_report is produced before release.",
                )
            )

        return risks

    def _collect_research_references(
        self,
        active_agent_ids: frozenset[str],
        request: CouncilPlanRequest,
    ) -> tuple[CouncilPlanResearchReference, ...]:
        """Collect research references from the research map."""
        research_root = request.research_root if request.research_root else ""
        rm = ResearchMap(research_root) if research_root else self._research

        if rm is None or not rm.is_available:
            return ()

        rm.load()
        refs: list[CouncilPlanResearchReference] = []
        for aid in sorted(active_agent_ids):
            agent_refs = rm.find_for_agent(aid)
            refs.extend(
                CouncilPlanResearchReference(
                    repo_id=ar.repo_id,
                    category=ar.category,
                    relevance_agent=ar.relevance_agent,
                    relevance_level=ar.relevance_level,
                    patterns=ar.patterns,
                )
                for ar in agent_refs
            )

        return tuple(refs)

    def _generate_evidence_requirements(
        self,
        project_type: str,
        missing_artifacts: list[str],
        active_agent_ids: frozenset[str],
    ) -> tuple[CouncilPlanEvidenceRequirement, ...]:
        """Generate basic evidence requirements for the plan."""
        reqs: list[CouncilPlanEvidenceRequirement] = []

        # Standard evidence requirements for all project types
        reqs.append(
            CouncilPlanEvidenceRequirement(
                requirement_id="ev_project_goal_validated",
                description="Project goal has been validated against known constraints.",
                priority="high",
            )
        )

        # Architecture evidence
        if "software_architect" in active_agent_ids:
            reqs.append(
                CouncilPlanEvidenceRequirement(
                    requirement_id="ev_architecture_decisions",
                    description="Architecture decisions have documented rationale and trade-offs.",
                    required_for_agent="software_architect",
                    required_for_artifact="architecture_spec",
                    source_hint="Agent output: software_architect",
                    priority="high",
                )
            )

        # Security evidence
        if "security_engineer" in active_agent_ids:
            reqs.append(
                CouncilPlanEvidenceRequirement(
                    requirement_id="ev_threat_model",
                    description="Threat model covers OWASP Top 10 with documented mitigations.",
                    required_for_agent="security_engineer",
                    required_for_artifact="security_requirements",
                    source_hint="Agent output: security_engineer",
                    priority="high",
                )
            )

        # Missing artifact evidence
        if missing_artifacts:
            reqs.append(
                CouncilPlanEvidenceRequirement(
                    requirement_id="ev_missing_artifacts",
                    description=f"Evidence of why critical artifacts are missing: {', '.join(missing_artifacts)}",
                    priority="high",
                )
            )

        # QA evidence
        if "qa_engineer" in active_agent_ids:
            reqs.append(
                CouncilPlanEvidenceRequirement(
                    requirement_id="ev_test_coverage",
                    description="Test coverage report with pass/fail/blocked counts.",
                    required_for_agent="qa_engineer",
                    required_for_artifact="QA_report",
                    source_hint="Agent output: qa_engineer",
                    priority="medium",
                )
            )

        # Ethics for AI/ML
        if project_type == "ai_tool" or "ml_engineer" in active_agent_ids:
            reqs.append(
                CouncilPlanEvidenceRequirement(
                    requirement_id="ev_model_evaluation",
                    description="Model evaluation metrics with bias/fairness assessment.",
                    required_for_agent="ml_engineer",
                    required_for_artifact="ml_system_design",
                    source_hint="Agent output: ml_engineer",
                    priority="high",
                )
            )

        return tuple(reqs)

    def _determine_next_action(
        self,
        project_type: str,
        missing_artifacts: list[str],
        risks: list[CouncilPlanRisk],
        request: CouncilPlanRequest,
        cycles: list[tuple[str, ...]],
        active_agent_ids: frozenset[str],
        warnings: list[str],
    ) -> tuple[CouncilPlanNextAction, bool]:
        """Determine the next action Ralph should take."""

        # 1. Unknown project type (blocking)
        if request.strict_mode and project_type not in _KNOWN_PROJECT_TYPES:
            return CouncilPlanNextAction.BLOCKED_BY_UNKNOWN_PROJECT_TYPE, False

        # 2. Dependency cycle (blocking)
        if cycles:
            return CouncilPlanNextAction.BLOCKED_BY_DEPENDENCY_CYCLE, False

        # 3. Missing critical artifacts in strict mode (blocking)
        if missing_artifacts and request.strict_mode:
            return CouncilPlanNextAction.NEEDS_MISSING_ARTIFACTS, False

        # 4. Missing required agents in strict mode
        if request.strict_mode:
            missing_req = self._check_required_agents(active_agent_ids)
            if missing_req:
                return CouncilPlanNextAction.BLOCKED_BY_MISSING_REQUIRED_AGENT, False

        # 5. Scope unclear (no goal or too short)
        if len(request.project_goal.strip()) < 5:
            return CouncilPlanNextAction.NEEDS_SCOPE_CLARIFICATION, False

        # 6. Warnings in non-strict mode — still ready but with warnings
        blocking_risks = [r for r in risks if r.severity == RiskSeverity.BLOCKING]
        if blocking_risks:
            return CouncilPlanNextAction.NEEDS_MISSING_ARTIFACTS, False

        # 7. Ready
        return CouncilPlanNextAction.READY_FOR_RUNTIME_PLANNING, True

    def _build_summary(
        self,
        project_type: str,
        request: CouncilPlanRequest,
        active_agent_ids: frozenset[str],
        missing: list[str],
        risks: list[CouncilPlanRisk],
        next_action: CouncilPlanNextAction,
        is_ready: bool,
    ) -> str:
        """Build a human-readable summary."""
        lines: list[str] = []
        lines.append(f"Council Plan for: {request.project_goal}")
        lines.append(f"Project Type: {project_type}")
        lines.append(f"Active Agents: {len(active_agent_ids)}")
        lines.append("Required Artifacts: (see artifact list)")
        lines.append(f"Missing Critical Artifacts: {len(missing)}")
        if missing:
            lines.append(f"  -> {', '.join(missing)}")
        lines.append(f"Risks Identified: {len(risks)}")
        blocking = [r for r in risks if r.severity == RiskSeverity.BLOCKING]
        if blocking:
            lines.append(f"  -> Blocking risks: {len(blocking)}")
        high = [r for r in risks if r.severity == RiskSeverity.HIGH]
        if high:
            lines.append(f"  -> High risks: {len(high)}")
        lines.append(f"Next Action: {next_action.value}")
        lines.append(f"Ready to Execute: {'Yes' if is_ready else 'No'}")
        if not is_ready:
            label_lookup: dict[CouncilPlanNextAction, str] = {
                CouncilPlanNextAction.READY_FOR_RUNTIME_PLANNING: "Ready — proceed to runtime task planning",
                CouncilPlanNextAction.NEEDS_MISSING_ARTIFACTS: "Blocked — missing required artifacts must be produced first",
                CouncilPlanNextAction.NEEDS_SCOPE_CLARIFICATION: "Blocked — project scope needs clarification",
                CouncilPlanNextAction.BLOCKED_BY_DEPENDENCY_CYCLE: "Blocked — dependency cycle detected",
                CouncilPlanNextAction.BLOCKED_BY_UNKNOWN_PROJECT_TYPE: "Blocked — unknown project type",
                CouncilPlanNextAction.BLOCKED_BY_MISSING_REQUIRED_AGENT: "Blocked — required agent not available",
            }
            lines.append(
                f"  -> {label_lookup.get(next_action, str(next_action.value))}"
            )
        return "\n".join(lines)

    def _filter_parallel_groups(
        self,
        groups: tuple[tuple[str, ...], ...],
        active_agent_ids: frozenset[str],
    ) -> tuple[tuple[str, ...], ...]:
        """Filter parallel groups to only include active agents."""
        filtered: list[tuple[str, ...]] = []
        for group in groups:
            active_in_group = tuple(aid for aid in group if aid in active_agent_ids)
            if active_in_group:
                filtered.append(active_in_group)
        return tuple(filtered)

    def _blocked(
        self,
        request: CouncilPlanRequest,
        project_type: str,
        next_action: CouncilPlanNextAction,
        reason: str,
        warnings: tuple[str, ...],
    ) -> CouncilPlanResult:
        """Build a blocked CouncilPlanResult."""
        return CouncilPlanResult(
            project_type=project_type,
            project_goal=request.project_goal,
            active_agents=(),
            critical_path=(),
            parallel_groups=(),
            required_artifacts=(),
            missing_artifacts=(),
            artifact_contracts=(),
            research_references=(),
            evidence_requirements=(),
            risks=(
                CouncilPlanRisk(
                    risk_id=next_action.value,
                    description=reason,
                    severity=RiskSeverity.BLOCKING,
                ),
            ),
            next_action=next_action,
            is_ready_to_execute=False,
            summary=f"BLOCKED: {reason}",
            warnings=warnings,
        )


# ---------------------------------------------------------------------------
# Convenience factory
# ---------------------------------------------------------------------------


def generate_council_plan(request: CouncilPlanRequest) -> CouncilPlanResult:
    """Generate a Council Plan from a request using the default generator.

    Convenience function — equivalent to:
        CouncilPlanGenerator().generate(request)
    """
    return CouncilPlanGenerator().generate(request)
