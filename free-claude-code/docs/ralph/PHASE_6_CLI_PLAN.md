# Phase 6 Plan — CLI Surface for Ralph Runtime

> **Date**: 2026-05-26
> **Status**: Implemented — see `PHASE_6_REPORT.md` for results
> **Phase 6 Goal**: Implement `fcc-ralph` CLI commands — plan, review, approve, run, status, report
>
> **Phase 6.1 Update (2026-05-27)**: `fcc-ralph run` now delegates to
> `RunExecutor.run_until_blocked()` instead of using `IterationRunner`
> directly. Strict ordered approval (Policy A) is enforced. See
> `PHASE_6_1_CLI_HARDENING_REPORT.md` for details.

---

## Summary

Phase 6 builds a CLI surface for the Ralph Runtime following the FCC CLI pattern (`fcc-<name> = "module:function"` in `pyproject.toml`). It exposes six subcommands that let users interact with the Ralph loop from the terminal without requiring Admin UI or Python API access.

## CLI Pattern (FCC Convention)

From `pyproject.toml`:

```toml
[project.scripts]
fcc-server = "cli.entrypoints:serve"
free-claude-code = "cli.entrypoints:serve"
fcc-init = "cli.entrypoints:init"
fcc-claude = "cli.entrypoints:launch_claude"
```

Each entry maps a shell command to a Python function. Hatchling generates console scripts during `pip install`. Phase 6 adds:

```toml
fcc-ralph = "core.ralph.cli:main"
```

## Module Structure

```
core/ralph/cli.py            — CLI entry point, argparse subcommand routing
core/ralph/cli_commands.py   — Subcommand handlers (thin wrappers over runtime)
```

No new `cli/` files — the Ralph CLI lives inside `core/ralph/` because:
- It is an **internal surface** for a core runtime, not an FCC platform CLI
- It avoids cross-package dependency from `cli/` → `core/ralph/`
- All imports stay within `core.ralph.*` and stdlib

## Command Reference

### `fcc-ralph plan <goal>`

| Aspect | Detail |
|---|---|
| **Purpose** | Create a task plan from a project goal |
| **Implies** | `goal` → `TaskPlanner.plan()` → prints task list summary |
| **Safety** | Read-only — no state mutation, no execution |
| **Output** | Task IDs, titles, roles, task count |

### `fcc-ralph review [run-id]`

| Aspect | Detail |
|---|---|
| **Purpose** | Display pending tasks for a run, or list all runs |
| **Implies** | `RunTable.list_active_entries()` or `CheckpointStore.latest_for_run()` |
| **Safety** | Read-only — no state mutation |
| **Output** | Run status, task table (ID, status, title, score), pending count |

### `fcc-ralph approve <task-id> [--run-id]`

| Aspect | Detail |
|---|---|
| **Purpose** | Approve a specific PENDING task for execution |
| **Implies** | `RunLifecycle.approve_task(task_id)` |
| **Safety** | Mutates task status (PENDING → APPROVED) — no execution |
| **Output** | Confirmation of approval, updated task status |

### `fcc-ralph run [run-id] [--task-id] [--real] [--max-tasks N]`

| Aspect | Detail |
|---|---|
| **Purpose** | Execute tasks (dry-run by default) |
| **Implies** | `RunExecutor.run_until_blocked()` — enforces Policy A strict ordered approval |
| **Safety** | **Default: dry-run** — `ExecutionMode.DRY_RUN`. `--real` flag required for actual execution |
| **Output** | Iteration results: passed/failed, status, blocked task, arbiter action |

### `fcc-ralph status [run-id]`

| Aspect | Detail |
|---|---|
| **Purpose** | Show run status, current task, iteration progress |
| **Implies** | `RunTable.get_entries_for_run()`, `CheckpointStore.latest_for_run()` |
| **Safety** | Read-only |
| **Output** | Run status, current task, iteration count, completion %, scores |

### `fcc-ralph report [run-id] [--format text|json]`

| Aspect | Detail |
|---|---|
| **Purpose** | Generate a structured run report |
| **Implies** | Gathers checkpoints, scoring, quality gate results |
| **Safety** | Read-only |
| **Output** | Full report with task results, scores, verification outcomes |

## Implementation Steps

### Step 1: Create `core/ralph/cli.py`

Entry point with `main()` function. Uses `argparse` (stdlib, no extra dependency) for subcommand routing:

