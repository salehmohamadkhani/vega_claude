"""Tests for TaskPromptBuilder — deterministic prompt construction."""

from __future__ import annotations

from core.ralph.agent_profiles import AgentProfile
from core.ralph.memory import MemoryRecord
from core.ralph.models import ProjectGoal, RalphTask
from core.ralph.prompt_builder import TaskPromptBuilder, TaskPromptContext
from core.ralph.verification import VerificationPlan


def _make_context(**overrides: object) -> TaskPromptContext:
    ctx = TaskPromptContext(
        goal=ProjectGoal(title="Fix the thing", description="Make it work better."),
        task=RalphTask(
            id="TASK-001",
            title="Implement Feature X",
            description="Add the new feature",
            allowed_files=["src/feature_x.py"],
            forbidden_files=["src/secret.py"],
            acceptance_criteria=["Feature works", "Tests pass"],
            verification_commands=["uv run pytest tests/ -q"],
            kpis=["All tests green"],
        ),
        verification_plan=VerificationPlan(
            commands=["uv run pytest tests/ -q"],
            smoke_targets=["api"],
            kpi_descriptions=["All tests green"],
        ),
        agent_profile=AgentProfile(
            agent_role="doer",
            model_role="doer",
            name="Doer",
            description="Implements changes",
            responsibilities=["Write code"],
            constraints=["Do not modify tests"],
        ),
        memory_records=[
            MemoryRecord(
                level="semantic",
                content="The API uses REST",
                tags=["api", "rest"],
            )
        ],
        previous_errors=["Previous attempt hit timeout"],
        constraints=["No provider calls"],
    )
    for key, value in overrides.items():
        setattr(ctx, key, value)
    return ctx


class TestTaskPromptBuilder:
    def setup_method(self) -> None:
        self.builder = TaskPromptBuilder()

    def test_prompt_includes_task_id(self) -> None:
        ctx = _make_context()
        prompt = self.builder.build_task_prompt(ctx)
        assert "TASK-001" in prompt

    def test_prompt_includes_task_title(self) -> None:
        ctx = _make_context()
        prompt = self.builder.build_task_prompt(ctx)
        assert "Implement Feature X" in prompt

    def test_prompt_includes_allowed_files(self) -> None:
        ctx = _make_context()
        prompt = self.builder.build_task_prompt(ctx)
        assert "src/feature_x.py" in prompt

    def test_prompt_includes_forbidden_files(self) -> None:
        ctx = _make_context()
        prompt = self.builder.build_task_prompt(ctx)
        assert "src/secret.py" in prompt

    def test_prompt_includes_acceptance_criteria(self) -> None:
        ctx = _make_context()
        prompt = self.builder.build_task_prompt(ctx)
        assert "Feature works" in prompt
        assert "Tests pass" in prompt

    def test_prompt_includes_verification_commands(self) -> None:
        ctx = _make_context()
        prompt = self.builder.build_task_prompt(ctx)
        assert "uv run pytest tests/ -q" in prompt

    def test_prompt_includes_kpis(self) -> None:
        ctx = _make_context()
        prompt = self.builder.build_task_prompt(ctx)
        assert "All tests green" in prompt

    def test_prompt_includes_previous_errors(self) -> None:
        ctx = _make_context()
        prompt = self.builder.build_task_prompt(ctx)
        assert "Previous attempt hit timeout" in prompt

    def test_prompt_contains_anti_hallucination(self) -> None:
        ctx = _make_context()
        prompt = self.builder.build_task_prompt(ctx)
        assert "Do NOT claim the task is complete" in prompt
        assert "ALL verification commands pass" in prompt

    def test_prompt_deterministic(self) -> None:
        ctx = _make_context()
        prompt1 = self.builder.build_task_prompt(ctx)
        prompt2 = self.builder.build_task_prompt(ctx)
        assert prompt1 == prompt2

    def test_prompt_contains_all_sections(self) -> None:
        ctx = _make_context()
        prompt = self.builder.build_task_prompt(ctx)
        sections = [
            "Project Goal",
            "Task: TASK-001",
            "Allowed Files",
            "Forbidden Files",
            "Acceptance Criteria",
            "Verification Commands",
            "KPIs",
            "Your Role: Doer",
            "Constraints",
            "Previous Errors to Avoid",
            "Relevant Context from Memory",
            "Important",
            "Output Format",
        ]
        for section in sections:
            assert section in prompt, f"Missing section: {section}"

    def test_prompt_contains_scoped_changes_instruction(self) -> None:
        ctx = _make_context()
        prompt = self.builder.build_task_prompt(ctx)
        assert "Keep changes scoped" in prompt
        assert "allowed files" in prompt

    def test_prompt_contains_forbidden_files_instruction(self) -> None:
        ctx = _make_context()
        prompt = self.builder.build_task_prompt(ctx)
        assert "Do NOT modify" in prompt
        assert "forbidden files" in prompt

    def test_prompt_contains_changed_files_instruction(self) -> None:
        ctx = _make_context()
        prompt = self.builder.build_task_prompt(ctx)
        assert "Changed:" in prompt
        assert "filepath" in prompt or "changed" in prompt.lower()
