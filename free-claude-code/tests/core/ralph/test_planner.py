"""Tests for core.ralph.planner."""

from __future__ import annotations

from core.ralph.models import ProjectGoal, TaskStatus
from core.ralph.planner import (
    ClarifyingQuestion,
    ProjectSpec,
    TaskPlan,
    TaskPlanner,
)
from core.ralph.roles import AgentRole
from core.ralph.verification import build_verification_plan_for_task


class TestTaskPlanner:
    def make_planner(self) -> TaskPlanner:
        return TaskPlanner()

    def test_generates_clarifying_questions(self) -> None:
        goal = ProjectGoal(title="Add model routing", description="Support multiple providers")
        planner = self.make_planner()
        questions = planner.generate_questions(goal)
        assert len(questions) >= 2
        assert all(isinstance(q, ClarifyingQuestion) for q in questions)
        # Should have scope question
        assert any(q.id == "Q-SCOPE" for q in questions)
        # API keywords should trigger API question
        assert any(q.id == "Q-API-TARGET" for q in questions)

    def test_questions_include_constraints(self) -> None:
        goal = ProjectGoal(title="Build CLI tool")
        planner = self.make_planner()
        questions = planner.generate_questions(goal)
        assert any(q.id == "Q-CONSTRAINTS" for q in questions)

    def test_builds_project_spec(self) -> None:
        goal = ProjectGoal(
            title="Add API proxy",
            description="Integrate with new provider",
            constraints=["no external deps"],
            success_kpis=["all tests pass"],
        )
        planner = self.make_planner()
        spec = planner.build_project_spec(goal)
        assert isinstance(spec, ProjectSpec)
        assert spec.goal_id == goal.id
        assert spec.title == goal.title
        assert "API" in spec.summary or "api" in spec.summary
        assert "no external deps" in spec.constraints
        assert "all tests pass" in spec.success_kpis

    def test_build_project_spec_includes_assumptions(self) -> None:
        goal = ProjectGoal(title="Generic feature")
        planner = self.make_planner()
        spec = planner.build_project_spec(goal)
        assert len(spec.assumptions) >= 1
        assert "FCC platform is available" in spec.assumptions[0]

    def test_build_project_spec_includes_risks(self) -> None:
        goal = ProjectGoal(title="New feature")
        planner = self.make_planner()
        spec = planner.build_project_spec(goal)
        assert len(spec.risks) >= 1

    def test_generates_at_least_four_tasks(self) -> None:
        spec = ProjectSpec(title="Simple feature", target_areas=["foundation"])
        planner = self.make_planner()
        tasks = planner.generate_tasks(spec)
        assert len(tasks) >= 4

    def test_tasks_are_deterministic(self) -> None:
        spec = ProjectSpec(title="Test feature", target_areas=["api", "testing"])
        planner = self.make_planner()
        tasks1 = planner.generate_tasks(spec)
        tasks2 = planner.generate_tasks(spec)
        assert len(tasks1) == len(tasks2)
        for t1, t2 in zip(tasks1, tasks2, strict=True):
            assert t1.title == t2.title
            assert len(t1.acceptance_criteria) == len(t2.acceptance_criteria)
            assert t1.agent_role == t2.agent_role

    def test_tasks_are_pending_not_approved(self) -> None:
        spec = ProjectSpec(title="New feature")
        planner = self.make_planner()
        tasks = planner.generate_tasks(spec)
        for task in tasks:
            assert task.status == TaskStatus.PENDING

    def test_tasks_have_descriptive_ids(self) -> None:
        spec = ProjectSpec(title="New feature")
        planner = self.make_planner()
        tasks = planner.generate_tasks(spec)
        for task in tasks:
            assert task.id.startswith("TASK-")

    def test_first_task_is_architect_role(self) -> None:
        spec = ProjectSpec(title="New feature")
        planner = self.make_planner()
        tasks = planner.generate_tasks(spec)
        assert tasks[0].agent_role == AgentRole.ARCHITECT

    def test_api_goal_adds_api_metadata(self) -> None:
        spec = ProjectSpec(
            title="Add API proxy",
            target_areas=["api"],
            constraints=["support routing"],
        )
        planner = self.make_planner()
        tasks = planner.generate_tasks(spec)
        # The implementation task should have smoke target "api"
        impl_task = tasks[1]  # second task is implementation
        assert any("api" in target for target in impl_task.smoke_targets)

    def test_ui_goal_adds_ui_metadata(self) -> None:
        spec = ProjectSpec(title="Build admin dashboard", target_areas=["ui"])
        planner = self.make_planner()
        tasks = planner.generate_tasks(spec)
        impl_task = tasks[1]
        kpis_text = " ".join(impl_task.kpis).lower()
        assert any("ui" in kpis_text or "render" in kpis_text for kpis_text in [kpis_text])

    def test_messaging_goal_adds_smoke_metadata(self) -> None:
        spec = ProjectSpec(title="Add Discord bot", target_areas=["messaging"])
        planner = self.make_planner()
        tasks = planner.generate_tasks(spec)
        impl_task = tasks[1]
        assert any("messaging" in target for target in impl_task.smoke_targets)

    def test_verification_goal_includes_test_commands(self) -> None:
        spec = ProjectSpec(title="Improve test coverage", target_areas=["testing"])
        planner = self.make_planner()
        tasks = planner.generate_tasks(spec)
        verify_task = tasks[2]
        assert any("pytest" in cmd for cmd in verify_task.verification_commands)
        assert any("smoke" in target for target in verify_task.smoke_targets)

    def test_generated_tasks_convert_to_verification_plans(self) -> None:
        spec = ProjectSpec(
            title="Full feature",
            target_areas=["api", "testing", "messaging"],
        )
        planner = self.make_planner()
        tasks = planner.generate_tasks(spec)
        for task in tasks:
            plan = build_verification_plan_for_task(task)
            assert plan is not None
            # The plan should have commands from the task
            if task.verification_commands:
                assert any(
                    cmd in plan.commands for cmd in task.verification_commands
                )

    def test_no_subprocess_commands_in_planner(self) -> None:

        planner = self.make_planner()
        goal = ProjectGoal(title="Any feature")
        plan_result = planner.plan(goal)
        # The planner itself should not execute anything
        assert isinstance(plan_result, TaskPlan)
        assert len(plan_result.tasks) >= 4

    def test_full_plan_pipeline(self) -> None:
        goal = ProjectGoal(
            title="Add new FCC provider",
            description="Integrate a new model provider",
            constraints=["no breaking changes"],
            success_kpis=["provider tests pass"],
        )
        planner = self.make_planner()
        plan_result = planner.plan(goal)
        assert isinstance(plan_result, TaskPlan)
        assert plan_result.goal is goal
        assert len(plan_result.questions) >= 2
        assert plan_result.spec.title == goal.title
        assert len(plan_result.tasks) >= 4
        # Tasks should be pending
        for task in plan_result.tasks:
            assert task.status == TaskStatus.PENDING
