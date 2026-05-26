"""Multi-task run executor for Ralph Runtime.

Coordinates task selection, iteration execution, loop guard evaluation,
and persistence across an entire run. Each task goes through one or
more iterations until passed, stopped, or escalated.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .arbiter import ArbiterAction, ArbiterEngine
from .checkpoint import CheckpointStore
from .context_builder import ContextBuilder
from .iteration_runner import IterationRunner, IterationRunResult
from .loop_guard import LoopGuard
from .models import (
    ProjectGoal,
    RalphRun,
    RalphTask,
    RunStatus,
    TaskStatus,
    _now_utc,
)
from .run_lifecycle import RunLifecycle
from .task_library import TaskLibrary
from .workspace import RalphWorkspace


@dataclass
class RunExecutorConfig:
    """Configuration for RunExecutor behavior.

    Safe defaults: no auto-approval, stop on debug/escalate.
    """

    auto_approve_pending_tasks: bool = False
    max_iterations_per_task: int = 1
    stop_on_debug: bool = True
    stop_on_escalate: bool = True


@dataclass
class RunExecutorResult:
    """Structured outcome of executing tasks in a run."""

    run: RalphRun = field(default_factory=RalphRun)
    task_results: list[IterationRunResult] = field(default_factory=list)
    completed: bool = False
    failed: bool = False
    stopped_reason: str = ""
    approval_required: bool = False
    pending_task_ids: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class RunExecutor:
    """Execute tasks in a Ralph run.

    Iterates through tasks, running iterations until each task passes
    or the arbiter/loop-guard stops execution.

    Default behaviour is safe (dry-run): no real execution occurs.
    """

    def __init__(
        self,
        config: RunExecutorConfig | None = None,
        workspace: RalphWorkspace | None = None,
        task_library: TaskLibrary | None = None,
        checkpoint_store: CheckpointStore | None = None,
        context_builder: ContextBuilder | None = None,
        iteration_runner: IterationRunner | None = None,
        run_lifecycle: RunLifecycle | None = None,
        loop_guard: LoopGuard | None = None,
        arbiter: ArbiterEngine | None = None,
    ) -> None:
        self._config = config or RunExecutorConfig()
        ws = workspace or RalphWorkspace()
        self._workspace = ws
        self._task_library = task_library or TaskLibrary(ws)
        self._checkpoint_store = checkpoint_store or CheckpointStore(ws)
        self._context_builder = context_builder or ContextBuilder(
            workspace=ws, repo_root="."
        )
        self._iteration_runner = iteration_runner or IterationRunner(
            workspace=ws,
            task_library=self._task_library,
            checkpoint_store=self._checkpoint_store,
            context_builder=self._context_builder,
        )
        self._run_lifecycle = run_lifecycle or RunLifecycle(
            workspace=ws,
            task_library=self._task_library,
            checkpoint_store=self._checkpoint_store,
            context_builder=self._context_builder,
        )
        self._loop_guard = loop_guard or LoopGuard()
        self._arbiter = arbiter or ArbiterEngine()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run_next_task(
        self,
        run: RalphRun,
        goal: ProjectGoal | None = None,
    ) -> IterationRunResult | None:
        """Find and run the next approved task.

        Returns the iteration result, or None if no runnable task exists.
        PENDING tasks are skipped unless ``auto_approve_pending_tasks=True``.
        """
        task = self._find_next_task(run)
        if task is None:
            return None

        # Approval gate: PENDING tasks require explicit approval or config
        if task.status == TaskStatus.PENDING:
            if not self._config.auto_approve_pending_tasks:
                return None
            self._run_lifecycle.approve_task(task.id)
            task.status = TaskStatus.APPROVED

        # Mark running
        self._run_lifecycle.mark_task_running(task.id)
        task.status = TaskStatus.RUNNING

        # Run one iteration
        result = self._iteration_runner.run_iteration(
            run=run,
            task=task,
            iteration_number=1,
            goal=goal,
        )

        # Update task and run status from result
        if result.passed:
            task.status = TaskStatus.PASSED
            self._run_lifecycle.mark_task_result(task.id, passed=True)
        else:
            task.status = TaskStatus.NEEDS_FIX

        run.updated_at = _now_utc()
        return result

    def run_until_blocked(
        self,
        run: RalphRun,
        goal: ProjectGoal | None = None,
        max_tasks: int | None = None,
    ) -> RunExecutorResult:
        """Execute tasks until blocked, stopped, or max_tasks reached.

        Loops through runnable tasks, running one iteration per task.
        Stops when:
        - No more runnable tasks
        - Arbiter returns STOP or ESCALATE
        - Loop guard returns STOP
        - max_tasks limit is reached
        """
        task_results: list[IterationRunResult] = []
        tasks_run = 0

        while True:
            # Check max_tasks limit
            if max_tasks is not None and tasks_run >= max_tasks:
                return RunExecutorResult(
                    run=run,
                    task_results=task_results,
                    completed=False,
                    stopped_reason=f"Reached max_tasks limit ({max_tasks}).",
                )

            # Find next task
            task = self._find_next_task(run)
            if task is None:
                # Check if all tasks are done
                all_done = (
                    all(t.status == TaskStatus.PASSED for t in run.tasks)
                    if run.tasks
                    else False
                )
                if all_done:
                    run.status = RunStatus.COMPLETED
                    return RunExecutorResult(
                        run=run,
                        task_results=task_results,
                        completed=True,
                    )
                # Check if approval is needed
                pending_ids = [
                    t.id for t in (run.tasks or [])
                    if t.status == TaskStatus.PENDING
                ]
                if pending_ids and not self._config.auto_approve_pending_tasks:
                    return RunExecutorResult(
                        run=run,
                        task_results=task_results,
                        completed=False,
                        approval_required=True,
                        pending_task_ids=pending_ids,
                        stopped_reason=(
                            f"Approval required for {len(pending_ids)} pending "
                            f"task(s). Set auto_approve_pending_tasks=True or "
                            f"approve tasks via RunLifecycle.approve_task()."
                        ),
                    )
                return RunExecutorResult(
                    run=run,
                    task_results=task_results,
                    completed=False,
                    stopped_reason="No runnable tasks found.",
                )

            # Approval gate: PENDING tasks require explicit approval or config
            if task.status == TaskStatus.PENDING:
                if not self._config.auto_approve_pending_tasks:
                    pending_ids = [
                        t.id for t in (run.tasks or [])
                        if t.status == TaskStatus.PENDING
                    ]
                    return RunExecutorResult(
                        run=run,
                        task_results=task_results,
                        completed=False,
                        approval_required=True,
                        pending_task_ids=pending_ids,
                        stopped_reason=(
                            f"Approval required for task {task.id}. "
                            f"Set auto_approve_pending_tasks=True or approve "
                            f"via RunLifecycle.approve_task()."
                        ),
                    )
                self._run_lifecycle.approve_task(task.id)
                task.status = TaskStatus.APPROVED

            # Mark running
            self._run_lifecycle.mark_task_running(task.id)
            task.status = TaskStatus.RUNNING

            # Run one iteration
            result = self._iteration_runner.run_iteration(
                run=run,
                task=task,
                iteration_number=1,
                goal=goal,
            )
            task_results.append(result)
            tasks_run += 1

            # Update task status
            if result.passed:
                task.status = TaskStatus.PASSED
                self._run_lifecycle.mark_task_result(task.id, passed=True)
            else:
                task.status = TaskStatus.NEEDS_FIX

            # Check arbiter decision for stop signals
            action = result.quality_gate_result.arbiter_decision.action
            if action == ArbiterAction.STOP:
                run.status = RunStatus.FAILED
                return RunExecutorResult(
                    run=run,
                    task_results=task_results,
                    failed=True,
                    stopped_reason=(
                        f"Arbiter stopped on task {task.id}: "
                        f"{result.quality_gate_result.arbiter_decision.reason}"
                    ),
                )

            if action == ArbiterAction.ESCALATE:
                run.status = RunStatus.FAILED
                return RunExecutorResult(
                    run=run,
                    task_results=task_results,
                    failed=True,
                    stopped_reason=(
                        f"Arbiter escalated on task {task.id}: "
                        f"{result.quality_gate_result.arbiter_decision.reason}"
                    ),
                )

            # Check loop guard
            lg_action = result.quality_gate_result.loop_guard_decision.action
            if lg_action.value == "stop":
                run.status = RunStatus.FAILED
                return RunExecutorResult(
                    run=run,
                    task_results=task_results,
                    failed=True,
                    stopped_reason=(
                        f"Loop guard stopped on task {task.id}: "
                        f"{result.quality_gate_result.loop_guard_decision.reason}"
                    ),
                )

            run.updated_at = _now_utc()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _find_next_task(self, run: RalphRun) -> RalphTask | None:
        """Find the next task eligible for execution.

        Returns tasks with PENDING or APPROVED status. The caller
        (run_next_task / run_until_blocked) enforces the approval gate:
        PENDING tasks only proceed if ``auto_approve_pending_tasks`` is set.
        """
        runnable_statuses = {TaskStatus.PENDING, TaskStatus.APPROVED}
        for task in run.tasks:
            if task.status in runnable_statuses:
                return task
        return None
