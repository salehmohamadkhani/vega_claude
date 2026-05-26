"""Tests for core.ralph.run_lifecycle."""

from __future__ import annotations

from core.ralph.checkpoint import CheckpointStore
from core.ralph.context_builder import ContextBuilder
from core.ralph.models import ProjectGoal, RalphTask, RunStatus, TaskStatus
from core.ralph.roles import AgentRole
from core.ralph.run_lifecycle import RunLifecycle, RunLifecycleResult
from core.ralph.task_library import TaskLibrary
from core.ralph.workspace import RalphWorkspace


class TestRunLifecycle:
    def make_lifecycle(self, tmp_path) -> RunLifecycle:
        ws = RalphWorkspace(tmp_path)
        ws.initialize()
        return RunLifecycle(
            workspace=ws,
            task_library=TaskLibrary(ws),
            checkpoint_store=CheckpointStore(ws),
            context_builder=ContextBuilder(workspace=ws, repo_root=tmp_path),
        )

    def make_goal(self) -> ProjectGoal:
        return ProjectGoal(id="goal-1", title="Test goal")

    def make_tasks(self) -> list[RalphTask]:
        return [
            RalphTask(
                id="TASK-001",
                title="Task One",
                agent_role=AgentRole.ARCHITECT,
            ),
            RalphTask(
                id="TASK-002",
                title="Task Two",
                agent_role=AgentRole.DOER,
                verification_commands=["echo ok"],
            ),
        ]

    def test_create_run_from_goal(self, tmp_path) -> None:
        lifecycle = self.make_lifecycle(tmp_path)
        goal = self.make_goal()
        run = lifecycle.create_run(goal)
        assert run.goal_id == "goal-1"
        assert run.status == RunStatus.CREATED
        assert run.id is not None

    def test_create_run_with_tasks(self, tmp_path) -> None:
        lifecycle = self.make_lifecycle(tmp_path)
        goal = self.make_goal()
        tasks = self.make_tasks()
        run = lifecycle.create_run(goal, tasks)
        assert len(run.tasks) == 2

    def test_prepare_run_persists_tasks(self, tmp_path) -> None:
        lifecycle = self.make_lifecycle(tmp_path)
        goal = self.make_goal()
        tasks = self.make_tasks()
        lifecycle.prepare_run(goal, tasks)
        # Tasks should be saved
        loaded = lifecycle._task_library.find_task("TASK-001")
        assert loaded is not None
        assert loaded.title == "Task One"

    def test_prepare_run_creates_run_table_entries(self, tmp_path) -> None:
        lifecycle = self.make_lifecycle(tmp_path)
        result = lifecycle.prepare_run(self.make_goal(), self.make_tasks())
        assert result.run_table.entry_count == 2
        entry = result.run_table.get_entry("TASK-001")
        assert entry is not None
        assert entry.status == TaskStatus.PENDING

    def test_prepare_run_creates_initial_checkpoint(self, tmp_path) -> None:
        lifecycle = self.make_lifecycle(tmp_path)
        result = lifecycle.prepare_run(self.make_goal(), self.make_tasks())
        cp = result.checkpoint
        assert cp.run_id == result.run.id
        assert cp.task_id == "TASK-001"
        assert cp.next_action == "start_task"

    def test_prepare_run_creates_context_snapshot(self, tmp_path) -> None:
        lifecycle = self.make_lifecycle(tmp_path)
        result = lifecycle.prepare_run(self.make_goal(), self.make_tasks())
        assert result.context_snapshot.goal_id == "goal-1"
        assert result.context_snapshot.run_id == result.run.id

    def test_prepare_run_saves_paths(self, tmp_path) -> None:
        lifecycle = self.make_lifecycle(tmp_path)
        result = lifecycle.prepare_run(self.make_goal(), self.make_tasks())
        assert len(result.paths) >= 3  # tasks + checkpoint + context + run metadata

    def test_approve_task_changes_status(self, tmp_path) -> None:
        lifecycle = self.make_lifecycle(tmp_path)
        result = lifecycle.prepare_run(self.make_goal(), self.make_tasks())
        task = lifecycle.approve_task("TASK-001")
        assert task.status == TaskStatus.APPROVED
        entry = result.run_table.get_entry("TASK-001")
        assert entry is not None
        assert entry.status == TaskStatus.APPROVED

    def test_mark_task_running_changes_status(self, tmp_path) -> None:
        lifecycle = self.make_lifecycle(tmp_path)
        lifecycle.prepare_run(self.make_goal(), self.make_tasks())
        task = lifecycle.mark_task_running("TASK-001")
        assert task.status == TaskStatus.RUNNING

    def test_mark_task_result_changes_status(self, tmp_path) -> None:
        lifecycle = self.make_lifecycle(tmp_path)
        lifecycle.prepare_run(self.make_goal(), self.make_tasks())
        passed = lifecycle.mark_task_result("TASK-001", passed=True)
        assert passed.status == TaskStatus.PASSED
        failed = lifecycle.mark_task_result("TASK-002", passed=False, reason="Bug")
        assert failed.status == TaskStatus.FAILED
        entry = lifecycle._run_table.get_entry("TASK-002")
        assert entry is not None
        assert entry.last_error == "Bug"

    def test_no_execution_happens(self, tmp_path) -> None:
        """Lifecycle must not execute anything."""
        lifecycle = self.make_lifecycle(tmp_path)
        goal = self.make_goal()
        tasks = self.make_tasks()
        assert not hasattr(lifecycle, "run_verification")
        assert not hasattr(lifecycle, "launch_claude")
        result = lifecycle.prepare_run(goal, tasks)
        assert isinstance(result, RunLifecycleResult)

    def test_prepare_run_sets_waiting_for_approval(self, tmp_path) -> None:
        lifecycle = self.make_lifecycle(tmp_path)
        result = lifecycle.prepare_run(self.make_goal(), self.make_tasks())
        assert result.run.status == RunStatus.WAITING_FOR_APPROVAL

    def test_prepare_run_with_empty_tasks(self, tmp_path) -> None:
        """prepare_run must handle empty task list gracefully."""
        lifecycle = self.make_lifecycle(tmp_path)
        result = lifecycle.prepare_run(self.make_goal(), [])
        assert result.run_table.entry_count == 0
        assert len(result.paths) >= 1  # at least run metadata
        assert result.run.status == RunStatus.WAITING_FOR_APPROVAL

    def test_nonexistent_task_approval_raises(self, tmp_path) -> None:
        lifecycle = self.make_lifecycle(tmp_path)
        lifecycle.prepare_run(self.make_goal(), self.make_tasks())
        with __import__("pytest").raises(Exception):
            lifecycle.approve_task("NONEXISTENT")

    def test_nonexistent_task_running_raises(self, tmp_path) -> None:
        lifecycle = self.make_lifecycle(tmp_path)
        lifecycle.prepare_run(self.make_goal(), self.make_tasks())
        with __import__("pytest").raises(Exception):
            lifecycle.mark_task_running("NONEXISTENT")
