"""Lightweight local memory store for Ralph Runtime.

Four memory levels inspired by Ralph concepts, implemented as FCC-native
deterministic JSON storage:

- **working**: current session context, short-lived
- **episodic**: task/run events and experiences
- **semantic**: learned facts and patterns
- **procedural**: known workflows and processes

No vector database. No external dependencies. Search is keyword-based.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from .models import _new_id
from .workspace import RalphWorkspace


class MemoryError(Exception):
    """Base error for memory operations."""


class MemoryRecordNotFoundError(MemoryError):
    """Raised when a memory record is not found."""


class InvalidMemoryLevelError(MemoryError):
    """Raised when an invalid memory level is provided."""


_VALID_MEMORY_LEVELS = frozenset({"working", "episodic", "semantic", "procedural"})


@dataclass
class MemoryRecord:
    """A single memory record in the Ralph Runtime memory store."""

    id: str = field(default_factory=_new_id)
    level: str = "working"
    content: str = ""
    tags: list[str] = field(default_factory=list)
    source: str = ""
    importance: int = 0
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.level not in _VALID_MEMORY_LEVELS:
            raise InvalidMemoryLevelError(
                f"Invalid memory level: {self.level!r}. "
                f"Must be one of {sorted(_VALID_MEMORY_LEVELS)}"
            )
        if not 0 <= self.importance <= 100:
            raise ValueError(f"importance must be 0-100, got {self.importance}")


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


class MemoryStore:
    """Persistent memory store for Ralph Runtime.

    All records are stored as individual JSON files under
    ``.fcc-ralph/memory/``. Search is keyword-based (token overlap).
    """

    def __init__(self, workspace: RalphWorkspace | None = None) -> None:
        self._workspace = workspace or RalphWorkspace()
        self._memory_dir = "memory"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add(self, record: MemoryRecord) -> MemoryRecord:
        """Store a memory record. Returns the record with any generated fields."""
        relative = f"{self._memory_dir}/{record.id}.json"
        data = self._record_to_dict(record)
        self._workspace.write_json(relative, data)
        return record

    def get(self, record_id: str) -> MemoryRecord | None:
        """Retrieve a memory record by ID. Returns None if not found."""
        relative = f"{self._memory_dir}/{record_id}.json"
        try:
            data = self._workspace.read_json(relative)
            return self._dict_to_record(data)
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return None

    def list_records(
        self,
        level: str | None = None,
        tags: list[str] | None = None,
    ) -> list[MemoryRecord]:
        """Return all memory records, optionally filtered by level and tags.

        Results are sorted: most recently updated first.
        """
        paths = self._workspace.list_paths(f"{self._memory_dir}/*.json")
        result: list[MemoryRecord] = []
        for p in paths:
            try:
                data = self._workspace.read_json(f"{self._memory_dir}/{p.name}")
                record = self._dict_to_record(data)
            except (FileNotFoundError, json.JSONDecodeError, OSError):
                continue

            if level is not None and record.level != level:
                continue
            if tags is not None:
                record_tags_set = set(record.tags)
                if not record_tags_set.intersection(tags):
                    continue
            result.append(record)

        result.sort(key=lambda r: r.updated_at or "", reverse=True)
        return result

    def search(
        self,
        query: str,
        level: str | None = None,
        limit: int = 10,
    ) -> list[MemoryRecord]:
        """Search memory records by keyword token overlap.

        Results are ordered by:
        1. Best match score (query token overlap with content + tags)
        2. Higher importance
        3. Newer updated_at
        """
        query_tokens = set(query.lower().split())
        if not query_tokens:
            return []

        candidates = self.list_records(level=level)
        scored: list[tuple[float, MemoryRecord]] = []

        for record in candidates:
            content_tokens = set(record.content.lower().split())
            tag_tokens = {t.lower() for t in record.tags}
            all_tokens = content_tokens | tag_tokens

            if not all_tokens:
                continue

            overlap = len(query_tokens & all_tokens)
            score = overlap / len(query_tokens) if query_tokens else 0.0
            if score > 0:
                scored.append((score, record))

        # Sort: higher score, higher importance, newer updated_at
        scored.sort(
            key=lambda x: (x[0], x[1].importance, x[1].updated_at or ""),
            reverse=True,
        )
        return [r for _, r in scored[:limit]]

    def update(self, record_id: str, **fields: Any) -> MemoryRecord:
        """Update fields on a memory record. Returns the updated record."""
        record = self.get(record_id)
        if record is None:
            raise MemoryRecordNotFoundError(f"Memory record not found: {record_id}")

        for key, value in fields.items():
            if hasattr(record, key):
                if key == "level" and value not in _VALID_MEMORY_LEVELS:
                    raise InvalidMemoryLevelError(
                        f"Invalid memory level: {value!r}. "
                        f"Must be one of {sorted(_VALID_MEMORY_LEVELS)}"
                    )
                if key == "importance" and not (0 <= value <= 100):
                    raise ValueError(f"importance must be 0-100, got {value}")
                setattr(record, key, value)

        record.updated_at = _now_iso()
        relative = f"{self._memory_dir}/{record_id}.json"
        data = self._record_to_dict(record)
        self._workspace.write_json(relative, data)
        return record

    def delete(self, record_id: str) -> bool:
        """Delete a memory record by ID. Returns True if deleted."""
        relative = f"{self._memory_dir}/{record_id}.json"
        return self._workspace.delete_path(relative)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _record_to_dict(self, record: MemoryRecord) -> dict[str, Any]:
        return {
            "id": record.id,
            "level": record.level,
            "content": record.content,
            "tags": list(record.tags),
            "source": record.source,
            "importance": record.importance,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
            "metadata": dict(record.metadata),
        }

    def _dict_to_record(self, data: dict[str, Any]) -> MemoryRecord:
        return MemoryRecord(
            id=data.get("id", ""),
            level=data.get("level", "working"),
            content=data.get("content", ""),
            tags=data.get("tags", []),
            source=data.get("source", ""),
            importance=data.get("importance", 0),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            metadata=data.get("metadata", {}),
        )
