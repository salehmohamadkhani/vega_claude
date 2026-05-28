"""FCC-native CLI surface for the Ralph Runtime.

Usage:
    fcc-ralph plan <goal> [options]
    fcc-ralph review [options]
    fcc-ralph approve [--all | <task-id>] [options]
    fcc-ralph run [options]
    fcc-ralph status [options]
    fcc-ralph report [options]
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import UTC, datetime
from typing import Any

from .agent_profiles import AgentProfileRegistry
from .checkpoint import CheckpointStore
from .execution_guard import check_real_execution_safety
from .loop_policy import LoopPolicy
from .loop_runner import RalphLoopRunner
from .models import ProjectGoal, RalphRun, RunStatus, TaskStatus
from .planner import TaskPlanner
from .real_pilot import RealPilot, RealPilotConfig, RealPilotResult
from .run_executor import RunExecutor, RunExecutorConfig
from .run_lifecycle import RunLifecycle
from .task_library import TaskLibrary
from .workspace import RalphWorkspace

# ---------------------------------------------------------------------------
# Exit codes
# ---------------------------------------------------------------------------

EXIT_SUCCESS = 0
EXIT_ERROR = 1
EXIT_INVALID_INPUT = 2
EXIT_TASK_NOT_FOUND = 3
EXIT_APPROVAL_REQUIRED = 4
EXIT_UNSAFE_REAL = 5


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------


def _print_json(data: Any) -> None:
    json.dump(data, sys.stdout, indent=2, default=str)
    sys.stdout.write("\n")


def _error(msg: str, exit_code: int = EXIT_ERROR) -> None:
    print(f"Error: {msg}", file=sys.stderr)
    sys.exit(exit_code)


def _warn(msg: str) -> None:
    print(f"Warning: {msg}", file=sys.stderr)


def _detect_loop_state(
    by_status: dict[str, int],
    run_meta: dict[str, Any] | None,
    checkpoints: list[dict[str, Any]],
) -> dict[str, Any]:
    """Detect loop state from task statuses, run meta, and checkpoints."""
    state: dict[str, Any] = {
        "has_pending": "pending" in by_status,
        "has_approved": "approved" in by_status,
        "has_needs_fix": "needs_fix" in by_status,
        "has_failed": "failed" in by_status,
        "has_passed": "passed" in by_status,
    }
    if run_meta:
        state["run_status"] = run_meta.get("status", "")
    if checkpoints:
        latest = checkpoints[0]
        state["latest_task"] = latest.get("task_id", "")
        state["latest_action"] = latest.get("action", "")
        state["latest_iteration"] = latest.get("iteration", 0)
    return state


def _print_task_result_line(
    r: Any,
    *,
    label: str | None = None,
) -> None:
    """Print a single iteration result line."""
    tid = label or r.task_id
    passed_str = "PASSED" if r.passed else "NOT PASSED"
    status_ = r.execution_result.status.value
    action = r.quality_gate_result.arbiter_decision.action.value
    print(f"  {tid}: {passed_str}")
    print(f"    Mode: dry-run  Status: {status_}  Action: {action}")
    if r.failure_reason:
        print(f"    Reason: {r.failure_reason}")


# ---------------------------------------------------------------------------
# Workspace helpers
# ---------------------------------------------------------------------------


def _open_workspace(workspace_arg: str | None) -> RalphWorkspace:
    return RalphWorkspace(project_root=workspace_arg or ".")


def _ensure_workspace(ws: RalphWorkspace) -> None:
    if not ws.exists():
        ws.initialize()


def _load_latest_run_meta(ws: RalphWorkspace) -> dict[str, Any] | None:
    """Load the most recent run metadata from workspace."""
    run_files = ws.list_paths("runs/*.json")
    if not run_files:
        return None
    run_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    try:
        return ws.read_json(f"runs/{run_files[0].name}")
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Plan
# ---------------------------------------------------------------------------


def _cmd_plan(args: argparse.Namespace) -> int:
    """Create a project goal, generate tasks, and persist them."""
    ws = _open_workspace(args.workspace)
    _ensure_workspace(ws)

    goal = ProjectGoal(
        title=args.title or args.goal[:80],
        description=args.goal,
        constraints=list(args.constraint),
        success_kpis=list(args.kpi),
    )

    planner = TaskPlanner()
    task_plan = planner.plan(goal)

    # Persist goal
    ws.write_json(
        f"goals/{goal.id}.json",
        {
            "id": goal.id,
            "title": goal.title,
            "description": goal.description,
            "constraints": list(goal.constraints),
            "success_kpis": list(goal.success_kpis),
        },
    )

    # Prepare run (persists tasks, run metadata, initial checkpoint)
    lifecycle = RunLifecycle(workspace=ws)
    result = lifecycle.prepare_run(goal=goal, tasks=task_plan.tasks)

    if args.json:
        _print_json(
            {
                "goal_id": goal.id,
                "run_id": result.run.id,
                "question_count": len(task_plan.questions),
                "task_count": len(task_plan.tasks),
                "spec": {
                    "title": task_plan.spec.title,
                    "summary": task_plan.spec.summary,
                    "constraints": task_plan.spec.constraints,
                    "kpis": task_plan.spec.success_kpis,
                },
                "tasks": [
                    {
                        "id": t.id,
                        "title": t.title,
                        "role": t.agent_role.value,
                        "status": t.status.value,
                    }
                    for t in task_plan.tasks
                ],
            }
        )
    else:
        print(f"Goal: {goal.title}")
        print(f"Goal ID: {goal.id}")
        print(f"Run ID: {result.run.id}")
        print(f"Questions generated: {len(task_plan.questions)}")
        print(f"Tasks generated: {len(task_plan.tasks)}")
        print()
        for t in task_plan.tasks:
            print(f"  {t.id}  [{t.agent_role.value}]  {t.title}")
        print()
        print("Tasks are PENDING — review and approve before running:")
        print()
        print("  fcc-ralph review")
        print("  fcc-ralph approve <task-id>")

    return EXIT_SUCCESS


# ---------------------------------------------------------------------------
# Review
# ---------------------------------------------------------------------------


def _cmd_review(args: argparse.Namespace) -> int:
    """Show tasks and their approval status."""
    ws = _open_workspace(args.workspace)
    if not ws.exists():
        _error("No Ralph workspace found. Run 'fcc-ralph plan' first.", EXIT_ERROR)

    task_lib = TaskLibrary(workspace=ws)

    if args.task:
        task = task_lib.find_task(args.task)
        if task is None:
            _error(f"Task {args.task!r} not found.", EXIT_TASK_NOT_FOUND)
        assert task is not None
        tasks = [task]
    else:
        tasks = task_lib.list_tasks()

    if args.json:
        _print_json(
            [
                {
                    "id": t.id,
                    "title": t.title,
                    "status": t.status.value,
                    "agent_role": t.agent_role.value,
                    "acceptance_criteria": t.acceptance_criteria,
                    "verification_commands": t.verification_commands,
                    "smoke_targets": t.smoke_targets,
                    "kpis": t.kpis,
                }
                for t in tasks
            ]
        )
        return EXIT_SUCCESS

    if not tasks:
        print("No tasks found in workspace.")
        return EXIT_SUCCESS

    by_status: dict[str, int] = {}
    for t in tasks:
        by_status[t.status.value] = by_status.get(t.status.value, 0) + 1

    print(f"Tasks: {len(tasks)} total")
    for status in ["pending", "approved", "running", "passed", "failed", "needs_fix"]:
        count = by_status.get(status, 0)
        if count:
            print(f"  {status}: {count}")

    print()
    for t in tasks:
        status_char = (
            "✓"
            if t.status == TaskStatus.APPROVED
            else "◷"
            if t.status == TaskStatus.RUNNING
            else "✔"
            if t.status == TaskStatus.PASSED
            else "○"
        )
        print(f"  {status_char}  {t.id}  [{t.agent_role.value}]  {t.title}")
        if t.acceptance_criteria and args.verbose:
            for ac in t.acceptance_criteria:
                print(f"     AC: {ac[:80]}")

    pending = [t for t in tasks if t.status == TaskStatus.PENDING]
    if pending:
        print()
        print(f"{len(pending)} task(s) pending approval.")
        print("Approve with: fcc-ralph approve <task-id>")

    return EXIT_SUCCESS


# ---------------------------------------------------------------------------
# Approve
# ---------------------------------------------------------------------------


def _cmd_approve(args: argparse.Namespace) -> int:
    """Approve one or all pending tasks."""
    ws = _open_workspace(args.workspace)
    if not ws.exists():
        _error("No Ralph workspace found. Run 'fcc-ralph plan' first.", EXIT_ERROR)

    task_lib = TaskLibrary(workspace=ws)

    if args.all:
        tasks = task_lib.list_tasks()
        pending = [t for t in tasks if t.status == TaskStatus.PENDING]
        if not pending:
            print("No pending tasks to approve.")
            return EXIT_SUCCESS
        for task in pending:
            task.status = TaskStatus.APPROVED
            task_lib.save_task(task)
        if args.json:
            _print_json({"approved": [t.id for t in pending]})
        else:
            print(f"Approved {len(pending)} task(s):")
            for t in pending:
                print(f"  {t.id}  {t.title}")
    else:
        task = task_lib.find_task(args.task_id)
        if task is None:
            _error(f"Task {args.task_id!r} not found.", EXIT_TASK_NOT_FOUND)
        if task.status == TaskStatus.APPROVED:
            print(f"Task {args.task_id} is already approved.")
            return EXIT_SUCCESS
        task.status = TaskStatus.APPROVED
        task_lib.save_task(task)
        if args.json:
            _print_json({"id": task.id, "status": "approved"})
        else:
            print(f"Approved: {task.id}  {task.title}")

    return EXIT_SUCCESS


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------


def _cmd_run(args: argparse.Namespace) -> int:
    """Run approved tasks through the Ralph runtime (dry-run by default).

    Delegates execution and approval policy to ``RunExecutor`` so that
    strict ordered execution (Policy A) is enforced. The CLI remains a
    thin wrapper: it validates flags, loads workspace state, creates the
    executor, and prints results — it does not reimplement task selection
    or execution logic.
    """
    ws = _open_workspace(args.workspace)
    if not ws.exists():
        _error("No Ralph workspace found. Run 'fcc-ralph plan' first.", EXIT_ERROR)

    task_lib = TaskLibrary(workspace=ws)
    all_tasks = task_lib.list_tasks()
    if not all_tasks:
        _error("No tasks in workspace.", EXIT_ERROR)

    # --real safety gate (CLI-level validation)
    if args.real and not args.allow_real_execution:
        _error(
            "--real requires --allow-real-execution. Defaulting to dry-run.",
            EXIT_UNSAFE_REAL,
        )

    approved = [t for t in all_tasks if t.status == TaskStatus.APPROVED]
    pending = [t for t in all_tasks if t.status == TaskStatus.PENDING]

    # Validate --task early (before approval/pending checks so that
    # a nonexistent task ID is reported correctly).
    if args.task:
        target = next((t for t in all_tasks if t.id == args.task), None)
        if target is None:
            _error(f"Task {args.task!r} not found.", EXIT_TASK_NOT_FOUND)
        assert target is not None
        if target.status != TaskStatus.APPROVED:
            _error(
                f"Task {args.task!r} is {target.status.value}, not APPROVED.",
                EXIT_APPROVAL_REQUIRED,
            )

    if not approved:
        if pending:
            _error(
                f"{len(pending)} task(s) are PENDING. "
                f"Approve them first: fcc-ralph approve <task-id>",
                EXIT_APPROVAL_REQUIRED,
            )
        _error("No approved tasks to run.", EXIT_ERROR)

    dry_run = not args.real or not args.allow_real_execution

    # Real execution guard (only when not dry-run)
    if not dry_run and args.workspace:
        guard_result = check_real_execution_safety(
            args.workspace,
            allow_repo_root_execution=args.allow_repo_root_execution,
            allow_dirty_git=args.allow_dirty_git,
        )
        if not guard_result.allowed:
            for reason in guard_result.failure_reasons:
                _warn(reason)
            _error(
                "Real execution blocked by safety guard. "
                "See warnings above.",
                EXIT_UNSAFE_REAL,
            )

    # Reconstruct run state from persisted metadata
    run_meta = _load_latest_run_meta(ws)
    run_id = run_meta.get("id", "") if run_meta else ""
    goal_id = run_meta.get("goal_id", "") if run_meta else ""

    # Build executor and populate its in-memory run table.
    # stop_on_debug=False: in dry-run the quality gate always returns
    # DEBUG (no verification results), so stopping on debug would
    # prevent multi-task dry-runs.
    executor = RunExecutor(
        workspace=ws,
        config=RunExecutorConfig(stop_on_debug=False),
    )

    if args.task:
        # --task mode with strict order enforcement (Policy A)
        target = next((t for t in all_tasks if t.id == args.task), None)
        if target is None:
            _error(f"Task {args.task!r} not found.", EXIT_TASK_NOT_FOUND)
        assert target is not None

        # Strict order: no earlier PENDING tasks may exist
        for t in all_tasks:
            if t.id == args.task:
                break
            if t.status == TaskStatus.PENDING:
                _error(
                    f"Cannot run {args.task}: task {t.id} is PENDING "
                    f"and blocks strict ordered execution.",
                    EXIT_APPROVAL_REQUIRED,
                )

        if target.status != TaskStatus.APPROVED:
            _error(
                f"Task {args.task} is not approved (status: {target.status.value}).",
                EXIT_APPROVAL_REQUIRED,
            )

        run = RalphRun(
            id=run_id,
            goal_id=goal_id,
            status=RunStatus.RUNNING,
            tasks=[target],
        )
        executor.load_run_tasks([target], run_id)
        max_tasks = 1
    else:
        run = RalphRun(
            id=run_id,
            goal_id=goal_id,
            status=RunStatus.RUNNING,
            tasks=all_tasks,
        )
        executor.load_run_tasks(all_tasks, run_id)
        max_tasks = args.max_tasks if args.max_tasks > 0 else None

    # Delegate execution to RunExecutor (enforces Policy A internally)
    result = executor.run_until_blocked(run=run, max_tasks=max_tasks)

    # Persist task status changes (RunExecutor modifies tasks in-place)
    for task in all_tasks:
        task_lib.save_task(task)

    # Build task results for display
    task_results_data = [
        {
            "task_id": r.task_id,
            "iteration": r.iteration,
            "execution_mode": r.execution_result.mode.value,
            "execution_status": r.execution_result.status.value,
            "quality_gate_action": r.quality_gate_result.arbiter_decision.action.value,
            "passed": r.passed,
            "next_action": r.next_action,
        }
        for r in result.task_results
    ]

    # ---- Handle result ----

    if result.approval_required:
        if args.json:
            _print_json(
                {
                    "status": "approval_required",
                    "completed": False,
                    "blocked_task_id": result.blocked_task_id,
                    "pending_task_ids": result.pending_task_ids,
                    "reason": result.stopped_reason,
                    "tasks_run": len(result.task_results),
                    "task_results": task_results_data,
                }
            )
        else:
            print("Run Results:")
            print(f"  Tasks run: {len(result.task_results)}")
            print(
                f"  Status: approval required — task "
                f"{result.blocked_task_id} is PENDING"
            )
            print()
            for r in result.task_results:
                _print_task_result_line(r)
            print()
            print(f"{len(result.pending_task_ids)} task(s) pending approval:")
            for tid in result.pending_task_ids:
                print(f"  {tid}")
            print()
            print("Approve with: fcc-ralph approve <task-id>")
        return EXIT_APPROVAL_REQUIRED

    if result.failed:
        if args.json:
            _print_json(
                {
                    "status": "failed",
                    "completed": False,
                    "stopped_reason": result.stopped_reason,
                    "tasks_run": len(result.task_results),
                    "task_results": task_results_data,
                }
            )
        else:
            print("Run Results:")
            print(f"  Tasks run: {len(result.task_results)}")
            print(f"  Status: FAILED — {result.stopped_reason}")
            print()
            for r in result.task_results:
                _print_task_result_line(r)
        return EXIT_ERROR

    if result.retry_required:
        if args.json:
            _print_json(
                {
                    "status": "retry_required",
                    "completed": False,
                    "stopped_reason": result.stopped_reason,
                    "tasks_run": len(result.task_results),
                    "task_results": task_results_data,
                }
            )
        else:
            print("Run Results:")
            print(f"  Tasks run: {len(result.task_results)}")
            print(f"  Status: retry required — {result.stopped_reason}")
            print()
            for r in result.task_results:
                _print_task_result_line(r)
        return EXIT_ERROR

    if result.debug_required:
        if args.json:
            _print_json(
                {
                    "status": "debug_required",
                    "completed": False,
                    "stopped_reason": result.stopped_reason,
                    "tasks_run": len(result.task_results),
                    "task_results": task_results_data,
                }
            )
        else:
            print("Run Results:")
            print(f"  Tasks run: {len(result.task_results)}")
            print(f"  Status: debug required — {result.stopped_reason}")
            print()
            for r in result.task_results:
                _print_task_result_line(r)
        return EXIT_ERROR

    # Success (completed or partial)
    status = "completed" if result.completed else "partial"
    if args.json:
        output: dict[str, Any] = {
            "status": status,
            "completed": result.completed,
            "tasks_run": len(result.task_results),
            "task_results": task_results_data,
        }
        if not result.completed:
            output["stopped_reason"] = result.stopped_reason
        _print_json(output)
    else:
        print("Run Results:")
        print(f"  Tasks run: {len(result.task_results)}")
        if result.completed:
            print("  Status: completed (all tasks passed)")
        else:
            print(f"  Status: {result.stopped_reason}")
        print()
        for r in result.task_results:
            _print_task_result_line(r)

    return EXIT_SUCCESS


# ---------------------------------------------------------------------------
# Run (loop mode) — multi-iteration Ralph loop
# ---------------------------------------------------------------------------


def _print_loop_result(result: Any, *, dry_run: bool) -> None:
    """Print a RalphLoopResult to stdout."""
    mode = "dry-run" if dry_run else "real"
    print(f"  Mode: {mode}")
    print(f"  Tasks attempted: {len(result.task_results)}")
    print(f"  Total iterations: {result.total_iterations}")
    print(f"  Checkpoints created: {result.checkpoints_created}")
    print()

    for tr in result.task_results:
        iters = len(tr.iterations)
        status = "PASSED" if tr.passed else "NOT PASSED"
        action = tr.final_action or "none"
        print(f"  {tr.task_id} ({tr.task_title[:50]}):")
        print(f"    Iterations: {iters}  Status: {status}  Action: {action}")
        if tr.stopped_reason:
            print(f"    Reason: {tr.stopped_reason}")
        if not tr.passed and tr.next_action:
            print(f"    Next recommended: {_next_step_hint(tr.next_action)}")

    print()
    if not result.completed:
        if result.approval_required:
            print("Next: fcc-ralph approve <task-id>")
        elif result.retry_required:
            print("Next: fcc-ralph run --loop (retry)")
        elif result.debug_required:
            print("Next: Investigate task output, then re-run")
        elif result.escalation_required:
            print("Next: Escalate to manual review")
        else:
            print(f"Status: {result.stopped_reason}")


def _print_loop_json(result: Any, *, dry_run: bool) -> None:
    """Print a RalphLoopResult as JSON."""
    _print_json(
        {
            "mode": "dry-run" if dry_run else "real",
            "completed": result.completed,
            "stopped_reason": result.stopped_reason,
            "approval_required": result.approval_required,
            "retry_required": result.retry_required,
            "debug_required": result.debug_required,
            "escalation_required": result.escalation_required,
            "total_iterations": result.total_iterations,
            "checkpoints_created": result.checkpoints_created,
            "blocked_task_id": result.blocked_task_id,
            "pending_task_ids": result.pending_task_ids,
            "task_results": [
                {
                    "task_id": tr.task_id,
                    "task_title": tr.task_title,
                    "iterations": len(tr.iterations),
                    "passed": tr.passed,
                    "final_action": tr.final_action,
                    "stopped_reason": tr.stopped_reason,
                    "next_action": tr.next_action,
                }
                for tr in result.task_results
            ],
        }
    )


def _next_step_hint(action: str) -> str:
    hints = {
        "approve": "Task approved, continue with next task",
        "retry": "fcc-ralph run --loop (will retry)",
        "debug": "Review dry-run output and task context",
        "escalate": "Manual review required",
        "stop": "Check task output for errors",
    }
    return hints.get(action, f"Action: {action}")


def _cmd_run_loop(args: argparse.Namespace) -> int:
    """Run approved tasks through the multi-iteration Ralph loop.

    Supports pilot mode (``--pilot``) for controlled real-execution
    validation, and guard flags (``--allow-dirty-git``,
    ``--allow-repo-root-execution``) for real execution safety.
    """
    # --- Pilot mode ---
    if args.pilot:
        return _cmd_pilot_run(args)

    ws = _open_workspace(args.workspace)
    if not ws.exists():
        _error("No Ralph workspace found. Run 'fcc-ralph plan' first.", EXIT_ERROR)

    task_lib = TaskLibrary(workspace=ws)
    all_tasks = task_lib.list_tasks()
    if not all_tasks:
        _error("No tasks in workspace.", EXIT_ERROR)

    # --real safety gate
    if args.real and not args.allow_real_execution:
        _error(
            "--real requires --allow-real-execution.",
            EXIT_UNSAFE_REAL,
        )

    dry_run = not args.real or not args.allow_real_execution

    # Real execution guard (only when not dry-run)
    if not dry_run and args.workspace:
        guard_result = check_real_execution_safety(
            args.workspace,
            allow_repo_root_execution=args.allow_repo_root_execution,
            allow_dirty_git=args.allow_dirty_git,
        )
        if not guard_result.allowed:
            for reason in guard_result.failure_reasons:
                _warn(reason)
            _error(
                "Real execution blocked by safety guard. "
                "See warnings above.",
                EXIT_UNSAFE_REAL,
            )

    # Build policy from CLI flags
    policy = LoopPolicy(
        max_tasks=args.max_tasks if args.max_tasks > 0 else None,
        max_iterations_per_task=args.max_iterations,
        stop_on_debug=args.stop_on_debug,
        stop_on_escalate=args.stop_on_escalate,
        dry_run=dry_run,
        allow_real_execution=args.allow_real_execution,
    )

    # Reconstruct run state from persisted metadata
    run_meta = _load_latest_run_meta(ws)
    run_id = run_meta.get("id", "") if run_meta else ""
    goal_id = run_meta.get("goal_id", "") if run_meta else ""

    run = RalphRun(
        id=run_id,
        goal_id=goal_id,
        status=RunStatus.RUNNING,
        tasks=all_tasks,
    )

    runner = RalphLoopRunner(workspace=ws, task_library=task_lib)
    result = runner.run(run=run, tasks=all_tasks, policy=policy)

    # Persist task status changes
    for task in all_tasks:
        task_lib.save_task(task)

    if args.json:
        _print_loop_json(result, dry_run=dry_run)
    else:
        mode = "Ralph Loop Results (dry-run)" if dry_run else "Ralph Loop Results"
        print(mode)
        print("=" * len(mode))
        _print_loop_result(result, dry_run=dry_run)

    if result.approval_required:
        return EXIT_APPROVAL_REQUIRED
    if result.retry_required or result.debug_required or result.escalation_required:
        return EXIT_ERROR
    if not result.completed:
        return EXIT_ERROR
    return EXIT_SUCCESS


def _print_pilot_result(result: RealPilotResult, *, json_mode: bool) -> None:
    """Print a RealPilotResult to stdout."""
    if json_mode:

        _print_json(
            {
                "pilot_workspace_path": result.pilot_workspace_path,
                "run_id": result.run_id,
                "task_id": result.task_id,
                "passed": result.passed,
                "changed_files": result.changed_files,
                "failure_reasons": result.failure_reasons,
                "guard": result.guard_result.to_dict() if result.guard_result else {},
                "loop": {
                    "completed": result.loop_result.completed
                    if result.loop_result
                    else False,
                    "stopped_reason": result.loop_result.stopped_reason
                    if result.loop_result
                    else "",
                    "approval_required": result.loop_result.approval_required
                    if result.loop_result
                    else False,
                    "total_iterations": result.loop_result.total_iterations
                    if result.loop_result
                    else 0,
                }
                if result.loop_result
                else None,
            }
        )
    else:
        print("Ralph Real Execution Pilot")
        print("=" * 60)
        print(f"  Pilot workspace: {result.pilot_workspace_path}")
        print(f"  Run ID: {result.run_id}")
        print(f"  Task ID: {result.task_id}")
        print(f"  Passed: {'yes' if result.passed else 'no'}")
        print()
        if result.guard_result:
            print(f"  Guard allowed: {result.guard_result.allowed}")
            if result.guard_result.failure_reasons:
                for r in result.guard_result.failure_reasons:
                    print(f"    Guard failure: {r}")
            print()
        if result.changed_files:
            print("  Changed files:")
            for f in result.changed_files:
                print(f"    {f}")
            print()
        if result.failure_reasons:
            print("  Failure reasons:")
            for r in result.failure_reasons:
                print(f"    {r}")
            print()
        if result.loop_result:
            print(f"  Loop completed: {result.loop_result.completed}")
            print(f"  Stopped reason: {result.loop_result.stopped_reason}")
            print(f"  Total iterations: {result.loop_result.total_iterations}")


def _cmd_pilot_run(args: argparse.Namespace) -> int:
    """Run the controlled real-execution pilot.

    Creates an isolated throwaway workspace, sets up a small task, and
    runs through the Ralph loop. Dry-run by default.

    The pilot is considered "passed" if:
    - No guard failures (real mode only)
    - No loop errors
    - The pilot infrastructure ran successfully

    In dry-run mode, the task may report ``debug_required`` from the
    quality gate — this is expected and does not indicate a pilot failure.
    """
    # --real safety gate
    if args.real and not args.allow_real_execution:
        _error(
            "--real requires --allow-real-execution.",
            EXIT_UNSAFE_REAL,
        )

    dry_run = not args.real or not args.allow_real_execution

    pilot_config = RealPilotConfig(
        pilot_workspace_path=args.pilot_workspace or "",
        dry_run=dry_run,
        allow_real_execution=args.allow_real_execution,
        max_iterations_per_task=args.max_iterations,
        allow_dirty_git=args.allow_dirty_git,
        allow_repo_root_execution=args.allow_repo_root_execution,
    )

    pilot = RealPilot(config=pilot_config)
    result = pilot.run()

    _print_pilot_result(result, json_mode=args.json)

    if result.guard_result and not result.guard_result.allowed:
        return EXIT_UNSAFE_REAL

    # Dry-run pilot: the loop may report debug/retry/non-completed from
    # the quality gate, but the pilot infrastructure itself succeeded.
    if dry_run:
        return EXIT_SUCCESS

    if result.passed:
        return EXIT_SUCCESS
    if result.loop_result and result.loop_result.approval_required:
        return EXIT_APPROVAL_REQUIRED
    return EXIT_ERROR


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------


def _cmd_status(args: argparse.Namespace) -> int:
    """Show current Ralph workspace / run status."""
    ws = _open_workspace(args.workspace)
    if not ws.exists():
        if args.json:
            _print_json({"workspace": False})
        else:
            print("No Ralph workspace found.")
            print("Start with: fcc-ralph plan <goal>")
        return EXIT_SUCCESS

    task_lib = TaskLibrary(workspace=ws)
    tasks = task_lib.list_tasks()

    by_status: dict[str, int] = {}
    for t in tasks:
        by_status[t.status.value] = by_status.get(t.status.value, 0) + 1

    # Latest run metadata
    run_meta = _load_latest_run_meta(ws)

    # Checkpoints
    cp_store = CheckpointStore(workspace=ws)
    checkpoints: list[dict[str, Any]] = []
    if run_meta:
        run_id = run_meta.get("id", "")
        if run_id:
            checkpoints.extend(
                {
                    "id": cp.id,
                    "iteration": cp.iteration_number,
                    "task_id": cp.task_id,
                    "action": cp.next_action,
                }
                for cp in cp_store.list_for_run(run_id)[:5]
            )

    # Agent profiles
    try:
        p_registry = AgentProfileRegistry(workspace=ws)
        profile_count = len(p_registry.list_profiles())
    except Exception:
        profile_count = 0

    # Reports
    reports = list(ws.list_paths("reports/*.md"))

    if args.json:
        _print_json(
            {
                "workspace": True,
                "task_count": len(tasks),
                "tasks_by_status": by_status,
                "latest_run": run_meta,
                "checkpoints": checkpoints,
                "profile_count": profile_count,
                "report_count": len(reports),
                "loop_state": _detect_loop_state(by_status, run_meta, checkpoints),
            }
        )
        return EXIT_SUCCESS

    print("Ralph Workspace Status")
    print("=====================")
    print(f"  Tasks: {len(tasks)} total")
    for status in ["pending", "approved", "running", "passed", "failed", "needs_fix"]:
        count = by_status.get(status, 0)
        if count:
            print(f"    {status}: {count}")
    print()
    if run_meta:
        print(f"  Latest Run: {run_meta.get('id', 'N/A')}")
        print(f"  Run Status: {run_meta.get('status', 'N/A')}")
    else:
        print("  No runs yet.")
    print()
    if checkpoints:
        latest_cp = checkpoints[0]
        print(f"  Recent checkpoints: {len(checkpoints)}")
        for cp in checkpoints:
            action_tag = ""
            if cp["action"] in ("debug", "escalate"):
                action_tag = " ⚠"
            elif cp["action"] == "retry":
                action_tag = " ↻"
            elif cp["action"] == "approve":
                action_tag = " ✓"
            print(
                f"    {cp['task_id']}  it={cp['iteration']}  "
                f"[{cp['action']}]{action_tag}"
            )
        print(f"  Latest loop action: {latest_cp.get('action', 'N/A')}")
    else:
        print("  No checkpoints yet.")
    print()
    print(f"  Agent profiles available: {profile_count}")
    print(f"  Reports on disk: {len(reports)}")
    print()

    # Next-command hint (enhanced)
    pending = by_status.get("pending", 0)
    approved = by_status.get("approved", 0)
    passed = by_status.get("passed", 0)
    needs_fix = by_status.get("needs_fix", 0)
    if needs_fix:
        print("  Next: fcc-ralph run --loop  (retry tasks needing fix)")
    elif approved and not pending:
        print("  Next: fcc-ralph run  or  fcc-ralph run --loop")
    elif approved and pending:
        print("  Next: fcc-ralph approve <task-id>  then  fcc-ralph run")
    elif pending:
        print("  Next: fcc-ralph review  ->  fcc-ralph approve <task-id>")
    elif not tasks:
        print("  Next: fcc-ralph plan <goal>")
    elif passed:
        print("  Next: fcc-ralph report")

    return EXIT_SUCCESS


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


def _cmd_report(args: argparse.Namespace) -> int:
    """Produce a human-readable report and save it to .fcc-ralph/reports/."""
    ws = _open_workspace(args.workspace)
    if not ws.exists():
        _error("No Ralph workspace found.", EXIT_ERROR)

    task_lib = TaskLibrary(workspace=ws)
    tasks = task_lib.list_tasks()

    by_status: dict[str, int] = {}
    task_details: list[dict[str, Any]] = []
    for t in tasks:
        by_status[t.status.value] = by_status.get(t.status.value, 0) + 1
        task_details.append(
            {
                "id": t.id,
                "title": t.title,
                "status": t.status.value,
                "agent_role": t.agent_role.value,
            }
        )

    cp_store = CheckpointStore(workspace=ws)
    run_meta = _load_latest_run_meta(ws)

    checkpoints: list[dict[str, Any]] = []
    if run_meta:
        run_id = run_meta.get("id", "")
        if run_id:
            checkpoints.extend(
                {
                    "id": cp.id,
                    "iteration": cp.iteration_number,
                    "task_id": cp.task_id,
                    "action": cp.next_action,
                    "score": cp.score,
                    "created_at": cp.created_at,
                }
                for cp in cp_store.list_for_run(run_id)
            )

    # Detect loop state
    loop_state = _detect_loop_state(by_status, run_meta, checkpoints)

    now_str = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")

    # Build markdown report
    lines = [
        "# Ralph Runtime Report",
        "",
        f"**Generated**: {now_str}",
        "",
        "## Summary",
        "",
        f"- Total tasks: {len(tasks)}",
    ]
    for status in ["pending", "approved", "running", "passed", "failed", "needs_fix"]:
        count = by_status.get(status, 0)
        if count:
            lines.append(f"- {status}: {count}")

    if loop_state.get("latest_action"):
        lines.extend(
            [
                "",
                "## Loop State",
                f"- Latest task: {loop_state.get('latest_task', 'N/A')}",
                f"- Latest action: {loop_state.get('latest_action', 'N/A')}",
                f"- Latest iteration: {loop_state.get('latest_iteration', 0)}",
                f"- Needs fix: {loop_state.get('has_needs_fix', False)}",
                f"- Has pending: {loop_state.get('has_pending', False)}",
            ]
        )

    lines.extend(["", "## Tasks"])
    for td in task_details:
        lines.extend(
            [
                "",
                f"### {td['id']} — {td['title']}",
                f"- Status: {td['status']}",
                f"- Role: {td['agent_role']}",
            ]
        )

    if checkpoints:
        lines.extend(["", "## Checkpoints"])
        for cp in checkpoints:
            score_str = ""
            if cp["score"]:
                scores = cp["score"]
                score_str = f"  Score: {scores}"
            lines.append(
                f"- {cp['task_id']} (it={cp['iteration']}): {cp['action']}{score_str}"
            )

    if run_meta:
        lines.extend(["", "## Run Metadata"])
        for key, value in run_meta.items():
            lines.append(f"- {key}: {value}")

    report_content = "\n".join(lines) + "\n"
    report_filename = f"reports/report-{uuid.uuid4().hex[:8]}.md"
    report_path = ws.write_text(report_filename, report_content)

    if args.json:
        _print_json(
            {
                "report_path": str(report_path),
                "task_count": len(tasks),
                "tasks_by_status": by_status,
                "checkpoint_count": len(checkpoints),
            }
        )
    else:
        print(f"Report written to: {report_path}")
        print()
        print("Summary:")
        print(f"  Tasks: {len(tasks)} total")
        for status in ["pending", "approved", "running", "passed", "failed"]:
            count = by_status.get(status, 0)
            if count:
                print(f"    {status}: {count}")
        print(f"  Checkpoints: {len(checkpoints)}")

    return EXIT_SUCCESS


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fcc-ralph",
        description="Ralph Runtime CLI — plan, review, approve, run, and report tasks.",
    )
    parser.add_argument(
        "--workspace",
        default=None,
        help="Project root path (default: current directory)",
    )
    parser.add_argument("--json", action="store_true", help="Output in JSON format")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")

    sub = parser.add_subparsers(dest="command", required=True)

    # --- plan ---
    p = sub.add_parser("plan", help="Create a task plan from a goal")
    p.add_argument("goal", help="Project goal description")
    p.add_argument("--title", default=None, help="Short title for the goal")
    p.add_argument(
        "--constraint", action="append", default=[], help="Constraint (repeatable)"
    )
    p.add_argument("--kpi", action="append", default=[], help="KPI (repeatable)")
    p.add_argument("--yes", action="store_true", help="Skip confirmation prompts")

    # --- review ---
    p = sub.add_parser("review", help="Review tasks and approval status")
    p.add_argument("--task", default=None, help="Show a specific task by ID")

    # --- approve ---
    p = sub.add_parser("approve", help="Approve one task or all pending tasks")
    p.add_argument("task_id", nargs="?", default=None, help="Task ID to approve")
    p.add_argument("--all", action="store_true", help="Approve all pending tasks")

    # --- run ---
    p = sub.add_parser("run", help="Run approved tasks (dry-run by default)")
    p.add_argument("--task", default=None, help="Run a specific task by ID")
    p.add_argument("--loop", action="store_true", help="Enable multi-iteration Ralph loop")
    p.add_argument(
        "--max-iterations",
        type=int,
        default=3,
        help="Max iterations per task in loop mode (default: 3)",
    )
    p.add_argument("--stop-on-debug", action="store_true", default=True, help="Stop on debug action (default: True)")
    p.add_argument("--no-stop-on-debug", action="store_false", dest="stop_on_debug", help="Do not stop on debug action")
    p.add_argument("--stop-on-escalate", action="store_true", default=True, help="Stop on escalate action (default: True)")
    p.add_argument("--no-stop-on-escalate", action="store_false", dest="stop_on_escalate", help="Do not stop on escalate action")
    p.add_argument(
        "--real",
        action="store_true",
        help="Request real execution (requires --allow-real-execution)",
    )
    p.add_argument(
        "--allow-real-execution",
        action="store_true",
        help="Acknowledge and allow real execution",
    )
    p.add_argument(
        "--max-tasks", type=int, default=0, help="Maximum number of tasks to run"
    )
    p.add_argument(
        "--pilot",
        action="store_true",
        help="Run in controlled pilot mode (isolated workspace)",
    )
    p.add_argument(
        "--pilot-workspace",
        default=None,
        help="Path for the pilot workspace (default: %%TEMP%%/vega-ralph-real-pilot)",
    )
    p.add_argument(
        "--allow-dirty-git",
        action="store_true",
        help="Allow real execution even when Git workspace is dirty",
    )
    p.add_argument(
        "--allow-repo-root-execution",
        action="store_true",
        help="Allow real execution on a Git repo root",
    )

    # --- status ---
    sub.add_parser("status", help="Show workspace / run status")

    # --- report ---
    p = sub.add_parser("report", help="Generate a run report")
    p.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        dest="report_format",
        help="Output format (text is always written to file; this controls stdout)",
    )

    return parser


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------


def _run_cli(argv: list[str]) -> int:
    """Parse arguments and dispatch to the appropriate command handler.

    Returns an exit code (never calls ``sys.exit`` directly so the test
    runner can inspect the return value).  Calls to ``_error()``
    (which raises ``SystemExit``) are caught and converted to a return.
    """
    try:
        parser = _build_parser()
        args = parser.parse_args(argv)

        if args.command == "plan":
            return _cmd_plan(args)
        elif args.command == "review":
            return _cmd_review(args)
        elif args.command == "approve":
            if not args.task_id and not args.all:
                _error("Specify a task ID or use --all.", EXIT_INVALID_INPUT)
            return _cmd_approve(args)
        elif args.command == "run":
            if args.loop or args.pilot:
                return _cmd_run_loop(args)
            return _cmd_run(args)
        elif args.command == "status":
            return _cmd_status(args)
        elif args.command == "report":
            return _cmd_report(args)
        else:
            parser.print_help()
            return EXIT_ERROR
    except SystemExit as e:
        code = e.code if isinstance(e.code, int) else EXIT_ERROR
        return code


def main() -> int:
    """Console-script entry point for ``fcc-ralph``."""
    return _run_cli(sys.argv[1:])
