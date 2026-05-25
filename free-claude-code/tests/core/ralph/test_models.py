"""Tests for core.ralph.models."""

from __future__ import annotations

import pytest

from core.ralph.models import (
    CriticDecision,
    IterationStatus,
    ProjectGoal,
    RalphIteration,
    RalphRun,
    RalphTask,
    RunStatus,
    TaskStatus,
    run_status_from_str,
    task_status_from_str,
)
from core.ralph.roles import AgentRole


class TestProjectGoal:
    def test_can_create(self) -> None:
        goal = ProjectGoal(title="Test Goal", description="A test")
        assert goal.title == "Test Goal"
        assert goal.description == "A test"
        assert goal.id is not None
        assert goal.created_at is not None
        assert goal.constraints == []
        assert goal.success_kpis == []

    def test_with_constraints_and_kpis(self) -> None:
        goal = ProjectGoal(
            title="Build feature",
            constraints=["no external deps"],
            success_kpis=["all tests pass", "latency < 200ms"],
        )
        assert "no external deps" in goal.constraints
        assert "all tests pass" in goal.success_kpis
        assert len(goal.success_kpis) == 2


class TestRalphTask:
    def test_can_create(self) -> None:
        task = RalphTask(title="Implement login")
        assert task.title == "Implement login"
        assert task.status == TaskStatus.PENDING
        assert task.agent_role == AgentRole.DOER
        assert task.max_iterations == 10
        assert task.allowed_files == []
        assert task.forbidden_files == []

    def test_default_status_is_pending(self) -> None:
        task = RalphTask()
        assert task.status == TaskStatus.PENDING

    def test_with_all_fields(self) -> None:
        task = RalphTask(
            title="Add tests",
            description="Write unit tests for auth",
            status=TaskStatus.APPROVED,
            agent_role=AgentRole.CRITIC,
            allowed_files=["src/auth/"],
            forbidden_files=["src/secrets/"],
            acceptance_criteria=["covers edge cases"],
            verification_commands=["pytest tests/auth"],
            smoke_targets=["smoke/auth"],
            kpis=["100% coverage"],
            max_iterations=5,
        )
        assert task.status == TaskStatus.APPROVED
        assert task.agent_role == AgentRole.CRITIC
        assert len(task.allowed_files) == 1
        assert task.max_iterations == 5

    def test_max_iterations_must_be_positive(self) -> None:
        with pytest.raises(ValueError, match="max_iterations"):
            RalphTask(max_iterations=0)

    def test_statuses_are_stable(self) -> None:
        """Verify enum values don't change unintentionally."""
        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.APPROVED.value == "approved"
        assert TaskStatus.RUNNING.value == "running"
        assert TaskStatus.VERIFYING.value == "verifying"
        assert TaskStatus.NEEDS_FIX.value == "needs_fix"
        assert TaskStatus.PASSED.value == "passed"
        assert TaskStatus.FAILED.value == "failed"
        assert TaskStatus.BLOCKED.value == "blocked"
        assert TaskStatus.CANCELLED.value == "cancelled"


class TestRalphRun:
    def test_can_contain_tasks(self) -> None:
        task1 = RalphTask(title="Task 1")
        task2 = RalphTask(title="Task 2")
        run = RalphRun(tasks=[task1, task2])
        assert len(run.tasks) == 2
        assert run.current_task_id == task1.id

    def test_default_status_is_created(self) -> None:
        run = RalphRun()
        assert run.status == RunStatus.CREATED

    def test_add_task(self) -> None:
        run = RalphRun()
        task = RalphTask(title="New task")
        run.add_task(task)
        assert len(run.tasks) == 1
        assert run.current_task_id == task.id

    def test_current_task_returns_none_when_empty(self) -> None:
        run = RalphRun()
        assert run.current_task() is None

    def test_current_task_returns_correct_task(self) -> None:
        task = RalphTask(title="Active")
        run = RalphRun(tasks=[task])
        assert run.current_task() == task

    def test_advance_to_next_task(self) -> None:
        t1 = RalphTask(title="First")
        t2 = RalphTask(title="Second")
        run = RalphRun(tasks=[t1, t2])
        run.advance_to_next_task()
        assert run.current_task_id == t2.id

    def test_advance_past_last_returns_none(self) -> None:
        t1 = RalphTask(title="Only")
        run = RalphRun(tasks=[t1])
        result = run.advance_to_next_task()
        assert result is None
        assert run.current_task_id is None


class TestRalphIteration:
    def test_can_create(self) -> None:
        it = RalphIteration(run_id="run1", task_id="task1", iteration_number=1)
        assert it.run_id == "run1"
        assert it.task_id == "task1"
        assert it.iteration_number == 1
        assert it.status == IterationStatus.STARTED

    def test_summary_defaults_to_empty(self) -> None:
        it = RalphIteration()
        assert it.summary == ""


class TestCriticDecision:
    def test_default_is_not_approved(self) -> None:
        d = CriticDecision()
        assert d.approved is False

    def test_confidence_must_be_in_range(self) -> None:
        CriticDecision(confidence=0.0)
        CriticDecision(confidence=1.0)
        with pytest.raises(ValueError, match="confidence"):
            CriticDecision(confidence=-0.1)
        with pytest.raises(ValueError, match="confidence"):
            CriticDecision(confidence=1.1)

    def test_with_fixes(self) -> None:
        d = CriticDecision(
            approved=False,
            reason="Missing error handling",
            required_fixes=["add try/except"],
            confidence=0.8,
        )
        assert d.approved is False
        assert len(d.required_fixes) == 1
        assert d.confidence == 0.8


class TestStatusParsing:
    def test_task_status_from_str(self) -> None:
        assert task_status_from_str("pending") == TaskStatus.PENDING
        assert task_status_from_str("PASSED") == TaskStatus.PASSED
        assert task_status_from_str("NEEDS_FIX") == TaskStatus.NEEDS_FIX

    def test_task_status_from_str_unknown(self) -> None:
        with pytest.raises(ValueError, match="Unknown TaskStatus"):
            task_status_from_str("bogus")

    def test_run_status_from_str(self) -> None:
        assert run_status_from_str("created") == RunStatus.CREATED
        assert run_status_from_str("COMPLETED") == RunStatus.COMPLETED

    def test_run_status_from_str_unknown(self) -> None:
        with pytest.raises(ValueError, match="Unknown RunStatus"):
            run_status_from_str("bogus")
