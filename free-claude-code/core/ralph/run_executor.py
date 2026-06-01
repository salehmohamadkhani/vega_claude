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

    When ``gate_config`` is provided, Agent Council evidence gates are
    enforced against task results during execution.
    """

    auto_approve_pending_tasks: bool = False
    max_iterations_per_task: int = 1
    stop_on_debug: bool = True
    stop_on_escalate: bool = True
    gate_config: object | None = None  # RuntimeGateConfig


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
    blocked_task_id: str = ""
    retry_required: bool = False
    debug_required: bool = False
    escalation_required: bool = False
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

        # Propagate gate_config from RunExecutorConfig to IterationRunner
        if self._config.gate_config is not None:
            irc = self._iteration_runner._config
            if irc.gate_config is None:
                irc.gate_config = self._config.gate_config

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_run_tasks(self, tasks: list[RalphTask], run_id: str = "") -> None:
        """Populate the in-memory run table from persisted tasks.

        ``RunTable`` is in-memory and does not survive process restarts.
        Call this before ``run_until_blocked()`` when tasks have been
        loaded from persistent storage (e.g., CLI re-entry).
        """
        self._run_lifecycle.load_run_tasks(tasks, run_id)

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
        Respects ``RunExecutorConfig`` for stop-on-debug, stop-on-escalate,
        max-iterations-per-task, and auto-approve settings.

        Stops when:
        - No more runnable tasks
        - Approval is required (Policy A: first pending blocks)
        - Arbiter returns STOP
        - Arbiter returns DEBUG and ``stop_on_debug=True``
        - Arbiter returns ESCALATE and ``stop_on_escalate=True``
        - ``max_iterations_per_task`` exceeded (was reached via RETRY)
        - Loop guard returns STOP
        - ``max_tasks`` limit is reached
        """
        task_results: list[IterationRunResult] = []
        tasks_run = 0
        # Track iterations per task for max_iterations_per_task enforcement
        task_iterations: dict[str, int] = {}

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
                # Check if approval is needed (Policy A: strict ordered)
                pending_ids = [
                    t.id for t in (run.tasks or []) if t.status == TaskStatus.PENDING
                ]
                if pending_ids and not self._config.auto_approve_pending_tasks:
                    return RunExecutorResult(
                        run=run,
                        task_results=task_results,
                        completed=False,
                        approval_required=True,
                        pending_task_ids=pending_ids,
                        blocked_task_id=pending_ids[0],
                        stopped_reason=(
                            f"Approval required for {len(pending_ids)} pending "
                            f"task(s). Set auto_approve_pending_tasks=True or "
                            f"approve tasks via RunLifecycle.approve_task(). "
                            f"First blocking task: {pending_ids[0]}"
                        ),
                    )
                return RunExecutorResult(
                    run=run,
                    task_results=task_results,
                    completed=False,
                    stopped_reason="No runnable tasks found.",
                )

            # Policy A: strict ordered execution — first PENDING blocks
            # even if later tasks are APPROVED
            if task.status == TaskStatus.PENDING:
                if not self._config.auto_approve_pending_tasks:
                    pending_ids = [
                        t.id
                        for t in (run.tasks or [])
                        if t.status == TaskStatus.PENDING
                    ]
                    return RunExecutorResult(
                        run=run,
                        task_results=task_results,
                        completed=False,
                        approval_required=True,
                        pending_task_ids=pending_ids,
                        blocked_task_id=task.id,
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

            # Track iteration count for max_iterations_per_task enforcement
            task_iterations[task.id] = task_iterations.get(task.id, 0) + 1
            iteration_number = task_iterations[task.id]

            # Enforce max_iterations_per_task
            if iteration_number > self._config.max_iterations_per_task:
                return RunExecutorResult(
                    run=run,
                    task_results=task_results,
                    completed=False,
                    stopped_reason=(
                        f"Task {task.id} reached max iterations "
                        f"({self._config.max_iterations_per_task})."
                    ),
                )

            # Run one iteration
            result = self._iteration_runner.run_iteration(
                run=run,
                task=task,
                iteration_number=iteration_number,
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

            # STOP always stops
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

            # RETRY: reset task to APPROVED so the next loop iteration
            # re-picks it up. The iteration counter already incremented,
            # so max_iterations_per_task enforcement is automatic.
            if action == ArbiterAction.RETRY:
                task.status = TaskStatus.APPROVED
                self._run_lifecycle.approve_task(task.id)
                run.updated_at = _now_utc()
                continue

            # DEBUG: stop if configured
            if action == ArbiterAction.DEBUG:
                if self._config.stop_on_debug:
                    return RunExecutorResult(
                        run=run,
                        task_results=task_results,
                        completed=False,
                        debug_required=True,
                        stopped_reason=(
                            f"Arbiter requested debug on task {task.id}: "
                            f"{result.quality_gate_result.arbiter_decision.reason}"
                        ),
                    )
                # If not stopping on debug, continue to next task
                continue

            # ESCALATE: stop if configured
            if action == ArbiterAction.ESCALATE:
                if self._config.stop_on_escalate:
                    run.status = RunStatus.FAILED
                    return RunExecutorResult(
                        run=run,
                        task_results=task_results,
                        failed=True,
                        escalation_required=True,
                        stopped_reason=(
                            f"Arbiter escalated on task {task.id}: "
                            f"{result.quality_gate_result.arbiter_decision.reason}"
                        ),
                    )
                # If not stopping on escalate, continue
                continue

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
