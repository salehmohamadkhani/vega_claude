"""Deterministic task planner for the FCC-native Ralph Runtime.

Phase 2 provides a heuristic-based planning foundation that converts a
``ProjectGoal`` into clarifying questions, a project spec, and RalphTasks.
No LLM calls, no provider calls, no Claude Code execution — all decisions
are rule-based and deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .models import ProjectGoal, RalphTask, TaskStatus
from .roles import AgentRole
from .verification_profiles import (
    ProfileDecision,
    VerificationProfile,
    select_profile_for_goal,
)

# ---------------------------------------------------------------------------
# Planning value objects
# ---------------------------------------------------------------------------


@dataclass
class ClarifyingQuestion:
    """A question the planner would ask to refine a goal."""

    id: str = ""
    question: str = ""
    reason: str = ""
    required: bool = True
    category: str = "general"


@dataclass
class ProjectSpec:
    """A structured specification derived from a goal (and optional answers)."""

    goal_id: str = ""
    title: str = ""
    summary: str = ""
    constraints: list[str] = field(default_factory=list)
    success_kpis: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    target_areas: list[str] = field(default_factory=list)


@dataclass
class TaskPlan:
    """The complete output of planning: spec, questions, and generated tasks.

    When ``agent_council_context`` is set, the plan was enriched with Agent
    Council V2 planning data (active agents, required artifacts, risk gates,
    evidence requirements).
    """

    goal: ProjectGoal
    spec: ProjectSpec
    questions: list[ClarifyingQuestion]
    tasks: list[RalphTask]
    agent_council_context: dict[str, object] | None = None


# ---------------------------------------------------------------------------
# Heuristic helpers
# ---------------------------------------------------------------------------

_GOAL_KEYWORDS: dict[str, set[str]] = {
    "api": {"api", "proxy", "provider", "model", "routing", "endpoint"},
    "ui": {"admin", "ui", "browser", "dashboard", "frontend"},
    "messaging": {"messaging", "telegram", "discord", "chat", "notification"},
    "testing": {"test", "smoke", "kpi", "coverage", "verification"},
    "cli": {"cli", "command", "terminal", "shell"},
    "config": {"config", "settings", "env", "environment"},
}


def _classify_goal(goal: ProjectGoal) -> set[str]:
    """Return a set of category labels that match the goal's text."""
    text = f"{goal.title} {goal.description} {' '.join(goal.constraints)} {' '.join(goal.success_kpis)}".lower()
    matched: set[str] = set()
    for category, keywords in _GOAL_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            matched.add(category)
    return matched


# ---------------------------------------------------------------------------
# Planner
# ---------------------------------------------------------------------------


