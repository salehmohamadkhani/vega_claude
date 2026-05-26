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
    """The complete output of planning: spec, questions, and generated tasks."""

    goal: ProjectGoal
    spec: ProjectSpec
    questions: list[ClarifyingQuestion]
    tasks: list[RalphTask]


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
# Task ID generation
# ---------------------------------------------------------------------------

_TASK_COUNTER: int = 0


def _next_task_id(prefix: str) -> str:
    """Return a stable, readable task ID."""
    global _TASK_COUNTER
    _TASK_COUNTER += 1
    return f"TASK-{_TASK_COUNTER:03d}-{prefix}"


# ---------------------------------------------------------------------------
# Planner
# ---------------------------------------------------------------------------


class TaskPlanner:
    """Deterministic, heuristic-based project task planner.

    Phase 2 implements rule-based planning only. Future phases may add
    LLM-driven planning that calls this as a fallback.
    """

    def generate_questions(self, goal: ProjectGoal) -> list[ClarifyingQuestion]:
        """Generate clarifying questions about a goal."""
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
    ) -> ProjectSpec:
        """Build a structured project spec from a goal and optional answers."""
        categories = _classify_goal(goal)

        # Summary — derive from goal title + matched categories
        area_hints = ", ".join(sorted(categories)) if categories else "general development"
        summary = (
            f"Project: {goal.title or 'Untitled'}. "
            f"Covers {area_hints}."
        )

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

        # Risks
        risks: list[str] = [
            "Scope creep beyond defined constraints.",
            "Missing provider configuration for required models.",
        ]
        if "ui" in categories:
            risks.append("UI changes may require Admin UI modifications (Phase 4+).")
        if "api" in categories:
            risks.append("Provider API changes or deprecation outside our control.")

        # Target areas
        target_areas = list(categories) if categories else ["foundation"]
        if "general" not in target_areas:
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

    def generate_tasks(self, spec: ProjectSpec) -> list[RalphTask]:
        """Generate deterministic RalphTasks from a project spec.

        Always produces at least four tasks. Metadata is injected based on
        the spec's target areas and constraints.
        """
        categories = set(spec.target_areas)
        all_text = f"{spec.title} {spec.summary} {' '.join(spec.constraints)}".lower()
        # Also scan constraints text for keywords
        for kw_category, keywords in _GOAL_KEYWORDS.items():
            if any(kw in all_text for kw in keywords):
                categories.add(kw_category)

        tasks: list[RalphTask] = []

        # --- Task 1: Architecture / context mapping ---
        ac1: list[str] = [
            "Map the relevant codebase areas affected by this goal.",
            "Document existing patterns that must be preserved.",
        ]
        vc1: list[str] = []
        st1: list[str] = []
        kp1: list[str] = ["Architecture document covers all affected modules."]
        if "api" in categories:
            ac1.append("Verify provider routing is compatible with the target API.")
            vc1.append("grep -r 'provider' core/ralph/ --include='*.py'")
        if "config" in categories:
            ac1.append("Ensure Settings integration does not break existing config.")
            vc1.append("uv run pytest tests/core/ralph -q")
        if not vc1:
            vc1.append("uv run pytest tests/core/ralph -q")

        tasks.append(
            RalphTask(
                id=_next_task_id("context-map"),
                title="Architecture and context mapping",
                description="Analyze the codebase and document the context for this goal.",
                status=TaskStatus.PENDING,
                agent_role=AgentRole.ARCHITECT,
                allowed_files=["core/ralph/"],
                forbidden_files=[],
                acceptance_criteria=ac1,
                verification_commands=vc1,
                smoke_targets=st1,
                kpis=kp1,
                max_iterations=3,
            )
        )

        # --- Task 2: Implementation ---
        ac2: list[str] = [
            f"Implement the changes required for: {spec.title or 'the goal'}.",
            "All acceptance criteria defined in the task must be met.",
        ]
        vc2: list[str] = ["uv run ruff check core/ralph"]
        st2: list[str] = []
        kp2: list[str] = ["Implementation passes ruff linting."]
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
        vc2.append("uv run pytest tests/core/ralph -q")

        tasks.append(
            RalphTask(
                id=_next_task_id("implementation"),
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
        ac3: list[str] = [
            "All new code has corresponding tests.",
            f"Tests pass for: {spec.title or 'implementation'}.",
        ]
        vc3: list[str] = [
            "uv run pytest tests/core/ralph -q",
            "uv run ruff check core/ralph tests/core/ralph",
            "uv run ty check core/ralph",
        ]
        st3: list[str] = []
        kp3: list[str] = [
            "All ruff checks pass.",
            "All ty (strict type) checks pass.",
            "All pytest tests pass.",
        ]
        if "testing" in categories:
            ac3.append("Smoke tests are updated or verified not to regress.")
            vc3.append("uv run pytest smoke --collect-only -q")
            st3.append("smoke")
        if "api" in categories:
            ac3.append("Provider smoke targets pass where applicable.")
            st3.append("providers")
        if "messaging" in categories:
            st3.append("messaging")

        tasks.append(
            RalphTask(
                id=_next_task_id("verification"),
                title="Verification and testing",
                description="Write and run tests to verify the implementation.",
                status=TaskStatus.PENDING,
                agent_role=AgentRole.VERIFIER,
                allowed_files=["tests/"],
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

        tasks.append(
            RalphTask(
                id=_next_task_id("docs-report"),
                title="Documentation and report",
                description="Document the implementation, decisions, and results.",
                status=TaskStatus.PENDING,
                agent_role=AgentRole.SUMMARIZER,
                allowed_files=["docs/"],
                forbidden_files=[],
                acceptance_criteria=ac4,
                verification_commands=vc4,
                smoke_targets=st4,
                kpis=kp4,
                max_iterations=3,
            )
        )

        return tasks

    def plan(
        self,
        goal: ProjectGoal,
        answers: dict[str, str] | None = None,
    ) -> TaskPlan:
        """Run the full planning pipeline for a goal.

        Returns a ``TaskPlan`` containing clarifying questions, a project
        spec, and generated RalphTasks.
        """
        questions = self.generate_questions(goal)
        spec = self.build_project_spec(goal, answers)
        tasks = self.generate_tasks(spec)
        return TaskPlan(goal=goal, spec=spec, questions=questions, tasks=tasks)
