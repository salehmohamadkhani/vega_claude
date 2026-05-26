"""Tests for core.ralph.memory."""
from __future__ import annotations

from core.ralph.memory import (
    InvalidMemoryLevelError,
    MemoryRecord,
    MemoryRecordNotFoundError,
    MemoryStore,
)
from core.ralph.workspace import RalphWorkspace


class TestMemoryStore:
    def make_store(self, tmp_path) -> MemoryStore:
        ws = RalphWorkspace(tmp_path)
        ws.initialize()
        return MemoryStore(ws)

    def make_record(self, **kw) -> MemoryRecord:
        kwargs = {
            "id": kw.pop("id", "mem1"),
            "level": kw.pop("level", "working"),
            "content": kw.pop("content", "test memory"),
            "tags": kw.pop("tags", ["test"]),
            "source": kw.pop("source", "test"),
            "importance": kw.pop("importance", 50),
        }
        kwargs.update(kw)
        return MemoryRecord(**kwargs)

    def test_add_and_get(self, tmp_path) -> None:
        store = self.make_store(tmp_path)
        record = self.make_record()
        store.add(record)
        loaded = store.get("mem1")
        assert loaded is not None
        assert loaded.id == "mem1"
        assert loaded.content == "test memory"

    def test_get_returns_none_if_missing(self, tmp_path) -> None:
        store = self.make_store(tmp_path)
        assert store.get("nonexistent") is None

    def test_list_all(self, tmp_path) -> None:
        store = self.make_store(tmp_path)
        store.add(self.make_record(id="a", content="alpha"))
        store.add(self.make_record(id="b", content="beta"))
        records = store.list_records()
        assert len(records) == 2

    def test_list_by_level(self, tmp_path) -> None:
        store = self.make_store(tmp_path)
        store.add(self.make_record(id="w1", level="working"))
        store.add(self.make_record(id="e1", level="episodic"))
        working = store.list_records(level="working")
        assert len(working) == 1
        assert working[0].id == "w1"

    def test_list_by_tags(self, tmp_path) -> None:
        store = self.make_store(tmp_path)
        store.add(self.make_record(id="a", tags=["important"]))
        store.add(self.make_record(id="b", tags=["other"]))
        tagged = store.list_records(tags=["important"])
        assert len(tagged) == 1
        assert tagged[0].id == "a"

    def test_search_by_keyword(self, tmp_path) -> None:
        store = self.make_store(tmp_path)
        store.add(self.make_record(id="a", content="fix bug in parser"))
        store.add(self.make_record(id="b", content="add new feature"))
        results = store.search("bug parser")
        assert len(results) >= 1
        assert results[0].id == "a"

    def test_search_ordering(self, tmp_path) -> None:
        store = self.make_store(tmp_path)
        store.add(self.make_record(id="a", content="fix bug", importance=30))
        store.add(self.make_record(id="b", content="fix bug", importance=80))
        results = store.search("fix bug")
        # Higher importance first
        assert results[0].id == "b"

    def test_update_record(self, tmp_path) -> None:
        store = self.make_store(tmp_path)
        store.add(self.make_record(id="u1", content="old", importance=10))
        updated = store.update("u1", content="new", importance=50)
        assert updated.content == "new"
        assert updated.importance == 50
        # Verify persistence
        loaded = store.get("u1")
        assert loaded is not None
        assert loaded.content == "new"

    def test_update_level_validation(self, tmp_path) -> None:
        store = self.make_store(tmp_path)
        store.add(self.make_record(id="lv"))
        with __import__("pytest").raises(InvalidMemoryLevelError):
            store.update("lv", level="invalid_level")

    def test_delete_record(self, tmp_path) -> None:
        store = self.make_store(tmp_path)
        store.add(self.make_record(id="del"))
        assert store.delete("del") is True
        assert store.get("del") is None
        assert store.delete("del") is False

    def test_validates_memory_level(self) -> None:
        with __import__("pytest").raises(InvalidMemoryLevelError):
            MemoryRecord(level="invalid_level")

    def test_validates_importance_range(self) -> None:
        with __import__("pytest").raises(ValueError):
            MemoryRecord(importance=150)

    def test_search_returns_empty_for_empty_query(self, tmp_path) -> None:
        store = self.make_store(tmp_path)
        assert store.search("") == []

    def test_update_nonexistent_raises(self, tmp_path) -> None:
        store = self.make_store(tmp_path)
        with __import__("pytest").raises(MemoryRecordNotFoundError):
            store.update("nonexistent", content="x")
