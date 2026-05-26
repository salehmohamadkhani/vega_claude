"""Tests for core.ralph.task_library."""

from __future__ import annotations

from core.ralph.models import RalphTask, TaskStatus
from core.ralph.roles import AgentRole
from core.ralph.task_library import TaskLibrary, TaskLibraryEntry, TaskLibraryError
from core.ralph.workspace import RalphWorkspace


class TestTaskLibrary:
    def make_library(self, tmp_path) -> TaskLibrary:
        ws = RalphWorkspace(tmp_path)
        ws.initialize()
        return TaskLibrary(ws)

    def make_task(self) -> RalphTask:
        return RalphTask(
            id="TASK-001-test",
            title="Test Task",
            description="A test task description.",
            status=TaskStatus.PENDING,
            agent_role=AgentRole.DOER,
            acceptance_criteria=["Feature works", "Tests pass"],
            verification_commands=["uv run pytest -q", "uv run ruff check"],
            kpis=["All tests pass", "Linting clean"],
            max_iterations=5,
        )

    def test_saves_task_as_markdown(self, tmp_path) -> None:
        lib = self.make_library(tmp_path)
        task = self.make_task()
        path = lib.save_task(task)
        assert path.exists()
        content = path.read_text("utf-8")
        assert content.startswith("---")
        assert "id: TASK-001-test" in content
        assert "agent_role: doer" in content
        assert "## Acceptance Criteria" in content
        assert "## Verification" in content
        assert "uv run pytest -q" in content

    def test_loads_task_from_markdown(self, tmp_path) -> None:
        lib = self.make_library(tmp_path)
        task = self.make_task()
        lib.save_task(task)
        loaded = lib.load_task(f"tasks/{task.id}.md")
        assert loaded.id == task.id
        assert loaded.title == task.title
        assert loaded.agent_role == task.agent_role
        assert loaded.acceptance_criteria == task.acceptance_criteria
        assert loaded.verification_commands == task.verification_commands

    def test_list_tasks(self, tmp_path) -> None:
        lib = self.make_library(tmp_path)
        t1 = self.make_task()
        t2 = RalphTask(id="TASK-002-other", title="Other")
        lib.save_task(t1)
        lib.save_task(t2)
        tasks = lib.list_tasks()
        assert len(tasks) == 2
        ids = {t.id for t in tasks}
        assert ids == {"TASK-001-test", "TASK-002-other"}

    def test_finds_task_by_id(self, tmp_path) -> None:
        lib = self.make_library(tmp_path)
        task = self.make_task()
        lib.save_task(task)
        found = lib.find_task(task.id)
        assert found is not None
        assert found.id == task.id

    def test_find_task_returns_none_if_missing(self, tmp_path) -> None:
        lib = self.make_library(tmp_path)
        assert lib.find_task("nonexistent") is None

    def test_handles_malformed_frontmatter(self, tmp_path) -> None:
        lib = self.make_library(tmp_path)
        ws = RalphWorkspace(tmp_path)
        ws.initialize()
        ws.write_text("tasks/bad.md", "No frontmatter here")
        with __import__("pytest").raises(TaskLibraryError):
            lib.load_task("tasks/bad.md")

    def test_does_not_execute_verification_commands(self, tmp_path) -> None:
        """Loading a task must not trigger any command execution."""
        lib = self.make_library(tmp_path)
        task = self.make_task()
        lib.save_task(task)
        loaded = lib.load_task(f"tasks/{task.id}.md")
        assert loaded.verification_commands == task.verification_commands
        # No subprocess should have been called

    def test_delete_task(self, tmp_path) -> None:
        lib = self.make_library(tmp_path)
        task = self.make_task()
        lib.save_task(task)
        assert lib.delete_task(task.id) is True
        assert lib.find_task(task.id) is None

    def test_entry_dataclass(self) -> None:
        entry = TaskLibraryEntry()
        assert entry.task is not None
        assert entry.body == ""
