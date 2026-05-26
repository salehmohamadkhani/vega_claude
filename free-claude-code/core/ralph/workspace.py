"""Safe filesystem layout for Ralph Runtime workspace state.

All Ralph Runtime state lives under ``.fcc-ralph/`` in the target project.
Phase 4 is purely filesystem-based — no database, no network, no provider calls.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path


class RalphWorkspaceError(Exception):
    """Base error for workspace operations."""


class PathTraversalError(RalphWorkspaceError):
    """Raised when a path escapes the workspace root."""


_WORKSPACE_DIR = ".fcc-ralph"

_SUBDIRS = [
    "goals",
    "tasks",
    "task-groups",
    "runs",
    "checkpoints",
    "context",
    "memory",
    "agents",
    "reports",
]


@dataclass(frozen=True)
class RalphWorkspacePaths:
    """Immutable container of workspace directory paths."""

    root: Path = field(compare=True)
    goals_dir: Path = field(compare=True)
    tasks_dir: Path = field(compare=True)
    task_groups_dir: Path = field(compare=True)
    runs_dir: Path = field(compare=True)
    checkpoints_dir: Path = field(compare=True)
    context_dir: Path = field(compare=True)
    memory_dir: Path = field(compare=True)
    agents_dir: Path = field(compare=True)
    reports_dir: Path = field(compare=True)


class RalphWorkspace:
    """Manage the Ralph Runtime workspace inside a project directory.

    All I/O is restricted to ``.fcc-ralph/``. Path traversal is explicitly
    prevented.
    """

    def __init__(self, project_root: str | Path = ".") -> None:
        self._root = Path(project_root).resolve()
        self._workspace_root = self._root / _WORKSPACE_DIR

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def initialize(self) -> RalphWorkspacePaths:
        """Create the workspace directory structure and return paths."""
        for subdir in _SUBDIRS:
            (self._workspace_root / subdir).mkdir(parents=True, exist_ok=True)
        return self.paths()

    def exists(self) -> bool:
        """Return True if the workspace root directory exists."""
        return self._workspace_root.is_dir()

    def paths(self) -> RalphWorkspacePaths:
        """Return a RalphWorkspacePaths with all subdirectory paths.

        Does not create directories — use ``initialize()`` for that.
        """
        return RalphWorkspacePaths(
            root=self._workspace_root,
            goals_dir=self._workspace_root / "goals",
            tasks_dir=self._workspace_root / "tasks",
            task_groups_dir=self._workspace_root / "task-groups",
            runs_dir=self._workspace_root / "runs",
            checkpoints_dir=self._workspace_root / "checkpoints",
            context_dir=self._workspace_root / "context",
            memory_dir=self._workspace_root / "memory",
            agents_dir=self._workspace_root / "agents",
            reports_dir=self._workspace_root / "reports",
        )

    def safe_path(self, relative_path: str | Path) -> Path:
        """Resolve a relative path inside the workspace root.

        Raises ``PathTraversalError`` if the resolved path escapes the workspace.
        """
        resolved = (self._workspace_root / relative_path).resolve()
        if not str(resolved).startswith(str(self._workspace_root)):
            raise PathTraversalError(
                f"Path {relative_path} escapes workspace root {self._workspace_root}"
            )
        return resolved

    def write_json(self, relative_path: str | Path, data: dict) -> Path:
        """Write a JSON file inside the workspace.

        Uses deterministic formatting: sorted keys, indent 2, UTF-8.
        """
        full_path = self.safe_path(relative_path)
        full_path.parent.mkdir(parents=True, exist_ok=True)
        content = json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False)
        full_path.write_text(content, encoding="utf-8")
        return full_path

    def read_json(self, relative_path: str | Path) -> dict:
        """Read a JSON file from inside the workspace."""
        full_path = self.safe_path(relative_path)
        return json.loads(full_path.read_text(encoding="utf-8"))

    def write_text(self, relative_path: str | Path, content: str) -> Path:
        """Write a UTF-8 text file inside the workspace."""
        full_path = self.safe_path(relative_path)
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")
        return full_path

    def read_text(self, relative_path: str | Path) -> str:
        """Read a UTF-8 text file from inside the workspace."""
        full_path = self.safe_path(relative_path)
        return full_path.read_text(encoding="utf-8")

    def delete_path(self, relative_path: str | Path) -> bool:
        """Delete a file inside the workspace. Returns True if deleted."""
        full_path = self.safe_path(relative_path)
        if full_path.is_file():
            os.remove(full_path)
            return True
        return False

    def list_paths(self, relative_glob: str) -> list[Path]:
        """Return matching paths inside the workspace, sorted."""
        pattern = self.safe_path(relative_glob)
        parent = pattern.parent
        glob_pattern = pattern.name
        if not parent.is_dir():
            return []
        return sorted(parent.glob(glob_pattern))
