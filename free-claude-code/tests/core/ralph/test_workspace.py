"""Tests for core.ralph.workspace."""
from __future__ import annotations

from core.ralph.workspace import (
    PathTraversalError,
    RalphWorkspace,
)


class TestRalphWorkspace:
    def test_initializes_expected_directories(self, tmp_path) -> None:
        ws = RalphWorkspace(tmp_path)
        paths = ws.initialize()
        assert paths.root.is_dir()
        assert paths.goals_dir.is_dir()
        assert paths.tasks_dir.is_dir()
        assert paths.task_groups_dir.is_dir()
        assert paths.runs_dir.is_dir()
        assert paths.checkpoints_dir.is_dir()
        assert paths.context_dir.is_dir()
        assert paths.memory_dir.is_dir()
        assert paths.agents_dir.is_dir()
        assert paths.reports_dir.is_dir()

    def test_exists_returns_true_after_init(self, tmp_path) -> None:
        ws = RalphWorkspace(tmp_path)
        assert ws.exists() is False
        ws.initialize()
        assert ws.exists() is True

    def test_paths_returns_correct_structure(self, tmp_path) -> None:
        ws = RalphWorkspace(tmp_path)
        ws.initialize()
        paths = ws.paths()
        assert str(paths.root).endswith(".fcc-ralph")
        assert str(paths.tasks_dir).endswith("tasks")

    def test_prevents_path_traversal(self, tmp_path) -> None:
        ws = RalphWorkspace(tmp_path)
        ws.initialize()
        with __import__("pytest").raises(PathTraversalError):
            ws.safe_path("../etc/passwd")

    def test_write_and_read_json(self, tmp_path) -> None:
        ws = RalphWorkspace(tmp_path)
        ws.initialize()
        data = {"key": "value", "nested": {"a": 1}}
        path = ws.write_json("runs/test.json", data)
        assert path.exists()
        loaded = ws.read_json("runs/test.json")
        assert loaded == data

    def test_deterministic_json_formatting(self, tmp_path) -> None:
        ws = RalphWorkspace(tmp_path)
        ws.initialize()
        data = {"b": 2, "a": 1}
        ws.write_json("test.json", data)
        content = (tmp_path / ".fcc-ralph" / "test.json").read_text("utf-8")
        # Keys are sorted: a then b
        assert content.index("a") < content.index("b")
        assert '"' in content

    def test_write_and_read_text(self, tmp_path) -> None:
        ws = RalphWorkspace(tmp_path)
        ws.initialize()
        path = ws.write_text("reports/summary.txt", "hello world")
        assert path.exists()
        assert ws.read_text("reports/summary.txt") == "hello world"

    def test_delete_path(self, tmp_path) -> None:
        ws = RalphWorkspace(tmp_path)
        ws.initialize()
        ws.write_text("test.txt", "content")
        assert ws.delete_path("test.txt") is True
        assert ws.delete_path("nonexistent.txt") is False

    def test_list_paths(self, tmp_path) -> None:
        ws = RalphWorkspace(tmp_path)
        ws.initialize()
        ws.write_text("tasks/a.md", "# A")
        ws.write_text("tasks/b.md", "# B")
        paths = ws.list_paths("tasks/*.md")
        assert len(paths) == 2
