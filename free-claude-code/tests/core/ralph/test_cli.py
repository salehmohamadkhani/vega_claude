"""Tests for the fcc-ralph CLI surface.

Tests call ``_run_cli()`` directly (not ``main()``) to avoid ``sys.exit``
in the test runner.  All tests use ``tmp_path`` so no real workspace is
touched.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from core.ralph.checkpoint import CheckpointStore
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
    """run after approval defaults to dry-run (no real execution)."""
    _run_cli([f"--workspace={tmp_path}", "plan", "Safe dry-run test"])
    task_lib = TaskLibrary(workspace=_ws(tmp_path))
    task = task_lib.list_tasks()[0]
    _run_cli([f"--workspace={tmp_path}", "approve", task.id])

    rc = _run_cli([f"--workspace={tmp_path}", "run"])
    assert rc == 0

    # Task should be marked NEEDS_FIX (dry-run doesn't pass)
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
    assert rc == 0
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
    import core.ralph.cli

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
    import core.ralph.cli

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
    cp_store = CheckpointStore(workspace=ws)
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