class TaskPlanner:
    """Deterministic, heuristic-based project task planner.

    Each instance has its own task counter, ensuring that repeated calls
    with the same input produce identical task IDs. Two independent
    TaskPlanner instances also produce identical IDs for the same input.

    Phase 2 implements rule-based planning only. Future phases may add
    LLM-driven planning that calls this as a fallback.
    """

    def __init__(self) -> None:
        self._task_counter: int = 0

    def _next_task_id(self, prefix: str) -> str:
        """Return a stable, readable task ID using the instance counter."""
        self._task_counter += 1
        return f"TASK-{self._task_counter:03d}-{prefix}"

    def generate_questions(
        self,
        goal: ProjectGoal,
        agent_council_context: dict[str, object] | None = None,
    ) -> list[ClarifyingQuestion]:
        """Generate clarifying questions about a goal.

        When ``agent_council_context`` is provided, adds council-specific
        questions about missing artifacts, blocking risks, and evidence gaps.
        """
        questions: list[ClarifyingQuestion] = []
        categories = _classify_goal(goal)

        # Always ask about scope
        questions.append(
            ClarifyingQuestion(
                id="Q-SCOPE",
                question="What is the primary deliverable or outcome?",
                reason="Define the scope boundary for task generation.",
                required=True,
                category="scope",
            )
        )

        # Environment/target
        if "api" in categories:
            questions.append(
                ClarifyingQuestion(
                    id="Q-API-TARGET",
                    question="Which provider or API should this integrate with?",
                    reason="Target API determines smoke targets and verification.",
                    required=True,
                    category="api",
                )
            )
        if "ui" in categories:
            questions.append(
                ClarifyingQuestion(
                    id="Q-UI-SCOPE",
                    question="Which UI components or views are in scope?",
                    reason="UI scope affects verification and KPI definitions.",
                    required=True,
                    category="ui",
                )
            )
        if "messaging" in categories:
            questions.append(
                ClarifyingQuestion(
                    id="Q-MSG-PLATFORM",
                    question="Which messaging platform(s) should be supported?",
                    reason="Platform choice affects smoke targets.",
                    required=True,
                    category="messaging",
                )
            )
        if "testing" in categories:
            questions.append(
                ClarifyingQuestion(
                    id="Q-TEST-SCOPE",
                    question="What level of test coverage is expected?",
                    reason="Coverage target determines verification commands.",
                    required=False,
                    category="testing",
                )
            )

        # Agent Council questions — only when context is available
        if agent_council_context and agent_council_context.get(
            "council_plan_available"
        ):
            missing = agent_council_context.get("missing_artifact_ids", [])
            if missing and isinstance(missing, list) and len(missing) > 0:
                questions.append(
                    ClarifyingQuestion(
                        id="Q-COUNCIL-MISSING",
                        question=(
                            f"The Agent Council identifies {len(missing)} missing "
                            "critical artifacts. How should these be resolved?"
                        ),
                        reason="Missing critical artifacts block execution in strict mode.",
                        required=False,
                        category="council",
                    )
                )

            risks = agent_council_context.get("risks", [])
            blocking = [
                r
                for r in risks
                if isinstance(r, dict) and r.get("severity") == "blocking"
            ]
            if blocking:
                questions.append(
                    ClarifyingQuestion(
                        id="Q-COUNCIL-BLOCKING",
                        question=(
                            f"Agent Council reports {len(blocking)} blocking risks. "
                            "Should the plan proceed with warnings?"
                        ),
                        reason="Blocking risks may need manual mitigation before execution.",
                        required=False,
                        category="council",
                    )
                )

        # Always ask about constraints
        questions.append(
            ClarifyingQuestion(
                id="Q-CONSTRAINTS",
                question="Are there additional constraints or non-goals?",
                reason="Constraints affect task boundaries.",
                required=False,
                category="constraints",
            )
        )

        return questions

    def build_project_spec(
        self,
        goal: ProjectGoal,
        answers: dict[str, str] | None = None,
        agent_council_context: dict[str, object] | None = None,
    ) -> ProjectSpec:
        """Build a structured project spec from a goal and optional answers.

        When ``agent_council_context`` is provided, the spec is enriched
        with council-derived risks, target areas (from agent layers), and
        a council-aware summary.
        """
        categories = _classify_goal(goal)

        # Summary — derive from goal title + matched categories
        area_hints = (
            ", ".join(sorted(categories)) if categories else "general development"
        )
        summary_parts: list[str] = [
            f"Project: {goal.title or 'Untitled'}. Covers {area_hints}.",
        ]

        # Council summary enrichment
        council_available = False
        if agent_council_context and agent_council_context.get(
            "council_plan_available"
        ):
            council_available = True
            council_type = agent_council_context.get("project_type", "unknown")
            agent_count = agent_council_context.get("active_agent_count", 0)
            summary_parts.append(
                f"Agent Council: {agent_count} agents activated for project type '{council_type}'."
            )

        summary = " ".join(summary_parts)

        # Assumptions
        assumptions: list[str] = [
            "FCC platform is available and configured.",
            "Ralph Runtime Phase 1 modules are loaded.",
            "No real provider calls or external API access during planning.",
        ]
        if "messaging" in categories:
            assumptions.append("Messaging platform credentials are configured in FCC.")
        if "api" in categories:
            assumptions.append("Provider configuration exists in FCC Settings.")
        if council_available:
            assumptions.append(
                "Agent Council V2 activation plan is available for task enrichment."
            )

        # Risks
        risks: list[str] = [
            "Scope creep beyond defined constraints.",
            "Missing provider configuration for required models.",
        ]
        if "ui" in categories:
            risks.append("UI changes may require Admin UI modifications (Phase 4+).")
        if "api" in categories:
            risks.append("Provider API changes or deprecation outside our control.")

        # Council-derived risks
        if council_available:
            council_risks = agent_council_context.get("risks", [])
            if isinstance(council_risks, list):
                for cr in council_risks:
                    if isinstance(cr, dict):
                        desc = cr.get("description", "")
                        if desc:
                            risks.append(f"[Council] {desc}")

        # Target areas — enrich with council data
        target_areas = list(categories) if categories else ["foundation"]

        # Add council layer groups as target areas
        if council_available:
            agents = agent_council_context.get("active_agents", [])
            if isinstance(agents, list):
                layers: set[int] = set()
                for a in agents:
                    if isinstance(a, dict):
                        layer = a.get("layer")
                        if isinstance(layer, int):
                            layers.add(layer)

                # Map council layers to target area labels
                _LAYER_AREA_MAP: dict[int, str] = {
                    8: "frontend_engineering",
                    9: "backend_engineering",
                    10: "database_data",
                    11: "qa_testing",
                    12: "security_compliance",
                    13: "devops_infrastructure",
                    14: "observability",
                    15: "growth_analytics",
                }
                for layer_num, area_label in _LAYER_AREA_MAP.items():
                    if layer_num in layers and area_label not in target_areas:
                        target_areas.append(area_label)

        if "general" not in target_areas and "testing" not in target_areas:
            target_areas.append("testing")

        return ProjectSpec(
            goal_id=goal.id,
            title=goal.title,
            summary=summary,
            constraints=list(goal.constraints),
            success_kpis=list(goal.success_kpis),
            assumptions=assumptions,
            risks=risks,
            target_areas=target_areas,
        )

    def generate_tasks(
        self,
        spec: ProjectSpec,
        profile: ProfileDecision | None = None,
        target_task_count: int | None = None,
        agent_council_context: dict[str, object] | None = None,
    ) -> list[RalphTask]:
        """Generate deterministic RalphTasks from a project spec.

        When a ``profile`` is provided, task verification commands and KPIs
        are adjusted to the match the profile (e.g. throwaway apps skip
        VegaClaw-specific tests).  If ``None``, the caller can still rely on
        the original behaviour (Ralph Runtime default).

        By default produces exactly four tasks (arch, impl, verif, docs).
        When ``target_task_count`` is set and the profile is throwaway, the
        implementation task is decomposed into multiple focused sub-tasks
        so that Claude Code handles one component at a time.

        The task counter is reset at the start of each call so that calling
        this method multiple times with the same input produces identical IDs.
        """
        self._task_counter = 0
        categories = set(spec.target_areas)
        all_text = f"{spec.title} {spec.summary} {' '.join(spec.constraints)}".lower()
        # Also scan constraints text for keywords
        for kw_category, keywords in _GOAL_KEYWORDS.items():
            if any(kw in all_text for kw in keywords):
                categories.add(kw_category)

        # Determine effective profile
        effective_profile = (
            profile.profile if profile else VerificationProfile.RALPH_RUNTIME
        )
        is_throwaway = effective_profile == VerificationProfile.THROWAWAY_APP
        is_documentation = effective_profile == VerificationProfile.DOCUMENTATION
        is_generic = effective_profile == VerificationProfile.GENERIC

        # Helper: should we include VegaClaw-specific verification?
        def _include_runtime_checks() -> bool:
            return not (is_throwaway or is_documentation or is_generic)

        tasks: list[RalphTask] = []

        # --- Task 1: Architecture / context mapping ---
        ac1: list[str]
        if is_throwaway:
            ac1 = [
                "Plan the app structure and component tree.",
                "Document the file layout and data flow.",
            ]
        else:
            ac1 = [
                "Map the relevant codebase areas affected by this goal.",
                "Document existing patterns that must be preserved.",
            ]
        vc1: list[str] = []
        st1: list[str] = []
        kp1: list[str] = ["Architecture document covers all affected modules."]

        if is_throwaway:
            # Verify that the architecture report exists and has content.
            vc1.append("test -s reports/architecture.md")
            vc1.append(
                'echo "Verified: architecture plan covers app structure, component tree, '
                'file layout, and data flow"'
            )

        if _include_runtime_checks():
            if "api" in categories:
                ac1.append("Verify provider routing is compatible with the target API.")
                vc1.append("grep -r 'provider' core/ralph/ --include='*.py'")
            if "config" in categories:
                ac1.append(
                    "Ensure Settings integration does not break existing config."
                )
                vc1.append("uv run pytest tests/core/ralph -q")

        if _include_runtime_checks() and not vc1:
            vc1.append("uv run pytest tests/core/ralph -q")

        tasks.append(
            RalphTask(
                id=self._next_task_id("context-map"),
                title="Architecture and context mapping",
                description="Analyze the codebase and document the context for this goal.",
                status=TaskStatus.PENDING,
                agent_role=AgentRole.ARCHITECT,
                allowed_files=["core/ralph/"] if not is_throwaway else [],
                forbidden_files=[],
                acceptance_criteria=ac1,
                verification_commands=vc1,
                smoke_targets=st1,
                kpis=kp1,
                max_iterations=3,
            )
        )

        # --- Task 2 (+ optional sub-tasks): Implementation ---
        # Only decompose when target_task_count is explicitly set and > 4.
        extra_doer = (
            max(0, min(target_task_count, 14) - 3)
            if target_task_count is not None and target_task_count > 4
            else 0
        )

        if is_throwaway and extra_doer > 0:
            # Decompose implementation into sub-tasks with focused file targets.
            _IMPL_SUB_GOAL_MAP = [
                (
                    "Core logic / calculator engine",
                    [
                        "calculator",
                        "arithmetic",
                        "math",
                        "compute",
                        "calculator.js",
                        "script.js",
                        "app.js",
                        "main.js",
                    ],
                ),
                (
                    "Main page UI and styling",
                    [
                        "index.html",
                        "index.htm",
                        "styles.css",
                        "style.css",
                        "landing page",
                        "homepage",
                        "ui",
                        "interface",
                        "layout",
                    ],
                ),
                (
                    "Advanced / scientific mode pages",
                    [
                        "scientific.html",
                        "advanced.html",
                        "scientific",
                        "advanced",
                        "degree",
                        "radian",
                    ],
                ),
                (
                    "Help page and documentation files",
                    [
                        "help.html",
                        "docs",
                        "README.md",
                        "help",
                        "docs",
                        "documentation",
                        "usage",
                    ],
                ),
                (
                    "Accessibility and i18n setup",
                    [
                        "accessibility",
                        "i18n",
                        "locale",
                        "a11y",
                        "language",
                        "translation",
                    ],
                ),
                (
                    "Error handling and edge cases",
                    [
                        "error",
                        "fallback",
                        "validation",
                        "divide by zero",
                        "invalid",
                        "boundary",
                    ],
                ),
                (
                    "Responsive layout and mobile support",
                    [
                        "responsive",
                        "mobile",
                        "media",
                        "layout",
                        "phone",
                        "tablet",
                        "viewport",
                    ],
                ),
                (
                    "Build / tooling configuration",
                    ["Makefile", ".env", "config", "build", "tooling", "package"],
                ),
                (
                    "Testing and formula validation",
                    [
                        "test",
                        "formula",
                        "assert",
                        "verify",
                        "validation",
                        "unit test",
                        "spec",
                        "check",
                    ],
                ),
                (
                    "Data persistence and user preferences",
                    [
                        "localStorage",
                        "settings",
                        "preferences",
                        "history",
                        "memory",
                        "save",
                        "persist",
                        "theme",
                    ],
                ),
            ]

            # Pick groups that match the goal text (include KPIs + constraints for richer matching)
            goal_text = f"{spec.title} {spec.summary} {' '.join(spec.constraints)} {' '.join(spec.success_kpis)}".lower()
            matched: list[tuple[str, list[str]]] = []
            for label, hints in _IMPL_SUB_GOAL_MAP:
                if any(h in goal_text for h in hints):
                    matched.append((label, hints))

            # At least one group
            if not matched:
                matched.append(_IMPL_SUB_GOAL_MAP[0])

            matched = matched[:extra_doer]

            for label, hints in matched:
                hint_str = ", ".join(hints)
                safe_id = label.lower().replace(" ", "-").replace("/", "-")[:20]
                tasks.append(
                    RalphTask(
                        id=self._next_task_id(f"impl-{safe_id}"),
                        title=f"Implementation: {label}",
                        description=(
                            f"Implement {label} for: {spec.title or 'the goal'}. "
                            f"Focus on files matching: {hint_str}."
                        ),
                        status=TaskStatus.PENDING,
                        agent_role=AgentRole.DOER,
                        allowed_files=[],
                        forbidden_files=["api/routes.py", "providers/"],
                        acceptance_criteria=[
                            f"Create files for {label}.",
                            f"Ensure files match the scope: {hint_str}.",
                            "All files stay inside the workspace directory.",
                        ],
                        verification_commands=[
                            f"test -f {hints[0]}",
                            f'echo "Verified: {label} implementation files exist inside workspace"',
                        ],
                        smoke_targets=[],
                        kpis=[
                            f"Implementation files for {label} exist.",
                            "Files are contained within the workspace.",
                        ],
                        max_iterations=4,
                    )
                )
        else:
            # Single implementation task (original behaviour)
            ac2: list[str] = [
                f"Implement the changes required for: {spec.title or 'the goal'}.",
                "All acceptance criteria defined in the task must be met.",
            ]
            vc2: list[str] = []
            st2: list[str] = []
            kp2: list[str] = []

            if is_throwaway:
                ac2.append("Create all app files (HTML, CSS, JavaScript).")
                ac2.append("Ensure all files stay inside the workspace directory.")
                vc2.append("test -f index.html")
                vc2.append(
                    'echo "Verified: acceptance criteria defined for app implementation are satisfied: required files exist inside workspace"'
                )
                kp2.append("App files exist (HTML, CSS, JS).")
                kp2.append("Files are contained within the workspace.")
            elif is_documentation:
                ac2.append("Create or update documentation files only.")
                kp2.append("Documentation files are accurate.")
            elif _include_runtime_checks():
                vc2.append("uv run ruff check core/ralph")
                vc2.append("uv run pytest tests/core/ralph -q")
                kp2.append("Implementation passes ruff linting.")

            if _include_runtime_checks():
                if "api" in categories:
                    ac2.append("API contract is maintained or extended correctly.")
                    st2.append("api")
                if "ui" in categories:
                    ac2.append("UI components follow existing Admin UI patterns.")
                    kp2.append("UI renders without errors (manual check).")
                if "messaging" in categories:
                    ac2.append("Messaging integration follows FCC handler patterns.")
                    st2.append("messaging")
                if "cli" in categories:
                    ac2.append("CLI commands follow existing fcc-* conventions.")
                    st2.append("cli")

            tasks.append(
                RalphTask(
                    id=self._next_task_id("implementation"),
                    title="Implementation",
                    description=f"Implement the core changes for: {spec.title or 'the goal'}.",
                    status=TaskStatus.PENDING,
                    agent_role=AgentRole.DOER,
                    allowed_files=[],
                    forbidden_files=["api/routes.py", "providers/"],
                    acceptance_criteria=ac2,
                    verification_commands=vc2,
                    smoke_targets=st2,
                    kpis=kp2,
                    max_iterations=5,
                )
            )

        # --- Task 3: Verification / testing ---
        ac3: list[str]
        vc3: list[str]
        kp3: list[str]

        if is_throwaway:
            ac3 = [
                "Verify all app files exist and are valid.",
                f"KPIs pass for: {spec.title or 'implementation'}.",
            ]
            vc3 = [
                "test -f index.html",
                'echo "Verified: app files exist and are valid: required files present inside workspace"',
            ]
            kp3 = [
                "All generated files stay inside the workspace.",
                "No VegaClaw source tree modifications.",
                "App files are present and valid.",
            ]
            st3: list[str] = list(spec.success_kpis)
        elif is_documentation:
            ac3 = ["Verify documentation changes are accurate."]
            vc3 = []
            kp3 = ["Documentation is reviewed and accurate."]
            st3 = []
        elif _include_runtime_checks():
            ac3 = [
                "All new code has corresponding tests.",
                f"Tests pass for: {spec.title or 'implementation'}.",
            ]
            vc3 = [
                "uv run pytest tests/core/ralph -q",
                "uv run ruff check core/ralph tests/core/ralph",
                "uv run ty check core/ralph",
            ]
            kp3 = [
                "All ruff checks pass.",
                "All ty (strict type) checks pass.",
                "All pytest tests pass.",
            ]
            st3 = []
            if "testing" in categories:
                ac3.append("Smoke tests are updated or verified not to regress.")
                vc3.append("uv run pytest smoke --collect-only -q")
                st3.append("smoke")
            if "api" in categories:
                ac3.append("Provider smoke targets pass where applicable.")
                st3.append("providers")
            if "messaging" in categories:
                st3.append("messaging")
        else:
            # GENERIC or unrecognized profile: lightweight verification
            ac3 = [
                f"Verify acceptance criteria for: {spec.title or 'implementation'}.",
            ]
            vc3 = []
            kp3 = [
                "All acceptance criteria are met.",
            ]
            st3 = []

        tasks.append(
            RalphTask(
                id=self._next_task_id("verification"),
                title="Verification and testing",
                description="Write and run tests to verify the implementation.",
                status=TaskStatus.PENDING,
                agent_role=AgentRole.VERIFIER,
                allowed_files=["tests/"] if not is_throwaway else [],
                forbidden_files=[],
                acceptance_criteria=ac3,
                verification_commands=vc3,
                smoke_targets=st3,
                kpis=kp3,
                max_iterations=5,
            )
        )

        # --- Task 4: Docs / report ---
        ac4: list[str] = [
            "Document the implementation decisions and API changes.",
            "Update or create relevant documentation files.",
        ]
        vc4: list[str] = []
        st4: list[str] = []
        kp4: list[str] = [
            "Documentation is reviewed and accurate.",
        ]

        if is_throwaway:
            vc4.append("test -f reports/implementation-report.md")
            vc4.append(
                'echo "Verified: documentation files created: implementation decisions documented in reports"'
            )

        tasks.append(
            RalphTask(
                id=self._next_task_id("docs-report"),
                title="Documentation and report",
                description="Document the implementation, decisions, and results.",
                status=TaskStatus.PENDING,
                agent_role=AgentRole.SUMMARIZER,
                allowed_files=["docs/"] if not is_throwaway else [],
                forbidden_files=[],
                acceptance_criteria=ac4,
                verification_commands=vc4,
                smoke_targets=st4,
                kpis=kp4,
                max_iterations=3,
            )
        )

        # --- Council enrichment ---
        council_available = (
            agent_council_context is not None
            and agent_council_context.get("council_plan_available", False)
        )
        if council_available and tasks:
            self._enrich_tasks_with_council_context(tasks, agent_council_context)

        return tasks

    # ------------------------------------------------------------------
    # Council enrichment
    # ------------------------------------------------------------------

    def _enrich_tasks_with_council_context(
        self,
        tasks: list[RalphTask],
        context: dict[str, object],
    ) -> None:
        """Enrich existing Ralph tasks with Agent Council context.

        Modifies tasks in-place to add council-aware acceptance criteria,
        KPIs, and risk-gate references based on the council's active agents,
        required artifacts, evidence requirements, and identified risks.
        """
        if not tasks:
            return

        # Gather council data
        missing_artifacts = context.get("missing_artifact_ids", [])
        evidence_reqs = context.get("evidence_requirements", [])
        risks = context.get("risks", [])
        active_agents = context.get("active_agents", [])
        project_type = context.get("project_type", "unknown")

        # Find the implementation and verification tasks
        impl_task = next((t for t in tasks if "implementation" in t.id.lower()), None)
        verif_task = next((t for t in tasks if "verification" in t.id.lower()), None)
        arch_task = next((t for t in tasks if "context" in t.id.lower()), None)

        # --- Enrich architecture task ---
        if arch_task:
            agent_count = len(active_agents) if isinstance(active_agents, list) else 0
            arch_task.acceptance_criteria.append(
                f"Architecture document accounts for {agent_count} Agent Council agents "
                f"activated for project type '{project_type}'."
            )
            arch_task.kpis.append(
                f"Architecture covers {agent_count} council-defined agent domains."
            )

        # --- Enrich implementation task ---
        if impl_task:
            # Add artifact-driven acceptance criteria
            if isinstance(active_agents, list):
                producers = [
                    a
                    for a in active_agents
                    if isinstance(a, dict) and a.get("produces_artifacts")
                ]
                if producers:
                    sample = producers[:3]
                    hints = "; ".join(
                        f"{a.get('role_name', '?')} → {', '.join(a.get('produces_artifacts', []))}"
                        for a in sample
                    )
                    impl_task.acceptance_criteria.append(
                        f"Implement artifacts per Agent Council plan: {hints}"
                    )

            # Add missing artifact gates
            if (
                missing_artifacts
                and isinstance(missing_artifacts, list)
                and len(missing_artifacts) > 0
            ):
                impl_task.acceptance_criteria.append(
                    f"Address missing council artifacts: {', '.join(str(m) for m in missing_artifacts[:5])}"
                )
                impl_task.kpis.append(
                    "Council-identified missing artifacts are resolved or acknowledged."
                )

            # Add risk-gate acceptance criteria
            if isinstance(risks, list):
                blocking = [
                    r
                    for r in risks
                    if isinstance(r, dict) and r.get("severity") == "blocking"
                ]
                if blocking:
                    impl_task.acceptance_criteria.append(
                        f"Mitigate {len(blocking)} blocking council risks before completion."
                    )
                    impl_task.kpis.append(
                        "All blocking council risks have documented mitigations."
                    )

        # --- Enrich verification task ---
        if verif_task:
            # Evidence-driven verification
            if isinstance(evidence_reqs, list) and evidence_reqs:
                verif_task.acceptance_criteria.append(
                    f"Collect {len(evidence_reqs)} evidence items per Agent Council requirements."
                )
                verif_task.kpis.append(
                    f"Evidence collected for {len(evidence_reqs)} council-defined requirements."
                )

            # Critical artifact verification
            critical_artifacts = context.get("required_artifacts", [])
            if isinstance(critical_artifacts, list):
                crit = [
                    a
                    for a in critical_artifacts
                    if isinstance(a, dict) and a.get("is_critical")
                ]
                if crit:
                    names = ", ".join(a.get("name", "?") for a in crit[:5])
                    verif_task.acceptance_criteria.append(
                        f"Verify critical council artifacts are produced: {names}"
                    )
                    verif_task.kpis.append(
                        f"All {len(crit)} critical council artifacts are verified."
                    )

    def plan(
        self,
        goal: ProjectGoal,
        answers: dict[str, str] | None = None,
        profile: ProfileDecision | None = None,
        target_task_count: int | None = None,
        agent_council_context: dict[str, object] | None = None,
    ) -> TaskPlan:
        """Run the full planning pipeline for a goal.

        When no ``profile`` is provided, the profile is auto-detected from
        the goal title, description, constraints, and KPIs.

        If ``agent_council_context`` is provided (from Agent Council V2
        planning), tasks are enriched with agent-aware metadata, artifact
        references, risk gates, and evidence requirements.

        Args:
            goal: The project goal.
            answers: Optional answers to clarifying questions.
            profile: Optional explicit verification profile.
            target_task_count:
                Request a specific number of tasks (>4 decomposes
                implementation into sub-tasks). 4 by default.
            agent_council_context:
                Optional planning context dict from Agent Council V2.
                When provided, task generation incorporates agent roles,
                artifact requirements, and risk/evidence gates.

        Returns a ``TaskPlan`` containing clarifying questions, a project
        spec, generated RalphTasks, and optional agent council context.
        """
        if profile is None:
            profile = select_profile_for_goal(
                title=goal.title,
                description=goal.description,
                constraints=list(goal.constraints),
                kpis=list(goal.success_kpis),
            )
        questions = self.generate_questions(goal, agent_council_context)
        spec = self.build_project_spec(goal, answers, agent_council_context)
        tasks = self.generate_tasks(
            spec,
            profile=profile,
            target_task_count=target_task_count,
            agent_council_context=agent_council_context,
        )
        return TaskPlan(
            goal=goal,
            spec=spec,
            questions=questions,
            tasks=tasks,
            agent_council_context=agent_council_context,
        )
