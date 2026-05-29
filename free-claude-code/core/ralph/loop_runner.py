"""CLI-driven Ralph loop runner.

Coordinates multi-iteration task execution through existing runtime
components. Enforces strict ordered approval (Policy A), retry loops,
debug/escalation handling, and persistent checkpoints.

Safe defaults: dry-run only, no auto-approval, stop on debug/escalate.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .arbiter import ArbiterAction
from .checkpoint import CheckpointStore
from .context_builder import ContextBuilder
from .iteration_runner import IterationRunner, IterationRunResult
from .loop_guard import LoopGuard
from .loop_policy import LoopPolicy, LoopStopReason
from .memory import MemoryRecord, MemoryStore
from .models import ProjectGoal, RalphRun, RalphTask, RunStatus, TaskStatus
from .quality_gate import QualityGate
from .task_library import TaskLibrary
from .workspace import RalphWorkspace


@dataclass
class TaskLoopResult:
    """Result of running a single task through multiple iterations."""

    task_id: str = ""
    task_title: str = ""
    iterations: list[IterationRunResult] = field(default_factory=list)
    final_status: TaskStatus = TaskStatus.PENDING
    final_action: str = ""
    passed: bool = False
    stopped_reason: str = ""
    checkpoints_created: int = 0
    last_error: str = ""
    next_action: str = ""


@dataclass
class RalphLoopResult:
    """Overall outcome of a Ralph loop run."""

    run_id: str = ""
    completed: bool = False
    stopped_reason: str = ""
    stopped_reason_enum: LoopStopReason = LoopStopReason.COMPLETED
    task_results: list[TaskLoopResult] = field(default_factory=list)
    approval_required: bool = False
    pending_task_ids: list[str] = field(default_factory=list)
    blocked_task_id: str = ""
    retry_required: bool = False
    debug_required: bool = False
    escalation_required: bool = False
    total_iterations: int = 0
    checkpoints_created: int = 0
    report_path: str = ""
    dry_run: bool = True


class RalphLoopRunner:
    """Run a multi-iteration Ralph loop for approved tasks.

    Orchestrates: task selection (Policy A) → per-task iteration loop
    → arbiter action handling → checkpoint/memory/context persistence.

    Uses existing ``IterationRunner``, ``QualityGate``, ``LoopGuard``,
    ``Arbiter``, ``CheckpointStore``, ``MemoryStore``, and
    ``ContextBuilder``. Does not reimplement execution or quality gate
    logic.
    """

    def __init__(
        self,
        workspace: RalphWorkspace | None = None,
        task_library: TaskLibrary | None = None,
        iteration_runner: IterationRunner | None = None,
        quality_gate: QualityGate | None = None,
        loop_guard: LoopGuard | None = None,
        checkpoint_store: CheckpointStore | None = None,
        memory_store: MemoryStore | None = None,
        context_builder: ContextBuilder | None = None,
    ) -> None:
        ws = workspace or RalphWorkspace()
        self._workspace = ws
        self._task_library = task_library or TaskLibrary(ws)
        self._checkpoint_store = checkpoint_store or CheckpointStore(ws)
        self._memory_store = memory_store or MemoryStore(ws)
        self._context_builder = context_builder or ContextBuilder(
            workspace=ws, repo_root="."
        )
        self._iteration_runner = iteration_runner or IterationRunner(
            workspace=ws,
            task_library=self._task_library,
            checkpoint_store=self._checkpoint_store,
            context_builder=self._context_builder,
        )
        self._quality_gate = quality_gate or QualityGate()
        self._loop_guard = loop_guard or LoopGuard()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(
        self,
        run: RalphRun,
        tasks: list[RalphTask],
        policy: LoopPolicy | None = None,
        goal: ProjectGoal | None = None,
    ) -> RalphLoopResult:
        """Run the Ralph loop for a set of tasks.

        Enforces strict ordered approval (Policy A): tasks are processed
        in order, the first PENDING task blocks all later tasks.

        Parameters
        ----------
        run:
            The RalphRun to execute.
        tasks:
            All tasks for this run (PENDING, APPROVED, PASSED, etc.).
        policy:
            Loop policy (safe defaults if omitted).
        goal:
            Optional ProjectGoal for prompt context.

        Returns
        -------
        A ``RalphLoopResult`` with per-task results and overall status.
        """
        effective_policy = policy or LoopPolicy()
        dry_run = effective_policy.dry_run

        task_results: list[TaskLoopResult] = []
        total_iterations = 0
        total_checkpoints = 0

        # Policy A: strict ordered execution
        first_pending_idx, pending_ids = self._find_first_pending_index(
            tasks, effective_policy.strict_task_order, effective_policy.require_approval
        )

        # If the very first task is PENDING, block the entire loop
        if first_pending_idx == 0 and effective_policy.require_approval:
            return RalphLoopResult(
                run_id=run.id,
                completed=False,
                stopped_reason=f"Approval required for task {tasks[0].id}.",
                stopped_reason_enum=LoopStopReason.APPROVAL_REQUIRED,
                approval_required=True,
                pending_task_ids=pending_ids,
                blocked_task_id=tasks[0].id,
                dry_run=dry_run,
            )

        # Contiguous runnable prefix: APPROVED tasks after PASSED ones
        runnable: list[RalphTask] = []
        first_blocked: str | None = None
        for t in tasks:
            if t.status == TaskStatus.APPROVED:
                runnable.append(t)
            elif t.status == TaskStatus.PASSED:
                continue  # Skip already-completed tasks
            else:
                if (
                    effective_policy.require_approval
                    and effective_policy.strict_task_order
                    and t.status == TaskStatus.PENDING
                ):
                    first_blocked = t.id
                break

        # Apply max_tasks limit
        if effective_policy.max_tasks is not None:
            runnable = runnable[: effective_policy.max_tasks]

        if not runnable:
            if first_blocked:
                return RalphLoopResult(
                    run_id=run.id,
                    completed=False,
                    stopped_reason=f"Approval required for task {first_blocked}.",
                    stopped_reason_enum=LoopStopReason.APPROVAL_REQUIRED,
                    approval_required=True,
                    pending_task_ids=pending_ids,
                    blocked_task_id=first_blocked,
                    dry_run=dry_run,
                )
            return RalphLoopResult(
                run_id=run.id,
                completed=True,
                stopped_reason="No approved tasks to run.",
                stopped_reason_enum=LoopStopReason.COMPLETED,
                dry_run=dry_run,
            )

        run.status = RunStatus.RUNNING

        for task in runnable:
            # Run multi-iteration loop for this task
            task_result = self._run_task_loop(
                run=run,
                task=task,
                policy=effective_policy,
                goal=goal,
            )
            task_results.append(task_result)
            total_iterations += len(task_result.iterations)
            total_checkpoints += task_result.checkpoints_created

            # Persist task status
            task.status = task_result.final_status
            self._task_library.save_task(task)

            # Stop if the task result indicates we should not continue
            if not task_result.passed and task_result.next_action in (
                "debug",
                "escalate",
                "stop",
            ):
                break

        # Determine overall loop result
        all_passed = all(r.passed for r in task_results)

        pending_blocked = first_blocked

        if all_passed and not pending_blocked:
            run.status = RunStatus.COMPLETED
            return RalphLoopResult(
                run_id=run.id,
                completed=True,
                stopped_reason="All tasks completed.",
                stopped_reason_enum=LoopStopReason.COMPLETED,
                task_results=task_results,
                total_iterations=total_iterations,
                checkpoints_created=total_checkpoints,
                dry_run=dry_run,
            )

        if pending_blocked:
            # Approval for the next task is required — it blocks
            # further progress even if a task had debug/retry/escalate.
            return RalphLoopResult(
                run_id=run.id,
                completed=False,
                stopped_reason=f"Approval required for task {pending_blocked}.",
                stopped_reason_enum=LoopStopReason.APPROVAL_REQUIRED,
                task_results=task_results,
                approval_required=True,
                pending_task_ids=pending_ids,
                blocked_task_id=pending_blocked,
                total_iterations=total_iterations,
                checkpoints_created=total_checkpoints,
                dry_run=dry_run,
            )

        # Find the first non-passing result for stop reason
        for r in task_results:
            if not r.passed:
                if r.next_action == "retry":
                    return RalphLoopResult(
                        run_id=run.id,
                        completed=False,
                        stopped_reason=r.stopped_reason,
                        stopped_reason_enum=LoopStopReason.RETRY_REQUIRED,
                        task_results=task_results,
                        retry_required=True,
                        total_iterations=total_iterations,
                        checkpoints_created=total_checkpoints,
                        dry_run=dry_run,
                    )
                if r.next_action == "debug":
                    return RalphLoopResult(
                        run_id=run.id,
                        completed=False,
                        stopped_reason=r.stopped_reason,
                        stopped_reason_enum=LoopStopReason.DEBUG_REQUIRED,
                        task_results=task_results,
                        debug_required=True,
                        total_iterations=total_iterations,
                        checkpoints_created=total_checkpoints,
                        dry_run=dry_run,
                    )
                if r.next_action == "escalate":
                    return RalphLoopResult(
                        run_id=run.id,
                        completed=False,
                        stopped_reason=r.stopped_reason,
                        stopped_reason_enum=LoopStopReason.ESCALATION_REQUIRED,
                        task_results=task_results,
                        escalation_required=True,
                        total_iterations=total_iterations,
                        checkpoints_created=total_checkpoints,
                        dry_run=dry_run,
                    )
                return RalphLoopResult(
                    run_id=run.id,
                    completed=False,
                    stopped_reason=r.stopped_reason or "Task did not pass.",
                    stopped_reason_enum=LoopStopReason.QUALITY_GATE_FAILED,
                    task_results=task_results,
                    total_iterations=total_iterations,
                    checkpoints_created=total_checkpoints,
                    dry_run=dry_run,
                )

        return RalphLoopResult(
            run_id=run.id,
            completed=False,
            stopped_reason="Loop stopped without completing all tasks.",
            stopped_reason_enum=LoopStopReason.ERROR,
            task_results=task_results,
            total_iterations=total_iterations,
            checkpoints_created=total_checkpoints,
            dry_run=dry_run,
        )

    # ------------------------------------------------------------------
    # Internal: per-task multi-iteration loop
    # ------------------------------------------------------------------

    def _run_task_loop(
        self,
        run: RalphRun,
        task: RalphTask,
        policy: LoopPolicy,
        goal: ProjectGoal | None = None,
    ) -> TaskLoopResult:
        """Run a single task through multiple iterations.

        Iterates up to ``policy.max_iterations_per_task`` times, checking
        the arbiter action after each iteration.

        States:
        - APPROVE / action=approve → task passed, stop iterating
        - RETRY → continue to next iteration (if under limit)
        - DEBUG → stop if policy says so
        - ESCALATE → stop if policy says so
        - STOP → stop with failure
        """
        iterations: list[IterationRunResult] = []
        last_action = ""
        last_passed = False
        stopped_reason = ""
        iters_run = 0

        checkpoint_count_before = len(
            self._checkpoint_store.list_for_run(run.id)
        )

        for iteration_number in range(1, policy.max_iterations_per_task + 1):
            # Mark task running on first iteration
            if iteration_number == 1:
                task.status = TaskStatus.RUNNING

            result = self._iteration_runner.run_iteration(
                run=run,
                task=task,
                iteration_number=iteration_number,
                goal=goal,
            )
            iterations.append(result)
            iters_run = iteration_number

            action = result.quality_gate_result.arbiter_decision.action
            last_action = action.value
            last_passed = result.passed

            # Add memory record for this iteration
            self._add_iteration_memory(run.id, task, iteration_number, result)

            # Handle arbiter action
            if action == ArbiterAction.APPROVE:
                task.status = TaskStatus.PASSED
                return TaskLoopResult(
                    task_id=task.id,
                    task_title=task.title,
                    iterations=iterations,
                    final_status=TaskStatus.PASSED,
                    final_action="approve",
                    passed=True,
                    stopped_reason="",
                    next_action="approve",
                    checkpoints_created=(
                        len(self._checkpoint_store.list_for_run(run.id))
                        - checkpoint_count_before
                    ),
                )

            if action == ArbiterAction.RETRY:
                if iteration_number < policy.max_iterations_per_task:
                    task.status = TaskStatus.NEEDS_FIX
                    continue  # next iteration
                # Max iterations reached
                stopped_reason = (
                    f"Task {task.id} reached max iterations "
                    f"({policy.max_iterations_per_task}) with RETRY."
                )
                task.status = TaskStatus.NEEDS_FIX
                break

            if action == ArbiterAction.DEBUG:
                if policy.stop_on_debug:
                    stopped_reason = (
                        f"Arbiter requested debug on task {task.id}: "
                        f"{result.quality_gate_result.arbiter_decision.reason}"
                    )
                    task.status = TaskStatus.NEEDS_FIX
                    break
                # Continue despite debug
                continue

            if action == ArbiterAction.ESCALATE:
                if policy.stop_on_escalate:
                    stopped_reason = (
                        f"Arbiter escalated on task {task.id}: "
                        f"{result.quality_gate_result.arbiter_decision.reason}"
                    )
                    task.status = TaskStatus.FAILED
                    break
                # Continue despite escalate
                continue

            if action == ArbiterAction.STOP:
                stopped_reason = (
                    f"Arbiter stopped on task {task.id}: "
                    f"{result.quality_gate_result.arbiter_decision.reason}"
                )
                task.status = TaskStatus.FAILED
                break

        # If we didn't return during the loop, determine final state
        if not stopped_reason and iters_run >= policy.max_iterations_per_task:
            stopped_reason = (
                f"Task {task.id} completed {iters_run} iteration(s) "
                f"without passing."
            )

        return TaskLoopResult(
            task_id=task.id,
            task_title=task.title,
            iterations=iterations,
            final_status=task.status,
            final_action=last_action,
            passed=last_passed and last_action == "approve",
            stopped_reason=stopped_reason,
            next_action=last_action,
            checkpoints_created=(
                len(self._checkpoint_store.list_for_run(run.id))
                - checkpoint_count_before
            ),
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _find_first_pending_index(
        self,
        tasks: list[RalphTask],
        strict_task_order: bool,
        require_approval: bool,
    ) -> tuple[int | None, list[str]]:
        """Find the index of the first PENDING task (Policy A).

        Returns ``(first_pending_index, pending_task_ids)``.

        When ``strict_task_order`` is True, returns the index of the first
        PENDING task.  When the first task (index 0) is PENDING, the loop
        is blocked entirely.  When a later task is PENDING, earlier APPROVED
        tasks in the prefix still run — the pending blocker is surfaced
        after execution.

        Returns ``(None, [])`` when all tasks are non-pending or approval
        is not required.
        """
        if not require_approval:
            return None, []

        pending_ids = [t.id for t in tasks if t.status == TaskStatus.PENDING]
        if not pending_ids or not strict_task_order:
            return None, pending_ids

        for i, t in enumerate(tasks):
            if t.status == TaskStatus.PENDING:
                return i, pending_ids

        return None, pending_ids

    def _add_iteration_memory(
        self,
        run_id: str,
        task: RalphTask,
        iteration_number: int,
        result: IterationRunResult,
    ) -> None:
        """Add an episodic memory record for a task iteration."""
        try:
            action = result.quality_gate_result.arbiter_decision.action.value
            status = "PASSED" if result.passed else "NOT_PASSED"
            record = MemoryRecord(
                level="episodic",
                content=(
                    f"Iteration {iteration_number} of task {task.id} "
                    f"({task.title}): {status}, action={action}"
                ),
                tags=[f"task:{task.id}", f"iteration:{iteration_number}", status.lower()],
                source="ralph_loop_runner",
                importance=50 if result.passed else 70,
            )
            self._memory_store.add(record)
        except Exception:
            pass  # Memory failures are non-fatal
