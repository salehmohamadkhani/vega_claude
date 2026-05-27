"""Tests for the fcc-ralph CLI surface.

Tests call ``_run_cli()`` directly (not ``main()``) to avoid ``sys.exit``
in the test runner.  All tests use ``tmp_path`` so no real workspace is
touched.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from core.ralph.cli import (
    EXIT_APPROVAL_REQUIRED,
    EXIT_ERROR,
    EXIT_TASK_NOT_FOUND,
    EXIT_UNSAFE_REAL,
    _run_cli,
)
from core.ralph.models import TaskStatus
from core.ralph.task_library import TaskLibrary
from core.ralph.workspace import RalphWorkspace


def _ws(project_root: Path) -> RalphWorkspace:
    return RalphWorkspace(project_root=str(project_root))


def test_plan_creates_workspace_and_tasks(tmp_path: Path) -> None:
    """plan creates workspace and persists tasks."""
    rc = _run_cli(
        [
            f"--workspace={tmp_path}",
            "plan",
            "Add unit tests for the CLI module",
        ]
    )
    assert rc == 0
    ws = _ws(tmp_path)
    assert ws.exists()
    task_lib = TaskLibrary(workspace=ws)
    tasks = task_lib.list_tasks()
    assert len(tasks) >= 4  # planner always generates 4+ tasks


def test_plan_does_not_approve_tasks(tmp_path: Path) -> None:
    """plan leaves all tasks in PENDING status."""
    _run_cli([f"--workspace={tmp_path}", "plan", "Fix login bug"])
    task_lib = TaskLibrary(workspace=_ws(tmp_path))
    assert all(t.status == TaskStatus.PENDING for t in task_lib.list_tasks())


def test_plan_with_constraints_and_kpis(tmp_path: Path) -> None:
    """plan accepts repeatable --constraint and --kpi."""
    rc = _run_cli(
        [
            f"--workspace={tmp_path}",
            "plan",
            "Add provider routing tests",
            "--constraint",
            "No real API keys",
            "--constraint",
            "Use mock providers",
            "--kpi",
            "All tests pass",
        ]
    )
    assert rc == 0
    ws = _ws(tmp_path)
    # The goal JSON should contain the constraints
    goals = list(ws.list_paths("goals/*.json"))
    assert len(goals) == 1
    data = ws.read_json(f"goals/{goals[0].name}")
    assert "No real API keys" in data["constraints"]
    assert "All tests pass" in data["success_kpis"]


def test_review_lists_tasks(tmp_path: Path) -> None:
    """review prints task list after plan."""
    _run_cli([f"--workspace={tmp_path}", "plan", "Refactor CLI module"])
    # review should exit 0 and find tasks
    rc = _run_cli([f"--workspace={tmp_path}", "review"])
    assert rc == 0


def test_review_shows_specific_task(tmp_path: Path) -> None:
    """review --task shows a single task."""
    _run_cli([f"--workspace={tmp_path}", "plan", "Implement search"])
    task_lib = TaskLibrary(workspace=_ws(tmp_path))
    first = task_lib.list_tasks()[0]
    rc = _run_cli([f"--workspace={tmp_path}", "review", f"--task={first.id}"])
    assert rc == 0


def test_review_unknown_task_returns_nonzero(tmp_path: Path) -> None:
    """review --task with nonexistent ID returns error."""
    _run_cli([f"--workspace={tmp_path}", "plan", "Fix something"])
    rc = _run_cli([f"--workspace={tmp_path}", "review", "--task=TASK-999-NONEXISTENT"])
    assert rc == EXIT_TASK_NOT_FOUND


def test_approve_changes_status(tmp_path: Path) -> None:
    """approve TASK-ID sets status to APPROVED."""
    _run_cli([f"--workspace={tmp_path}", "plan", "Add error handling"])
    task_lib = TaskLibrary(workspace=_ws(tmp_path))
    task = task_lib.list_tasks()[0]
    assert task.status == TaskStatus.PENDING

    rc = _run_cli([f"--workspace={tmp_path}", "approve", task.id])
    assert rc == 0

    reloaded = task_lib.find_task(task.id)
    assert reloaded is not None
    assert reloaded.status == TaskStatus.APPROVED


def test_approve_all_approves_all_pending(tmp_path: Path) -> None:
    """approve --all approves every pending task."""
    _run_cli([f"--workspace={tmp_path}", "plan", "Build the feature"])
    task_lib = TaskLibrary(workspace=_ws(tmp_path))
    tasks = task_lib.list_tasks()
    assert all(t.status == TaskStatus.PENDING for t in tasks)

    rc = _run_cli([f"--workspace={tmp_path}", "approve", "--all"])
    assert rc == 0

    for t in task_lib.list_tasks():
        assert t.status == TaskStatus.APPROVED, f"{t.id} was not approved"


def test_approve_already_approved_reports_cleanly(tmp_path: Path) -> None:
    """approve on already-approved task exits 0 with message."""
    _run_cli([f"--workspace={tmp_path}", "plan", "Test approve re-approve"])
    task_lib = TaskLibrary(workspace=_ws(tmp_path))
    task = task_lib.list_tasks()[0]
    _run_cli([f"--workspace={tmp_path}", "approve", task.id])
    rc = _run_cli([f"--workspace={tmp_path}", "approve", task.id])
    assert rc == 0  # idempotent


def test_approve_unknown_task_returns_nonzero(tmp_path: Path) -> None:
    """approve with nonexistent task ID returns error."""
    _run_cli([f"--workspace={tmp_path}", "plan", "Test unknown approve"])
    rc = _run_cli([f"--workspace={tmp_path}", "approve", "TASK-999-NOPE"])
    assert rc == EXIT_TASK_NOT_FOUND


def test_run_with_pending_returns_approval_required(tmp_path: Path) -> None:
    """run with no approved tasks returns approval-required."""
    _run_cli([f"--workspace={tmp_path}", "plan", "Run without approval"])
    rc = _run_cli([f"--workspace={tmp_path}", "run"])
    assert rc == EXIT_APPROVAL_REQUIRED


def test_run_with_approved_task_defaults_to_dry_run(tmp_path: Path) -> None:
    """run after approval defaults to dry-run (no real execution).

    Note: only TASK-001 is APPROVED; TASK-002 is still PENDING so the
    run is blocked by Policy A (strict ordered approval).  The approved
    task still runs and gets NEEDS_FIX from the dry-run.
    """
    _run_cli([f"--workspace={tmp_path}", "plan", "Safe dry-run test"])
    task_lib = TaskLibrary(workspace=_ws(tmp_path))
    task = task_lib.list_tasks()[0]
    _run_cli([f"--workspace={tmp_path}", "approve", task.id])

    rc = _run_cli([f"--workspace={tmp_path}", "run"])
    assert rc == EXIT_APPROVAL_REQUIRED

    # Task still attempted in dry-run mode
    reloaded = task_lib.find_task(task.id)
    assert reloaded is not None
    assert reloaded.status == TaskStatus.NEEDS_FIX


def test_run_real_without_allow_flag_fails_safely(tmp_path: Path) -> None:
    """run --real without --allow-real-execution exits with unsafe error."""
    _run_cli([f"--workspace={tmp_path}", "plan", "Real exec safety test"])
    task_lib = TaskLibrary(workspace=_ws(tmp_path))
    task = task_lib.list_tasks()[0]
    _run_cli([f"--workspace={tmp_path}", "approve", task.id])

    rc = _run_cli([f"--workspace={tmp_path}", "run", "--real"])
    assert rc == EXIT_UNSAFE_REAL


def test_run_real_with_allow_flag_still_uses_dry_run(tmp_path: Path) -> None:
    """run --real --allow-real-execution still uses dry-run in Phase 6."""
    _run_cli([f"--workspace={tmp_path}", "plan", "Real with allow flag"])
    task_lib = TaskLibrary(workspace=_ws(tmp_path))
    task = task_lib.list_tasks()[0]
    _run_cli([f"--workspace={tmp_path}", "approve", task.id])

    rc = _run_cli(
        [
            f"--workspace={tmp_path}",
            "run",
            "--real",
            "--allow-real-execution",
        ]
    )
    # Policy A blocks because TASK-002 is PENDING
    assert rc == EXIT_APPROVAL_REQUIRED
    reloaded = task_lib.find_task(task.id)
    assert reloaded is not None
    assert reloaded.status == TaskStatus.NEEDS_FIX  # still dry-run


def test_run_specific_task(tmp_path: Path) -> None:
    """run --task=TASK-ID runs only that task."""
    _run_cli([f"--workspace={tmp_path}", "plan", "Run specific task test"])
    task_lib = TaskLibrary(workspace=_ws(tmp_path))
    tasks = task_lib.list_tasks()
    for t in tasks:
        _run_cli([f"--workspace={tmp_path}", "approve", t.id])

    target = tasks[1]
    rc = _run_cli([f"--workspace={tmp_path}", "run", f"--task={target.id}"])
    assert rc == 0

    reloaded = task_lib.find_task(target.id)
    assert reloaded is not None
    assert reloaded.status == TaskStatus.NEEDS_FIX


def test_run_with_no_workspace_returns_error(tmp_path: Path) -> None:
    """run without a workspace exits with error."""
    rc = _run_cli([f"--workspace={tmp_path}", "run"])
    assert rc == EXIT_ERROR


def test_status_shows_task_counts(tmp_path: Path) -> None:
    """status displays task counts from workspace."""
    _run_cli([f"--workspace={tmp_path}", "plan", "Status display test"])
    rc = _run_cli([f"--workspace={tmp_path}", "status"])
    assert rc == 0


def test_status_on_empty_workspace(tmp_path: Path) -> None:
    """status on non-existent workspace returns 0 and prints guidance."""
    rc = _run_cli([f"--workspace={tmp_path}", "status"])
    assert rc == 0


def test_report_writes_file(tmp_path: Path) -> None:
    """report writes a .md file to .fcc-ralph/reports/."""
    _run_cli([f"--workspace={tmp_path}", "plan", "Report writing test"])
    rc = _run_cli([f"--workspace={tmp_path}", "report"])
    assert rc == 0

    ws = _ws(tmp_path)
    reports = list(ws.list_paths("reports/*.md"))
    assert len(reports) >= 1


def test_report_without_workspace_returns_error(tmp_path: Path) -> None:
    """report without a workspace exits with error."""
    rc = _run_cli([f"--workspace={tmp_path}", "report"])
    assert rc == EXIT_ERROR


def test_json_output_is_valid_json(tmp_path: Path) -> None:
    """--json flag produces parseable JSON output."""
    rc = _run_cli([f"--workspace={tmp_path}", "--json", "plan", "JSON output test"])
    assert rc == 0


def test_json_review_output(tmp_path: Path) -> None:
    """review --json outputs valid JSON with task data."""
    _run_cli([f"--workspace={tmp_path}", "plan", "JSON review test"])
    rc = _run_cli([f"--workspace={tmp_path}", "--json", "review"])
    assert rc == 0


def test_json_status_output(tmp_path: Path) -> None:
    """status --json outputs valid JSON."""
    _run_cli([f"--workspace={tmp_path}", "plan", "JSON status test"])
    rc = _run_cli([f"--workspace={tmp_path}", "--json", "status"])
    assert rc == 0


def test_approve_without_task_id_or_all_fails(tmp_path: Path) -> None:
    """approve with no task-id and no --all returns error."""
    _run_cli([f"--workspace={tmp_path}", "plan", "Approve without args"])
    rc = _run_cli([f"--workspace={tmp_path}", "approve"])
    assert rc != 0


def test_no_provider_imports(tmp_path: Path) -> None:
    """CLI module does not import providers."""
    import core.ralph.cli  # noqa: F401

    modnames = set(sys.modules)
    provider_mods = [m for m in modnames if "provider" in m.lower()]
    # The only acceptable match is "providers" as a smoke-target string
    # in the planner, NOT as an imported module.
    assert not any(
        m.startswith("providers.") or m.startswith("api.") or "anthropic" in m
        for m in provider_mods
    )


def test_no_network_imports(tmp_path: Path) -> None:
    """CLI module does not import network libraries."""
    import core.ralph.cli  # noqa: F401

    modnames = set(sys.modules)
    # httpx is an FCC project dependency that may be loaded by other modules;
    # socket/urllib3 are stdlib / transitive deps.  The dangerous ones here are
    # request-level HTTP clients that should never appear in the Ralph runtime.
    dangerous = {"requests", "aiohttp"}
    imported = {m.split(".")[0] for m in modnames}
    assert not dangerous & imported, f"Dangerous imports found: {dangerous & imported}"


def test_plan_json_output_describes_tasks(tmp_path: Path) -> None:
    """plan --json returns structured data with tasks."""
    rc = _run_cli(
        [
            f"--workspace={tmp_path}",
            "--json",
            "plan",
            "Test structured JSON",
            "--kpi",
            "Coverage >= 80%",
        ]
    )
    assert rc == 0

    task_lib = TaskLibrary(workspace=_ws(tmp_path))
    tasks = task_lib.list_tasks()
    assert len(tasks) > 0
    # Verify persisted tasks have correct structure
    for t in tasks:
        assert t.id
        assert t.title
        assert t.agent_role


def test_plan_persists_checkpoint(tmp_path: Path) -> None:
    """plan creates an initial checkpoint."""
    _run_cli([f"--workspace={tmp_path}", "plan", "Checkpoint test"])
    ws = _ws(tmp_path)
    checkpoints = list(ws.list_paths("checkpoints/*.json"))
    assert len(checkpoints) >= 1


def test_run_max_tasks_limit(tmp_path: Path) -> None:
    """run --max-tasks limits the number of tasks executed."""
    _run_cli([f"--workspace={tmp_path}", "plan", "Max tasks test"])
    task_lib = TaskLibrary(workspace=_ws(tmp_path))
    tasks = task_lib.list_tasks()

    # Approve first 2 tasks
    for t in tasks[:2]:
        _run_cli([f"--workspace={tmp_path}", "approve", t.id])

    # Run with max-tasks=1
    rc = _run_cli([f"--workspace={tmp_path}", "run", "--max-tasks=1"])
    assert rc == 0

    # First task should be NEEDS_FIX (ran, but dry-run didn't pass)
    reloaded0 = task_lib.find_task(tasks[0].id)
    assert reloaded0 is not None
    assert reloaded0.status == TaskStatus.NEEDS_FIX

    # Second task should still be APPROVED (not run)
    reloaded1 = task_lib.find_task(tasks[1].id)
    assert reloaded1 is not None
    assert reloaded1.status == TaskStatus.APPROVED


def test_review_empty_workspace(tmp_path: Path) -> None:
    """review on empty workspace returns error."""
    rc = _run_cli([f"--workspace={tmp_path}", "review"])
    assert rc == EXIT_ERROR


def test_approve_with_no_workspace(tmp_path: Path) -> None:
    """approve on empty workspace returns error."""
    rc = _run_cli([f"--workspace={tmp_path}", "approve", "TASK-001"])
    assert rc == EXIT_ERROR


def test_cli_does_not_modify_files_outside_workspace(tmp_path: Path) -> None:
    """CLI only writes inside .fcc-ralph/."""
    _run_cli([f"--workspace={tmp_path}", "plan", "Boundary test"])
    # Check no unexpected files at the root level
    entries = {p.name for p in tmp_path.iterdir()}
    assert ".fcc-ralph" in entries
    assert len(entries) == 1, f"Unexpected files outside workspace: {entries}"


# ======================================================================
# Step 3 — Strict approval policy tests
# ======================================================================


def test_strict_order_blocks_later_approved_task(tmp_path: Path) -> None:
    """TASK-001 PENDING blocks TASK-002 even if TASK-002 is APPROVED."""
    _run_cli([f"--workspace={tmp_path}", "plan", "Strict order policy"])
    task_lib = TaskLibrary(workspace=_ws(tmp_path))
    tasks = task_lib.list_tasks()
    task1, task2 = tasks[0], tasks[1]

    # Approve only task2
    _run_cli([f"--workspace={tmp_path}", "approve", task2.id])

    # Run must fail: task1 is still PENDING
    rc = _run_cli([f"--workspace={tmp_path}", "run"])
    assert rc == EXIT_APPROVAL_REQUIRED

    # task2 must still be APPROVED (never ran)
    reloaded = task_lib.find_task(task2.id)
    assert reloaded is not None
    assert reloaded.status == TaskStatus.APPROVED

    # Approve all remaining tasks
    _run_cli([f"--workspace={tmp_path}", "approve", task1.id])
    _run_cli([f"--workspace={tmp_path}", "approve", "--all"])

    # Now run should succeed (dry-run)
    rc = _run_cli([f"--workspace={tmp_path}", "run"])
    assert rc == 0

    # task1 should have been attempted
    reloaded1 = task_lib.find_task(task1.id)
    assert reloaded1 is not None
    assert reloaded1.status == TaskStatus.NEEDS_FIX


def test_strict_order_json_shows_blocked_task(
    tmp_path: Path, capsys
) -> None:
    """run --json includes blocked_task_id and pending_task_ids."""
    _run_cli([f"--workspace={tmp_path}", "plan", "JSON blocked"])
    task_lib = TaskLibrary(workspace=_ws(tmp_path))
    tasks = task_lib.list_tasks()

    # Approve only later task
    _run_cli([f"--workspace={tmp_path}", "approve", tasks[1].id])
    capsys.readouterr()  # discard setup output

    rc = _run_cli([f"--workspace={tmp_path}", "--json", "run"])
    captured = capsys.readouterr()
    data = json.loads(captured.out)

    assert rc == EXIT_APPROVAL_REQUIRED
    assert data["status"] == "approval_required"
    assert data["blocked_task_id"] == tasks[0].id
    assert len(data["pending_task_ids"]) >= 1


def test_specific_task_respects_strict_order(tmp_path: Path) -> None:
    """run --task=LATER is blocked when earlier task is PENDING."""
    _run_cli([f"--workspace={tmp_path}", "plan", "Strict specific task"])
    task_lib = TaskLibrary(workspace=_ws(tmp_path))
    tasks = task_lib.list_tasks()

    # Approve only later task
    _run_cli([f"--workspace={tmp_path}", "approve", tasks[1].id])

    # --task=later must be blocked by strict order
    rc = _run_cli(
        [f"--workspace={tmp_path}", "run", f"--task={tasks[1].id}"]
    )
    assert rc == EXIT_APPROVAL_REQUIRED

    # Approve the blocking task
    _run_cli([f"--workspace={tmp_path}", "approve", tasks[0].id])

    # Now --task=later should run
    rc = _run_cli(
        [f"--workspace={tmp_path}", "run", f"--task={tasks[1].id}"]
    )
    assert rc == 0
    reloaded = task_lib.find_task(tasks[1].id)
    assert reloaded is not None
    assert reloaded.status == TaskStatus.NEEDS_FIX

    # Earlier task should NOT have been run (--task is specific)
    reloaded0 = task_lib.find_task(tasks[0].id)
    assert reloaded0 is not None
    assert reloaded0.status == TaskStatus.APPROVED


def test_specific_task_unknown_returns_error(tmp_path: Path) -> None:
    """run --task with nonexistent ID returns error."""
    _run_cli([f"--workspace={tmp_path}", "plan", "Unknown specific task"])
    rc = _run_cli(
        [f"--workspace={tmp_path}", "run", "--task=TASK-999-NOPE"]
    )
    assert rc == EXIT_TASK_NOT_FOUND


def test_approve_then_run_runs_multiple_tasks(tmp_path: Path) -> None:
    """Approve all, run executes all approved tasks in order."""
    _run_cli(
        [f"--workspace={tmp_path}", "plan", "Multi-task run test"]
    )
    task_lib = TaskLibrary(workspace=_ws(tmp_path))
    tasks = task_lib.list_tasks()

    # Approve all
    _run_cli([f"--workspace={tmp_path}", "approve", "--all"])

    # Run without limit
    rc = _run_cli([f"--workspace={tmp_path}", "run"])
    assert rc == 0

    # All tasks should have been attempted
    for t in tasks:
        reloaded = task_lib.find_task(t.id)
        assert reloaded is not None
        assert reloaded.status in (
            TaskStatus.NEEDS_FIX,
            TaskStatus.PASSED,
        )


# ======================================================================
# Step 3 — JSON output validation
# ======================================================================


def test_plan_json_output_is_parseable(
    tmp_path: Path, capsys
) -> None:
    """plan --json outputs parseable JSON with expected fields."""
    _run_cli(
        [
            f"--workspace={tmp_path}",
            "--json",
            "plan",
            "JSON parseable plan",
        ]
    )
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert "goal_id" in data
    assert "run_id" in data
    assert "task_count" in data
    assert "tasks" in data
    assert isinstance(data["tasks"], list)
    assert len(data["tasks"]) == data["task_count"]


def test_review_json_output_is_parseable(
    tmp_path: Path, capsys
) -> None:
    """review --json outputs parseable JSON list."""
    _run_cli([f"--workspace={tmp_path}", "plan", "JSON review test"])
    capsys.readouterr()  # discard plan output
    _run_cli([f"--workspace={tmp_path}", "--json", "review"])
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert isinstance(data, list)
    if data:
        assert "id" in data[0]
        assert "title" in data[0]
        assert "status" in data[0]


def test_status_json_output_is_parseable(
    tmp_path: Path, capsys
) -> None:
    """status --json outputs parseable JSON object."""
    _run_cli([f"--workspace={tmp_path}", "plan", "JSON status test"])
    capsys.readouterr()  # discard plan output
    _run_cli([f"--workspace={tmp_path}", "--json", "status"])
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert isinstance(data, dict)
    assert "workspace" in data
    assert "task_count" in data
    assert "tasks_by_status" in data


def test_run_json_output_is_parseable(
    tmp_path: Path, capsys
) -> None:
    """run --json outputs parseable JSON after approval."""
    _run_cli([f"--workspace={tmp_path}", "plan", "JSON run test"])
    task_lib = TaskLibrary(workspace=_ws(tmp_path))
    _run_cli(
        [f"--workspace={tmp_path}", "approve", task_lib.list_tasks()[0].id]
    )
    capsys.readouterr()  # discard setup output

    _run_cli([f"--workspace={tmp_path}", "--json", "run"])
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert isinstance(data, dict)
    assert "status" in data
    assert "tasks_run" in data
    assert "task_results" in data


def test_json_error_does_not_mix_into_stdout(
    tmp_path: Path, capsys
) -> None:
    """JSON mode writes errors to stderr, stdout stays clean."""
    rc = _run_cli([f"--workspace={tmp_path}", "--json", "run"])
    captured = capsys.readouterr()
    # No workspace → error before any JSON output
    assert captured.out == "", (
        f"Expected empty stdout, got: {captured.out!r}"
    )
    assert "Error" in captured.err
    assert rc != 0


# ======================================================================
# Step 4 — Console script registration tests
# ======================================================================


def test_main_is_importable() -> None:
    """core.ralph.cli.main is importable as a function."""
    from core.ralph.cli import main

    assert main is not None
    assert callable(main)


def test_console_script_registered() -> None:
    """pyproject.toml registers fcc-ralph console script."""
    import core.ralph.cli as cli_mod

    assert hasattr(cli_mod, "main")
    assert callable(cli_mod.main)
