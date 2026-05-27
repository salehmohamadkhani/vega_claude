"""Run lifecycle skeleton — coordinates planned runs without executing code.

Creates and prepares a run by persisting tasks, creating run table entries,
initial checkpoints, and context snapshots. Does NOT execute tasks, launch
Claude Code, or run verification.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .checkpoint import Checkpoint, CheckpointStore
from .context_builder import ContextBuilder, RalphContextSnapshot
from .models import (
    ProjectGoal,
    RalphRun,
    RalphTask,
    RunStatus,
    TaskStatus,
    _new_id,
    _now_utc,
)
from .run_table import RunTable, RunTableEntry
from .task_library import TaskLibrary
from .workspace import RalphWorkspace


class RunLifecycleError(Exception):
    """Base error for run lifecycle operations."""


@dataclass
class RunLifecycleResult:
    """Structured output of preparing a run."""

    run: RalphRun = field(default_factory=RalphRun)
    tasks: list[RalphTask] = field(default_factory=list)
    run_table: RunTable = field(default_factory=RunTable)
    checkpoint: Checkpoint = field(default_factory=Checkpoint)
    context_snapshot: RalphContextSnapshot = field(default_factory=RalphContextSnapshot)
    paths: list[Path] = field(default_factory=list)


class RunLifecycle:
    """Coordinate a planned run's lifecycle without executing code.

    Responsibilities:
    - Create and persist run metadata
    - Persist tasks to the task library
    - Populate run table entries
    - Create initial checkpoints
    - Build context snapshots
    - Track task status transitions

    Does NOT:
    - Execute tasks
    - Launch Claude Code
    - Run verification commands
    """

    def __init__(
        self,
        workspace: RalphWorkspace | None = None,
        task_library: TaskLibrary | None = None,
        checkpoint_store: CheckpointStore | None = None,
        context_builder: ContextBuilder | None = None,
    ) -> None:
        ws = workspace or RalphWorkspace()
        self._workspace = ws
        self._task_library = task_library or TaskLibrary(ws)
        self._checkpoint_store = checkpoint_store or CheckpointStore(ws)
        self._context_builder = context_builder or ContextBuilder(
            workspace=ws, repo_root="."
        )
        self._run_table = RunTable()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_run_tasks(
        self, tasks: list[RalphTask], run_id: str = ""
    ) -> None:
        """Populate the in-memory run table from a list of tasks.

        ``RunTable`` is in-memory and does not survive process restarts.
        This method is needed when recreating ``RunLifecycle`` from
        persisted state (e.g., after a CLI process restart) so that
        ``mark_task_running`` / ``mark_task_result`` do not raise
        ``RunLifecycleError`` for missing entries.
        """
        for task in tasks:
            entry = self._run_table.get_entry(task.id)
            if entry is None:
                entry = RunTableEntry(
                    run_id=run_id,
                    task_id=task.id,
                    task_title=task.title or "",
                    agent_role=task.agent_role,
                    status=task.status,
                )
                self._run_table.add_entry(entry)
            else:
                entry.status = task.status

    def create_run(
        self,
        goal: ProjectGoal,
        tasks: list[RalphTask] | None = None,
    ) -> RalphRun:
        """Create a new RalphRun from a goal and optional tasks.

        Does NOT persist anything — use ``prepare_run()`` for that.
        """
        run = RalphRun(
            id=_new_id(),
            goal_id=goal.id,
            status=RunStatus.CREATED,
            tasks=tasks or [],
            created_at=_now_utc(),
            updated_at=_now_utc(),
        )
        return run

    def prepare_run(
        self,
        goal: ProjectGoal,
        tasks: list[RalphTask],
    ) -> RunLifecycleResult:
        """Prepare a run for execution by persisting all state.

        This is the main entry point for starting a planned run:
        1. Creates the RalphRun object
        2. Persists all tasks to the task library
        3. Populates the run table with task entries
        4. Creates an initial checkpoint
        5. Builds a context snapshot
        6. Persists run metadata to workspace
        """
        run = self.create_run(goal, tasks)
        run.status = RunStatus.PLANNING

        paths: list[Path] = []

        # Persist tasks
        for task in tasks:
            p = self._task_library.save_task(task)
            paths.append(p)

        # Populate run table
        for task in tasks:
            entry = RunTableEntry(
                run_id=run.id,
                task_id=task.id,
                task_title=task.title,
                agent_role=task.agent_role,
                status=TaskStatus.PENDING,
            )
            self._run_table.add_entry(entry)

        # Create initial checkpoint
        checkpoint = Checkpoint.from_run_state(
            run_id=run.id,
            task_id=tasks[0].id if tasks else "",
            iteration_number=0,
            run_status=RunStatus.PLANNING,
            task_status=TaskStatus.PENDING,
            next_action="start_task",
        )
        cp_path = self._checkpoint_store.save_checkpoint(checkpoint)
        paths.append(cp_path)

        # Build context snapshot
        first_task = tasks[0] if tasks else None
        context = self._context_builder.build_snapshot(
            goal_id=goal.id,
            run_id=run.id,
            task_id=first_task.id if first_task else "",
            task=first_task,
        )
        ctx_path = self._context_builder.save_snapshot(context)
        paths.append(ctx_path)

        # Persist run metadata
        run.status = RunStatus.WAITING_FOR_APPROVAL
        run_path = self._save_run_metadata(run, tasks)
        paths.append(run_path)

        return RunLifecycleResult(
            run=run,
            tasks=tasks,
            run_table=self._run_table,
            checkpoint=checkpoint,
            context_snapshot=context,
            paths=paths,
        )

    def approve_task(self, task_id: str) -> RalphTask:
        """Mark a task as APPROVED in the run table.

        Raises ``RunLifecycleError`` if the task is not in the run table.
        """
        if self._run_table.get_entry(task_id) is None:
            raise RunLifecycleError(f"Task {task_id!r} not found in run table")
        self._run_table.update_status(task_id, TaskStatus.APPROVED)
        return self._make_task_stub(task_id, TaskStatus.APPROVED)

    def mark_task_running(self, task_id: str) -> RalphTask:
        """Mark a task as RUNNING.

        Raises ``RunLifecycleError`` if the task is not in the run table.
        """
        if self._run_table.get_entry(task_id) is None:
            raise RunLifecycleError(f"Task {task_id!r} not found in run table")
        self._run_table.update_status(task_id, TaskStatus.RUNNING)
        return self._make_task_stub(task_id, TaskStatus.RUNNING)

    def mark_task_result(
        self, task_id: str, passed: bool, reason: str = ""
    ) -> RalphTask:
        """Mark a task as PASSED or FAILED.

        Raises ``RunLifecycleError`` if the task is not in the run table.
        """
        if self._run_table.get_entry(task_id) is None:
            raise RunLifecycleError(f"Task {task_id!r} not found in run table")
        status = TaskStatus.PASSED if passed else TaskStatus.FAILED
        self._run_table.update_status(task_id, status)
        if not passed and reason:
            self._run_table.record_error(task_id, reason)
        return self._make_task_stub(task_id, status)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _save_run_metadata(self, run: RalphRun, tasks: list[RalphTask]) -> Path:
        """Persist run metadata to the workspace."""
        data: dict[str, Any] = {
            "id": run.id,
            "goal_id": run.goal_id,
            "status": run.status.value,
            "task_ids": [t.id for t in tasks],
            "created_at": run.created_at.isoformat() if run.created_at else "",
            "updated_at": run.updated_at.isoformat() if run.updated_at else "",
        }
        return self._workspace.write_json(f"runs/{run.id}.json", data)

    def _make_task_stub(self, task_id: str, status: TaskStatus) -> RalphTask:
        """Return a task stub with the given ID and status."""
        entry = self._run_table.get_entry(task_id)
        if entry is None:
            return RalphTask(id=task_id, status=status)
        return RalphTask(
            id=entry.task_id,
            title=entry.task_title,
            status=status,
            agent_role=entry.agent_role,
        )