```python
def main() -> None:
    parser = argparse.ArgumentParser(prog="fcc-ralph")
    sub = parser.add_subparsers(dest="command", required=True)

    # plan — read-only, creates task plan from goal
    plan_p = sub.add_parser("plan", help="Create a task plan from a goal")
    plan_p.add_argument("goal", help="Project goal description")

    # review — read-only, display pending tasks
    review_p = sub.add_parser("review", help="Review pending tasks")
    review_p.add_argument("run_id", nargs="?", default=None)

    # approve — mutates task status, no execution
    approve_p = sub.add_parser("approve", help="Approve a task for execution")
    approve_p.add_argument("task_id", help="Task ID to approve")
    approve_p.add_argument("--run-id", default=None, help="Run ID (optional)")

    # run — dry-run by default, --real for actual execution
    run_p = sub.add_parser("run", help="Run tasks (dry-run by default)")
    run_p.add_argument("run_id", nargs="?", default=None)
    run_p.add_argument("--task-id", default=None, help="Single task to run")
    run_p.add_argument("--real", action="store_true", help="Enable real execution")
    run_p.add_argument("--max-tasks", type=int, default=0, help="Max tasks to run")

    # status — read-only
    status_p = sub.add_parser("status", help="Show run status")
    status_p.add_argument("run_id", nargs="?", default=None)

    # report — read-only
    report_p = sub.add_parser("report", help="Generate run report")
    report_p.add_argument("run_id", nargs="?", default=None)
    report_p.add_argument("--format", choices=["text", "json"], default="text")

    args = parser.parse_args()
    _dispatch(args)
```

### Step 2: Create `core/ralph/cli_commands.py`

Thin handler functions that construct runtime objects and print results. Each handler should:

1. Construct or load the required runtime components (RunTable, RunLifecycle, RunExecutor, etc.)
2. Call the component method
3. Format and print the result

Example handler pattern:

```python
def _cmd_plan(args: argparse.Namespace) -> None:
    planner = TaskPlanner()
    goal = ProjectGoal(description=args.goal)
    task_plan = planner.plan(goal)
    print(f"Plan: {task_plan.goal.title}")
    for t in task_plan.tasks:
        print(f"  {t.id}: [{t.assigned_role}] {t.title}")
```

### Step 3: Register in `pyproject.toml`

Add to `[project.scripts]`:

```toml
fcc-ralph = "core.ralph.cli:main"
```

No other changes needed — `core/` is already in the wheel packages list:

```toml
[tool.hatch.build.targets.wheel]
packages = ["api", "cli", "config", "core", "messaging", "providers"]
```

### Step 4: Test

| Test File | What It Covers |
|---|---|
| `tests/core/ralph/test_cli.py` | Subcommand parsing, argument validation, help output |
| `tests/core/ralph/test_cli_commands.py` | Handler integration with mocked runtime components |

Key test scenarios:
- `fcc-ralph plan "fix login bug"` produces a task plan
- `fcc-ralph run` defaults to dry-run
- `fcc-ralph run --real` requires explicit flag
- `fcc-ralph approve TASK-001` calls `RunLifecycle.approve_task`
- `fcc-ralph status` returns readable output for an active run
- Unknown subcommand shows help
- Missing required arguments error gracefully

## Safety Properties (Pre-Verified)

| Property | Status | Phase 5.7 Reference |
|---|---|---|
| Default dry-run | ✅ | `ExecutionConfig(dry_run=True, allow_real_execution=False)` |
| Real execution requires `--real` | ✅ | CLI pass-through to `ExecutionMode.REAL` |
| Command allowlist enforced | ✅ | `_is_command_allowed()` with basename matching |
| No provider/API key ownership | ✅ | Zero provider imports in `core/ralph/` |
| No shell injection | ✅ | `subprocess.run(shell=False)` throughout |
| Output truncation | ✅ | `max_output_chars` caps stdout/stderr |
| Timeout enforcement | ✅ | `subprocess.run(timeout=...)` |
| Checkpoint isolation | ✅ | All state under `.fcc-ralph/` |

## Risks and Mitigations

| Risk | Mitigation |
|---|---|
| **Subcommand scope creep** | Keep handlers thin — one operation per command, no interactive mode |
| **argparse limitations** | If subcommand nesting grows, migrate to `click` or `typer` (Phase 6+) |
| **User runs `--real` accidentally** | Confirmation prompt before real execution; double opt-in via CLI flag + config gate |
| **Windows path issues** | Already handled by Phase 5.6 allowlist hardening (`list[str]` argv, no quoting) |

## Out of Scope (Phase 6)

| Feature | Reason |
|---|---|
| Interactive/TUI mode | CLI should be scriptable — no curses/rich dependency |
| Admin UI dashboard | Phase 7 — optional, post-CLI |
| Full async Ralph Loop | Phase 8 — connects RunExecutor to FCC proxy |
| Playwright KPI verification | Phase 9 — browser-based acceptance testing |
| Provider routing / API keys | FCC-owned — Ralph Runtime never manages these |

---

*See `PHASE_5_7_CLI_FIRST_AUDIT.md` for the execution contract audit that confirms CLI safety.*
