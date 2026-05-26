"""Tests for core.ralph.task_groups."""

from __future__ import annotations

from core.ralph.task_groups import TaskGroup, TaskGroupNotFoundError, TaskGroupStore
from core.ralph.workspace import RalphWorkspace


class TestTaskGroupStore:
    def make_store(self, tmp_path) -> TaskGroupStore:
        ws = RalphWorkspace(tmp_path)
        ws.initialize()
        return TaskGroupStore(ws)

    def test_saves_and_loads_group(self, tmp_path) -> None:
        store = self.make_store(tmp_path)
        group = TaskGroup(id="g1", title="Phase 1", task_ids=["t1", "t2"])
        store.save_group(group)
        loaded = store.load_group("g1")
        assert loaded.id == "g1"
        assert loaded.title == "Phase 1"
        assert loaded.task_ids == ["t1", "t2"]

    def test_preserves_task_order(self, tmp_path) -> None:
        store = self.make_store(tmp_path)
        group = TaskGroup(id="order", task_ids=["a", "b", "c"])
        store.save_group(group)
        loaded = store.load_group("order")
        assert loaded.task_ids == ["a", "b", "c"]

    def test_prevents_duplicate_task_ids(self, tmp_path) -> None:
        group = TaskGroup(id="dedup", task_ids=["a"])
        group.add_task("a")
        assert group.task_ids == ["a"], "Duplicate task ID must not be added"

    def test_add_removes_task(self, tmp_path) -> None:
        store = self.make_store(tmp_path)
        group = TaskGroup(id="mod", task_ids=["x", "y"])
        store.save_group(group)
        store.add_task("mod", "z")
        loaded = store.load_group("mod")
        assert "z" in loaded.task_ids

        store.remove_task("mod", "x")
        loaded2 = store.load_group("mod")
        assert "x" not in loaded2.task_ids
        assert loaded2.task_ids == ["y", "z"]

    def test_remove_nonexistent_task_returns_false(self, tmp_path) -> None:
        group = TaskGroup(id="g", task_ids=["a"])
        assert group.remove_task("nonexistent") is False

    def test_list_groups(self, tmp_path) -> None:
        store = self.make_store(tmp_path)
        store.save_group(TaskGroup(id="g1", title="First"))
        store.save_group(TaskGroup(id="g2", title="Second"))
        groups = store.list_groups()
        assert len(groups) == 2
        assert {g.id for g in groups} == {"g1", "g2"}

    def test_load_nonexistent_raises(self, tmp_path) -> None:
        store = self.make_store(tmp_path)
        with __import__("pytest").raises(TaskGroupNotFoundError):
            store.load_group("nonexistent")

    def test_delete_group(self, tmp_path) -> None:
        store = self.make_store(tmp_path)
        store.save_group(TaskGroup(id="del"))
        assert store.delete_group("del") is True
        assert store.delete_group("del") is False
