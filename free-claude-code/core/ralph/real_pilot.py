"""Controlled real-execution pilot for Ralph Runtime.

Provides a safe helper to create a throwaway pilot workspace for manual
and automated validation of real execution through the Ralph loop.

The pilot workspace is created outside the Vega repo by default, so the
real execution pilot never modifies Vega source files.

Safe defaults:
- Dry-run by default
- Pilot workspace in ``%TEMP%`` or user-provided path
- Small pilot file (README.md) with an approved task
- Allowed files enforced
- Structured pilot result
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .execution_guard import (
    RealExecutionGuardResult,
    check_real_execution_safety,
)
from .loop_policy import LoopPolicy
from .loop_runner import RalphLoopResult, RalphLoopRunner
from .models import (
    RalphRun,
    RalphTask,
    RunStatus,
    TaskStatus,
)
from .task_library import TaskLibrary
from .workspace import RalphWorkspace


@dataclass
class RealPilotConfig:
    """Configuration for creating and running a real-execution pilot.

    Safe defaults: dry-run only, isolated workspace outside repo.
    """

    pilot_workspace_path: str = ""
    dry_run: bool = True
    allow_real_execution: bool = False
    max_iterations_per_task: int = 1
    allowed_files: list[str] = field(default_factory=lambda: ["README.md"])
    forbidden_files: list[str] = field(
        default_factory=lambda: [
            "*.py",
            "*.json",
            "*.yaml",
            "*.yml",
            "*.toml",
            "*.cfg",
            "*.ini",
            ".git",
        ]
    )
    allow_dirty_git: bool = False
    allow_repo_root_execution: bool = False


@dataclass
class RealPilotResult:
    """Structured result of a real-execution pilot run."""

    pilot_workspace_path: str = ""
    run_id: str = ""
    task_id: str = ""
    guard_result: RealExecutionGuardResult | None = None
    loop_result: RalphLoopResult | None = None
    passed: bool = False
    changed_files: list[str] = field(default_factory=list)
    failure_reasons: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class RealPilot:
    """Create and run a controlled real-execution pilot.

    The pilot creates an isolated workspace with a small task and runs
    it through the normal Ralph loop machinery.

    Usage::

        pilot = RealPilot(config=RealPilotConfig(dry_run=False, ...))
        result = pilot.run()
    """

    def __init__(
        self,
        config: RealPilotConfig | None = None,
    ) -> None:
        self._config = config or RealPilotConfig()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self) -> RealPilotResult:
        """Create the pilot workspace, set up a task, and run through the loop.

        Returns a ``RealPilotResult`` with guard and loop outcomes.
        """
        # Step 1: Determine pilot workspace path
        ws_path = self._resolve_pilot_path()

        # Step 2: Create pilot workspace (must exist before guard check)
        ws = self._create_pilot_workspace(ws_path)

        # Step 3: Check guard
        guard_result = self._run_guard(ws_path)
        if not guard_result.allowed and not self._config.dry_run:
            return RealPilotResult(
                pilot_workspace_path=ws_path,
                guard_result=guard_result,
                passed=False,
                failure_reasons=guard_result.failure_reasons,
            )

        task_lib = TaskLibrary(workspace=ws)

        # Step 4: Create a small pilot file and task
        pilot_file_path = self._create_pilot_file(ws)
        task = self._create_pilot_task(task_lib, pilot_file_path)

        # Step 5: Build run state
        run = RalphRun(
            id=_new_pilot_id(),
            goal_id=_new_pilot_id(),
            status=RunStatus.RUNNING,
            tasks=[task],
        )

        # Step 6: Run through loop
        policy = LoopPolicy(
            max_iterations_per_task=self._config.max_iterations_per_task,
            dry_run=self._config.dry_run,
            allow_real_execution=self._config.allow_real_execution,
            strict_task_order=True,
            require_approval=True,
        )
        runner = RalphLoopRunner(workspace=ws, task_library=task_lib)
        loop_result = runner.run(run=run, tasks=[task], policy=policy)

        # Persist changes
        task_lib.save_task(task)

        # Step 7: Detect changed files
        changed = self._detect_changed_files(ws)

        return RealPilotResult(
            pilot_workspace_path=ws_path,
            run_id=run.id,
            task_id=task.id,
            guard_result=guard_result,
            loop_result=loop_result,
            passed=loop_result.completed if loop_result else False,
            changed_files=changed,
            failure_reasons=(
                [loop_result.stopped_reason]
                if loop_result and loop_result.stopped_reason
                else []
            ),
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_pilot_path(self) -> str:
        """Resolve the pilot workspace path.

        Uses the configured path or creates one in ``%TEMP%``.
        """
        if self._config.pilot_workspace_path:
            return str(Path(self._config.pilot_workspace_path).resolve())

        base = Path(tempfile.gettempdir()) / "vega-ralph-real-pilot"
        base.mkdir(parents=True, exist_ok=True)
        return str(base.resolve())

    def _run_guard(self, ws_path: str) -> RealExecutionGuardResult:
        """Run the real execution guard.

        In dry-run mode, the guard always allows.
        """
        if self._config.dry_run:
            return RealExecutionGuardResult(
                allowed=True,
                workspace_path=ws_path,
            )
        return check_real_execution_safety(
            ws_path,
            allow_repo_root_execution=self._config.allow_repo_root_execution,
            allow_dirty_git=self._config.allow_dirty_git,
        )

    def _create_pilot_workspace(self, path: str) -> RalphWorkspace:
        """Create a Ralph workspace at the given path."""
        ws = RalphWorkspace(project_root=path)
        if not ws.exists():
            ws.initialize()
        return ws

    def _create_pilot_file(self, ws: RalphWorkspace) -> str:
        """Create a small pilot file (e.g. README.md) in the workspace.

        Returns the relative path of the created file.
        """
        content = (
            "# Ralph Real Execution Pilot\n\n"
            "This file was created by the Ralph real-execution pilot.\n"
        )
        ws.write_text("README.md", content)
        return "README.md"

    def _create_pilot_task(
        self,
        task_lib: TaskLibrary,
        pilot_file_path: str,
    ) -> RalphTask:
        """Create a single approved pilot task."""
        task = RalphTask(
            id=_new_pilot_id(),
            title="Real execution pilot task",
            status=TaskStatus.APPROVED,
            acceptance_criteria=["Pilot file exists and is valid"],
            verification_commands=["dir README.md"],
            allowed_files=self._config.allowed_files,
            forbidden_files=self._config.forbidden_files,
        )
        task_lib.save_task(task)
        return task

    def _detect_changed_files(self, ws: RalphWorkspace) -> list[str]:
        """Detect files changed in the workspace compared to initial state."""
        root = Path(ws.paths().root)
        if not root.exists():
            return []
        changed: list[str] = []
        for entry in root.rglob("*"):
            if entry.is_file():
                rel = str(entry.relative_to(root))
                changed.append(rel)
        return changed


def _new_pilot_id() -> str:
    import uuid

    return f"PILOT-{uuid.uuid4().hex[:8]}"
