"""Persist and load Ralph tasks as Markdown files with YAML frontmatter.

Task files live under ``.fcc-ralph/tasks/``.

Markdown format::

    ---
    id: TASK-001-context-map
    title: Context Map
    status: pending
    agent_role: architect
    ---

    # Context Map

    ## Acceptance Criteria

    - ...

    ## Verification

    ```bash
    uv run pytest tests -q
    ```

        Uses _frontmatter internally — no PyYAML dependency.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ._frontmatter import FrontmatterError
from ._frontmatter import dumps as _yaml_dumps
from ._frontmatter import safe_load as _yaml_safe_load
from .models import RalphTask, TaskStatus, task_status_from_str
from .roles import agent_role_from_str
from .workspace import RalphWorkspace


class TaskLibraryError(Exception):
    """Base error for task library operations."""


class TaskNotFoundError(TaskLibraryError):
    """Raised when a task is not found."""


class TaskParseError(TaskLibraryError):
    """Raised when a task file is malformed."""


_FRONTMATTER_DELIM = "---"


@dataclass
class TaskLibraryEntry:
    """A loaded task entry with metadata."""

    task: RalphTask = field(default_factory=RalphTask)
    path: Path | None = None
    frontmatter: dict[str, Any] = field(default_factory=dict)
    body: str = ""


class TaskLibrary:
    """Persist and load Ralph tasks as Markdown files.

    Uses ``RalphWorkspace`` for filesystem access. Task files are stored
    as ``{task_id}.md`` under ``.fcc-ralph/tasks/``.
    """

    def __init__(self, workspace: RalphWorkspace | None = None) -> None:
        self._workspace = workspace or RalphWorkspace()
        self._tasks_dir = "tasks"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def save_task(self, task: RalphTask) -> Path:
        """Save a task as a Markdown file. Returns the file path."""
        frontmatter = {
            "id": task.id,
            "title": task.title,
            "status": task.status.value,
            "agent_role": task.agent_role.value,
            "max_iterations": task.max_iterations,
            "allowed_files": task.allowed_files,
            "forbidden_files": task.forbidden_files,
            "smoke_targets": task.smoke_targets,
        }
        body_parts: list[str] = [f"# {task.title}", ""]
        if task.description:
            body_parts.extend([task.description, ""])

        if task.acceptance_criteria:
            body_parts.append("## Acceptance Criteria")
            body_parts.append("")
            body_parts.extend(f"- {ac}" for ac in task.acceptance_criteria)
            body_parts.append("")

        if task.verification_commands:
            body_parts.append("## Verification")
            body_parts.append("")
            body_parts.append("```bash")
            body_parts.extend(task.verification_commands)
            body_parts.append("```")
            body_parts.append("")

        if task.kpis:
            body_parts.append("## KPIs")
            body_parts.append("")
            body_parts.extend(f"- {kpi}" for kpi in task.kpis)
            body_parts.append("")

        body = "\n".join(body_parts).rstrip() + "\n"

        frontmatter_str = _yaml_dumps(frontmatter)

        content = f"{_FRONTMATTER_DELIM}\n{frontmatter_str}{_FRONTMATTER_DELIM}\n{body}"
        relative = f"{self._tasks_dir}/{task.id}.md"
        return self._workspace.write_text(relative, content)

    def load_task(self, path: str | Path) -> RalphTask:
        """Load a task from a Markdown file path.

        The path can be absolute or workspace-relative.
        """
        rel = self._resolve_load_path(path)
        content = self._workspace.read_text(rel)
        return self._parse_markdown(content)

    def list_tasks(self) -> list[RalphTask]:
        """Return all tasks in the task library."""
        paths = self._workspace.list_paths(f"{self._tasks_dir}/*.md")
        tasks: list[RalphTask] = []
        for p in paths:
            try:
                rel = f"{self._tasks_dir}/{p.name}"
                content = self._workspace.read_text(rel)
                tasks.append(self._parse_markdown(content))
            except TaskParseError:
                continue
        return tasks

    def find_task(self, task_id: str) -> RalphTask | None:
        """Find a task by its ID. Returns None if not found."""
        relative = f"{self._tasks_dir}/{task_id}.md"
        try:
            content = self._workspace.read_text(relative)
            return self._parse_markdown(content)
        except TaskParseError, FileNotFoundError, OSError:
            return None

    def delete_task(self, task_id: str) -> bool:
        """Delete a task file by ID. Returns True if deleted."""
        relative = f"{self._tasks_dir}/{task_id}.md"
        return self._workspace.delete_path(relative)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_load_path(self, path: str | Path) -> str:
        """Convert a load path to a workspace-relative string."""
        p = Path(path)
        if p.is_absolute():
            # Try to make it relative to workspace
            try:
                return str(p.relative_to(self._workspace.paths().root.parent))
            except ValueError:
                return str(p.relative_to(self._workspace.paths().root))
        return str(p)

    def _parse_markdown(self, content: str) -> RalphTask:
        """Parse a Markdown string with YAML frontmatter into a RalphTask."""
        stripped = content.strip()
        if not stripped.startswith(_FRONTMATTER_DELIM):
            raise TaskParseError("Missing frontmatter delimiter '---'")

        # Find closing delimiter
        end_idx = stripped.find(_FRONTMATTER_DELIM, 3)
        if end_idx == -1:
            raise TaskParseError("Missing closing frontmatter delimiter '---'")

        yaml_text = stripped[3:end_idx].strip()
        body_text = stripped[end_idx + 3 :].strip()

        try:
            frontmatter: dict[str, Any] = _yaml_safe_load(yaml_text) or {}
        except FrontmatterError as exc:
            raise TaskParseError(f"Invalid YAML frontmatter: {exc}") from exc

        if not isinstance(frontmatter, dict):
            raise TaskParseError("Frontmatter must be a mapping")

        task_id = frontmatter.get("id", "")
        if not task_id:
            raise TaskParseError("Frontmatter missing required 'id' field")

        # Parse status
        raw_status = frontmatter.get("status", "pending")
        try:
            status = task_status_from_str(str(raw_status))
        except ValueError:
            status = TaskStatus.PENDING

        # Parse agent role
        raw_role = frontmatter.get("agent_role", "doer")
        agent_role = agent_role_from_str(str(raw_role))

        # Parse acceptance criteria from body
        criteria = self._extract_list_section(body_text, "Acceptance Criteria")

        # Parse verification commands from body
        commands = self._extract_code_blocks(body_text)

        # Parse KPIs from body
        kpis = self._extract_list_section(body_text, "KPIs")

        task = RalphTask(
            id=task_id,
            title=frontmatter.get("title", ""),
            description=body_text.split("\n\n")[0] if body_text else "",
            status=status,
            agent_role=agent_role,
            max_iterations=int(frontmatter.get("max_iterations", 10)),
            allowed_files=frontmatter.get("allowed_files", []),
            forbidden_files=frontmatter.get("forbidden_files", []),
            smoke_targets=frontmatter.get("smoke_targets", []),
            acceptance_criteria=criteria,
            verification_commands=commands,
            kpis=kpis,
        )
        return task

    def _extract_list_section(self, body: str, heading: str) -> list[str]:
        """Extract markdown list items under a given heading."""
        items: list[str] = []
        in_section = False
        for line in body.split("\n"):
            stripped = line.strip()
            if stripped.startswith(f"## {heading}") or stripped.startswith(
                f"# {heading}"
            ):
                in_section = True
                continue
            if in_section:
                if stripped.startswith("##"):
                    break
                if stripped.startswith("- ") or stripped.startswith("* "):
                    items.append(stripped[2:].strip())
                elif stripped.startswith("1. "):
                    items.append(stripped[3:].strip())
        return items

    def _extract_code_blocks(self, body: str) -> list[str]:
        """Extract bash code block contents from the body."""
        commands: list[str] = []
        lines = body.split("\n")
        in_code = False
        for line in lines:
            if line.strip().startswith("```bash"):
                in_code = True
                continue
            if line.strip().startswith("```"):
                in_code = False
                continue
            if in_code:
                cmd = line.strip()
                if cmd:
                    commands.append(cmd)
        return commands
