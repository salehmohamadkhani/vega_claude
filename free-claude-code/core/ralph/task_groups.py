"""Task groups — ordered collections of Ralph tasks.

Groups are stored as JSON files under ``.fcc-ralph/task-groups/``.

A task group defines an ordered execution plan of task IDs. Groups may be
used to represent phases, sprints, or any logical collection of tasks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .models import _new_id, _now_utc
from .workspace import RalphWorkspace


class TaskGroupError(Exception):
    """Base error for task group operations."""


class TaskGroupNotFoundError(TaskGroupError):
    """Raised when a task group is not found."""


@dataclass
class TaskGroup:
    """An ordered collection of task IDs forming an execution plan."""

    id: str = field(default_factory=_new_id)
    title: str = ""
    description: str = ""
    task_ids: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: _now_utc().isoformat())

    def add_task(self, task_id: str) -> None:
        """Append a task ID if not already present."""
        if task_id not in self.task_ids:
            self.task_ids.append(task_id)

    def remove_task(self, task_id: str) -> bool:
        """Remove a task ID. Returns True if found and removed."""
        if task_id in self.task_ids:
            self.task_ids.remove(task_id)
            return True
        return False


class TaskGroupStore:
    """Persist and load task groups as JSON files.

    Uses ``RalphWorkspace`` for filesystem access. Groups are stored as
    ``{group_id}.json`` under ``.fcc-ralph/task-groups/``.
    """

    def __init__(self, workspace: RalphWorkspace | None = None) -> None:
        self._workspace = workspace or RalphWorkspace()
        self._groups_dir = "task-groups"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def save_group(self, group: TaskGroup) -> Path:
        """Save a task group as JSON. Returns the file path."""
        data: dict[str, Any] = {
            "id": group.id,
            "title": group.title,
            "description": group.description,
            "task_ids": group.task_ids,
            "created_at": group.created_at,
        }
        relative = f"{self._groups_dir}/{group.id}.json"
        return self._workspace.write_json(relative, data)

    def load_group(self, group_id: str) -> TaskGroup:
        """Load a task group by ID. Raises TaskGroupNotFoundError if missing."""
        relative = f"{self._groups_dir}/{group_id}.json"
        try:
            data = self._workspace.read_json(relative)
        except FileNotFoundError as exc:
            raise TaskGroupNotFoundError(f"Task group not found: {group_id}") from exc

        return TaskGroup(
            id=data.get("id", group_id),
            title=data.get("title", ""),
            description=data.get("description", ""),
            task_ids=data.get("task_ids", []),
            created_at=data.get("created_at", ""),
        )

    def list_groups(self) -> list[TaskGroup]:
        """Return all task groups, sorted by creation time."""
        paths = self._workspace.list_paths(f"{self._groups_dir}/*.json")
        groups: list[TaskGroup] = []
        for p in paths:
            gid = p.stem
            try:
                groups.append(self.load_group(gid))
            except TaskGroupNotFoundError:
                continue
        return groups

    def add_task(self, group_id: str, task_id: str) -> TaskGroup:
        """Add a task ID to a group and persist. Returns the updated group."""
        group = self.load_group(group_id)
        group.add_task(task_id)
        self.save_group(group)
        return group

    def remove_task(self, group_id: str, task_id: str) -> TaskGroup:
        """Remove a task ID from a group and persist. Returns the updated group."""
        group = self.load_group(group_id)
        group.remove_task(task_id)
        self.save_group(group)
        return group

    def delete_group(self, group_id: str) -> bool:
        """Delete a group file by ID. Returns True if deleted."""
        relative = f"{self._groups_dir}/{group_id}.json"
        return self._workspace.delete_path(relative)
