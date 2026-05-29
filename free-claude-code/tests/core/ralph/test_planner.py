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
from core.ralph.verification_profiles import (
    select_profile_for_goal,
)


class TestTaskPlanner:
    def make_planner(self) -> TaskPlanner:
        return TaskPlanner()

    def test_generates_clarifying_questions(self) -> None:
        goal = ProjectGoal(
            title="Add model routing", description="Support multiple providers"
        )
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
            assert t1.id == t2.id, f"Task ID mismatch: {t1.id} != {t2.id}"
            assert t1.title == t2.title
            assert len(t1.acceptance_criteria) == len(t2.acceptance_criteria)
            assert t1.agent_role == t2.agent_role

    def test_task_ids_are_stable_across_instances(self) -> None:
        """Two independent TaskPlanner instances must produce identical IDs."""
        spec = ProjectSpec(title="Stable IDs", target_areas=["api"])
        p1 = self.make_planner()
        p2 = self.make_planner()
        tasks1 = p1.generate_tasks(spec)
        tasks2 = p2.generate_tasks(spec)
        for t1, t2 in zip(tasks1, tasks2, strict=True):
            assert t1.id == t2.id, f"Cross-instance ID mismatch: {t1.id} != {t2.id}"

    def test_task_ids_start_at_001(self) -> None:
        """First task should always be TASK-001-context-map."""
        spec = ProjectSpec(title="Fresh start")
        planner = self.make_planner()
        tasks = planner.generate_tasks(spec)
        assert tasks[0].id == "TASK-001-context-map"

    def test_plan_ids_stable_across_repeated_calls(self) -> None:
        """The full plan() pipeline must produce stable IDs."""
        goal = ProjectGoal(title="Stable planning")
        planner = self.make_planner()
        plan1 = planner.plan(goal)
        plan2 = planner.plan(goal)
        for t1, t2 in zip(plan1.tasks, plan2.tasks, strict=True):
            assert t1.id == t2.id

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
        assert any(
            "ui" in kpis_text or "render" in kpis_text for kpis_text in [kpis_text]
        )

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
                assert any(cmd in plan.commands for cmd in task.verification_commands)

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

    # ------------------------------------------------------------------
    # Verification profile integration tests
    # ------------------------------------------------------------------

    def test_calculator_goal_auto_detects_throwaway_profile(self) -> None:
        """Calculator goal should auto-detect THROWAWAY_APP and skip runtime checks."""
        goal = ProjectGoal(
            title="Build a tiny browser calculator app",
            description="HTML, CSS, and JavaScript calculator with add, subtract, multiply, divide",
            success_kpis=[
                "Calculator can add two numbers correctly",
                "All generated files stay inside the pilot workspace",
            ],
        )
        planner = self.make_planner()
        plan_result = planner.plan(goal)

        # All tasks should have no pytest tests/core/ralph verification
        for task in plan_result.tasks:
            for cmd in task.verification_commands:
                assert "pytest" not in cmd, (
                    f"Task {task.id} should not have pytest: {cmd}"
                )
                assert "ruff" not in cmd, (
                    f"Task {task.id} should not have ruff: {cmd}"
                )

    def test_calculator_goal_implementation_checks_file_existence(self) -> None:
        """Throwaway app implementation task should check file existence."""
        goal = ProjectGoal(
            title="Build a calculator app",
            description="HTML and JavaScript calculator",
        )
        planner = self.make_planner()
        plan_result = planner.plan(goal)

        impl_task = plan_result.tasks[1]  # TASK-002
        assert impl_task.id == "TASK-002-implementation"
        assert any("test -f" in cmd or "find " in cmd for cmd in impl_task.verification_commands)

    def test_ralph_runtime_goal_includes_pytest_verification(self) -> None:
        """Ralph Runtime goal should include pytest verification."""
        goal = ProjectGoal(
            title="Add new provider routing to the Ralph Runtime",
            description="Extend the Ralph Runtime to support a new provider type",
        )
        planner = self.make_planner()
        plan_result = planner.plan(goal)

        # At least the implementation and verification tasks should have pytest
        impl_task = plan_result.tasks[1]
        verify_task = plan_result.tasks[2]
        assert any("pytest" in cmd for cmd in impl_task.verification_commands), (
            f"Implementation task should have pytest, got: {impl_task.verification_commands}"
        )
        assert any("pytest" in cmd for cmd in verify_task.verification_commands)

    def test_explicit_throwaway_profile_works(self) -> None:
        """Explicit THROWAWAY_APP profile should skip runtime checks."""
        goal = ProjectGoal(
            title="Dummy goal that looks like runtime work",
            description="But we use throwaway profile explicitly",
        )
        planner = self.make_planner()
        profile = select_profile_for_goal(
            title="Build a calculator",
        )
        plan_result = planner.plan(goal, profile=profile)

        for task in plan_result.tasks:
            for cmd in task.verification_commands:
                assert "pytest" not in cmd
                assert "ruff" not in cmd

    def test_documentation_profile_no_command_verification(self) -> None:
        """Documentation profile should have minimal or no command verification."""
        goal = ProjectGoal(
            title="Update project documentation",
            description="Write docs",
        )
        planner = self.make_planner()
        plan_result = planner.plan(goal)

        for task in plan_result.tasks:
            assert not any("pytest" in cmd for cmd in task.verification_commands)
            assert not any("ruff" in cmd for cmd in task.verification_commands)
            assert not any("ty " in cmd for cmd in task.verification_commands)

    def test_generic_profile_no_runtime_checks(self) -> None:
        """GENERIC profile should not include runtime-specific checks."""
        from core.ralph.verification_profiles import (
            VerificationProfile as _VP,
        )
        from core.ralph.verification_profiles import (
            make_profile_decision,
        )

        goal = ProjectGoal(title="Unrelated task")
        profile = make_profile_decision(_VP.GENERIC)
        planner = self.make_planner()
        plan_result = planner.plan(goal, profile=profile)

        for task in plan_result.tasks:
            for cmd in task.verification_commands:
                assert "pytest" not in cmd
                assert "ruff" not in cmd
