"""Structured task prompt builder for Ralph Runtime.

Builds deterministic prompts for Claude Code from task context,
verification plans, memory records, and agent profiles.

No AI calls, no network — pure string construction.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .agent_profiles import AgentProfile
from .memory import MemoryRecord
from .models import ProjectGoal, RalphTask
from .verification import VerificationPlan


@dataclass
class TaskPromptContext:
    """All context needed to build a prompt for a single task."""

    goal: ProjectGoal | None = None
    task: RalphTask | None = None
    context_snapshot: str = ""
    agent_profile: AgentProfile | None = None
    verification_plan: VerificationPlan | None = None
    memory_records: list[MemoryRecord] = field(default_factory=list)
    previous_errors: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)


class TaskPromptBuilder:
    """Deterministic prompt builder for Ralph Runtime tasks.

    Produces structured prompts with sections for goal, task details,
    verification, constraints, and output instructions.
    """

    def build_task_prompt(self, context: TaskPromptContext) -> str:
        """Build a structured prompt for Claude Code execution.

        Returns a fully-formed prompt string. Deterministic — same
        context always produces the same output.
        """
        parts: list[str] = []
        self._add_project_goal(parts, context)
        self._add_task_details(parts, context)
        self._add_files(parts, context)
        self._add_acceptance_criteria(parts, context)
        self._add_verification(parts, context)
        self._add_kpis(parts, context)
        self._add_agent_role(parts, context)
        self._add_constraints(parts, context)
        self._add_previous_errors(parts, context)
        self._add_memory_records(parts, context)
        self._add_anti_hallucination(parts)
        self._add_output_format(parts)
        return "\n".join(parts)

    # ------------------------------------------------------------------
    # Section builders
    # ------------------------------------------------------------------

    def _add_project_goal(self, parts: list[str], ctx: TaskPromptContext) -> None:
        if ctx.goal and ctx.goal.title:
            parts.append(f"# Project Goal: {ctx.goal.title}")
            if ctx.goal.description:
                parts.append("")
                parts.append(ctx.goal.description)
            parts.append("")

    def _add_task_details(self, parts: list[str], ctx: TaskPromptContext) -> None:
        task = ctx.task
        if task is None:
            return
        parts.append(f"## Task: {task.id}")
        parts.append("")
        if task.title:
            parts.append(f"### {task.title}")
            parts.append("")
        if task.description:
            parts.append(task.description)
            parts.append("")

    def _add_files(self, parts: list[str], ctx: TaskPromptContext) -> None:
        task = ctx.task
        if task is None:
            return
        if task.allowed_files:
            parts.append("### Allowed Files")
            parts.extend(f"- {f}" for f in task.allowed_files)
            parts.append("")
            parts.append("Keep changes scoped to the allowed files listed above.")
            parts.append("")
        if task.forbidden_files:
            parts.append("### Forbidden Files")
            parts.extend(f"- {f}" for f in task.forbidden_files)
            parts.append("")
            parts.append("Do NOT modify any forbidden files.")
            parts.append("")

    def _add_acceptance_criteria(
        self, parts: list[str], ctx: TaskPromptContext
    ) -> None:
        task = ctx.task
        if task is None or not task.acceptance_criteria:
            return
        parts.append("### Acceptance Criteria")
        parts.extend(f"- [ ] {ac}" for ac in task.acceptance_criteria)
        parts.append("")

    def _add_verification(self, parts: list[str], ctx: TaskPromptContext) -> None:
        plan = ctx.verification_plan
        if plan is None:
            return
        has_commands = bool(plan.commands)
        has_smoke = bool(plan.smoke_targets)
        if not has_commands and not has_smoke:
            return

        parts.append("### Verification Commands")
        parts.append("")
        if has_commands:
            parts.append("Run these commands to verify your work:")
            parts.append("")
            parts.append("```bash")
            parts.extend(plan.commands)
            parts.append("```")
            parts.append("")
        if has_smoke:
            parts.append("Smoke targets to verify:")
            parts.extend(f"- {target}" for target in plan.smoke_targets)
            parts.append("")

    def _add_kpis(self, parts: list[str], ctx: TaskPromptContext) -> None:
        plan = ctx.verification_plan
        if plan is None or not plan.kpi_descriptions:
            return
        parts.append("### KPIs")
        parts.extend(f"- {kpi}" for kpi in plan.kpi_descriptions)
        parts.append("")

    def _add_agent_role(self, parts: list[str], ctx: TaskPromptContext) -> None:
        profile = ctx.agent_profile
        if profile is None:
            return
        parts.append(f"### Your Role: {profile.name}")
        parts.append("")
        if profile.description:
            parts.append(profile.description)
            parts.append("")
        if profile.responsibilities:
            parts.append("Responsibilities:")
            parts.extend(f"- {r}" for r in profile.responsibilities)
            parts.append("")
        if profile.constraints:
            parts.append("Role Constraints:")
            parts.extend(f"- {c}" for c in profile.constraints)
            parts.append("")

    def _add_constraints(self, parts: list[str], ctx: TaskPromptContext) -> None:
        all_constraints = list(ctx.constraints)
        if ctx.agent_profile:
            all_constraints.extend(ctx.agent_profile.constraints)
        if not all_constraints:
            return
        parts.append("### Constraints")
        parts.extend(f"- {c}" for c in all_constraints)
        parts.append("")

    def _add_previous_errors(self, parts: list[str], ctx: TaskPromptContext) -> None:
        if not ctx.previous_errors:
            return
        parts.append("### Previous Errors to Avoid")
        parts.extend(f"- {err}" for err in ctx.previous_errors)
        parts.append("")

    def _add_memory_records(self, parts: list[str], ctx: TaskPromptContext) -> None:
        if not ctx.memory_records:
            return
        parts.append("### Relevant Context from Memory")
        for record in ctx.memory_records:
            parts.append(f"- [{record.level}] {record.content}")
            if record.tags:
                parts.append(f"  Tags: {', '.join(record.tags)}")
        parts.append("")

    def _add_anti_hallucination(self, parts: list[str]) -> None:
        parts.append("### Important")
        parts.append(
            "Do NOT claim the task is complete unless ALL verification commands pass."
        )
        parts.append("")

    def _add_output_format(self, parts: list[str]) -> None:
        parts.append("### Output Format")
        parts.append(
            "When done, summarize: "
            "1) What files were changed "
            "2) Whether verification passed "
            "3) Any issues encountered"
        )
        parts.append("")
        parts.append(
            "For each changed file, include a line starting with "
            "'Changed: <filepath>' so changes can be tracked."
        )
        parts.append("")
