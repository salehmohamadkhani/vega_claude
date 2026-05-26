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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .agent_profiles import AgentProfileRegistry
from .checkpoint import CheckpointStore
from .iteration_runner import IterationRunner
from .memory import MemoryStore
from .models import ProjectGoal, RalphRun, RalphTask, RunStatus, TaskStatus
from .planner import TaskPlanner
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
    """Run approved tasks through the Ralph runtime (dry-run by default)."""
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
            "--real requires --allow-real-execution. "
            "Defaulting to dry-run.",
            EXIT_UNSAFE_REAL,
        )

    approved = [t for t in all_tasks if t.status == TaskStatus.APPROVED]
    pending = [t for t in all_tasks if t.status == TaskStatus.PENDING]

    if not approved:
        if pending:
            _error(
                f"{len(pending)} task(s) are PENDING. "
                f"Approve them first: fcc-ralph approve <task-id>",
                EXIT_APPROVAL_REQUIRED,
            )
        _error("No approved tasks to run.", EXIT_ERROR)

    if args.real and args.allow_real_execution:
        _warn(
            "REAL EXECUTION requested but not available in Phase 6. "
            "Using dry-run."
        )

    tasks_to_run = approved
    if args.task:
        tasks_to_run = [t for t in tasks_to_run if t.id == args.task]
        if not tasks_to_run:
            _error(
                f"Task {args.task!r} is not approved or not found.",
                EXIT_TASK_NOT_FOUND,
            )

    max_tasks = args.max_tasks if args.max_tasks else len(tasks_to_run)
    tasks_to_run = tasks_to_run[:max_tasks]

    # Reconstruct run state from persisted metadata
    run_meta = _load_latest_run_meta(ws)
    if run_meta:
        run = RalphRun(
            id=run_meta.get("id", ""),
            goal_id=run_meta.get("goal_id", ""),
            status=RunStatus.RUNNING,
            tasks=all_tasks,
        )
    else:
        run = RalphRun(status=RunStatus.RUNNING, tasks=all_tasks)

    iteration_runner = IterationRunner(workspace=ws)

    task_results = []
    for task in tasks_to_run:
        task.status = TaskStatus.RUNNING
        task_lib.save_task(task)

        result = iteration_runner.run_iteration(run=run, task=task)
        task_results.append(result)

        if result.passed:
            task.status = TaskStatus.PASSED
        else:
            task.status = TaskStatus.NEEDS_FIX
        task_lib.save_task(task)

    if args.json:
        _print_json(
            {
                "tasks_run": len(task_results),
                "task_results": [
                    {
                        "task_id": r.task_id,
                        "iteration": r.iteration,
                        "execution_mode": r.execution_result.mode.value,
                        "execution_status": r.execution_result.status.value,
                        "quality_gate_action": r.quality_gate_result.arbiter_decision.action.value,
                        "passed": r.passed,
                        "next_action": r.next_action,
                    }
                    for r in task_results
                ],
            }
        )
    else:
        print("Run Results:")
        print(f"  Tasks run: {len(task_results)}")
        print()
        for r in task_results:
            passed_str = "PASSED" if r.passed else "NOT PASSED"
            status_ = r.execution_result.status.value
            action = r.quality_gate_result.arbiter_decision.action.value
            print(f"  {r.task_id}: {passed_str}")
            print(f"    Mode: dry-run  Status: {status_}  Action: {action}")
            if r.failure_reason:
                print(f"    Reason: {r.failure_reason}")

    return EXIT_SUCCESS


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
            for cp in cp_store.list_for_run(run_id)[:5]:
                checkpoints.append(
                    {
                        "id": cp.id,
                        "iteration": cp.iteration_number,
                        "task_id": cp.task_id,
                        "action": cp.next_action,
                    }
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
        print(f"  Recent checkpoints: {len(checkpoints)}")
        for cp in checkpoints:
            print(f"    {cp['task_id']}  it={cp['iteration']}  [{cp['action']}]")
    else:
        print("  No checkpoints yet.")
    print()
    print(f"  Agent profiles available: {profile_count}")
    print(f"  Reports on disk: {len(reports)}")
    print()

    # Next-command hint
    pending = by_status.get("pending", 0)
    approved = by_status.get("approved", 0)
    passed = by_status.get("passed", 0)
    if approved:
        print("  Next: fcc-ralph run")
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
            for cp in cp_store.list_for_run(run_id):
                checkpoints.append(
                    {
                        "id": cp.id,
                        "iteration": cp.iteration_number,
                        "task_id": cp.task_id,
                        "action": cp.next_action,
                        "score": cp.score,
                        "created_at": cp.created_at,
                    }
                )

    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

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
    for status in ["pending", "approved", "running", "passed", "failed"]:
        count = by_status.get(status, 0)
        if count:
            lines.append(f"- {status}: {count}")

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
            lines.append(f"- {cp['task_id']} (it={cp['iteration']}): {cp['action']}{score_str}")

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
    p.add_argument("--constraint", action="append", default=[], help="Constraint (repeatable)")
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
            return _cmd_run(args)
        elif args.command == "status":
            return _cmd_status(args)
        elif args.command == "report":
            return _cmd_report(args)
        else:
            parser.print_help()
            return EXIT_ERROR
    except SystemExit as e:
        code = e.code if e.code is not None else EXIT_ERROR
        return code


def main() -> int:
    """Console-script entry point for ``fcc-ralph``."""
    return _run_cli(sys.argv[1:])
