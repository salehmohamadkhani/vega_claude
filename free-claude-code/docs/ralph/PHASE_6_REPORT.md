# Phase 6 Report — `fcc-ralph` CLI Surface

> **Date**: 2026-05-26
> **Status**: Complete — 32 tests passing, all safety greps clean

---

## Summary

Phase 6 implemented the first usable FCC-style CLI surface for the Ralph
Runtime: `fcc-ralph`.  Six subcommands expose the runtime services (planner,
task library, iteration runner, checkpoint store) from the terminal without
requiring Admin UI or Python API access.

### What Was Built

| Command | Handler | Purpose |
|---|---|---|
| `fcc-ralph plan <goal>` | `_cmd_plan` | Create a project goal, generate tasks, persist to workspace |
| `fcc-ralph review` | `_cmd_review` | Show tasks and their approval status |
| `fcc-ralph approve <task-id> \| --all` | `_cmd_approve` | Approve one or all pending tasks |
| `fcc-ralph run` | `_cmd_run` | Run approved tasks (dry-run by default) |
| `fcc-ralph status` | `_cmd_status` | Show workspace / run status with checkpoints and profiles |
| `fcc-ralph report` | `_cmd_report` | Generate a structured markdown report |

All commands support `--json` for machine-readable output and `--workspace` to
point at a specific project root.

### Files Created

| File | Lines | Purpose |
|---|---|---|
| `core/ralph/cli.py` | 723 | CLI entry point, argparse subcommand routing, 6 command handlers, output helpers, exit codes |
| `tests/core/ralph/test_cli.py` | 390 | 32 tests covering all commands, error paths, JSON output, safety properties |

### Files Modified

| File | Change |
|---|---|
| `pyproject.toml` | Added `fcc-ralph = "core.ralph.cli:main"` to `[project.scripts]` |

---

## Safety Behaviour

| Property | Mechanism | Status |
|---|---|---|
| Dry-run by default | `IterationRunnerConfig(execution_mode=DRY_RUN)` — no subprocess calls | ✅ |
| Pending tasks require approval | `run` checks `TaskStatus.APPROVED`; exits `EXIT_APPROVAL_REQUIRED` (4) if none approved | ✅ |
| Real execution requires double opt-in | `--real` + `--allow-real-execution`; exits `EXIT_UNSAFE_REAL` (5) if missing | ✅ |
| No provider/API imports | Zero imports from `providers/`, `api/`, or `anthropic` in CLI module | ✅ |
| No network libraries | CLI does not import `requests`, `aiohttp` | ✅ |
| Workspace isolation | All state written under `.fcc-ralph/`; CLI tests verify no files outside workspace | ✅ |
| `shell=True` not used | CLI never constructs subprocess calls; existing IterationRunner uses `shell=False` | ✅ |

### Exit Codes

| Code | Constant | When Returned |
|---|---|---|
| 0 | `EXIT_SUCCESS` | Operation completed successfully |
| 1 | `EXIT_ERROR` | Workspace not found, no tasks, general error |
| 2 | `EXIT_INVALID_INPUT` | Missing required arguments (e.g. approve without task-id) |
| 3 | `EXIT_TASK_NOT_FOUND` | Task ID does not exist in workspace |
| 4 | `EXIT_APPROVAL_REQUIRED` | All tasks are PENDING, none approved |
| 5 | `EXIT_UNSAFE_REAL` | `--real` used without `--allow-real-execution` |

---

## Test Results

```
32 passed in 3.94s
```

### Test Coverage by Category

| Category | Tests | Key Assertions |
|---|---|---|
| **plan** | 5 | Workspace creation, no auto-approve, constraints/KPIs, JSON output, checkpoint persistence |
| **review** | 4 | Task listing, specific task, unknown task error, empty workspace error |
| **approve** | 6 | Status change, `--all`, idempotent, unknown task error, no-arg error, no-workspace error |
| **run** | 6 | Pending → approval-required, dry-run, `--real` safety, `--real --allow`, specific task, max-tasks limit |
| **status** | 3 | Task counts, empty workspace, JSON output |
| **report** | 2 | File written to `.fcc-ralph/reports/`, no-workspace error |
| **JSON** | 3 | `plan --json`, `review --json`, `status --json` all produce valid JSON |
| **Safety** | 3 | No provider imports, no network imports, no files outside workspace |

### Safety Grep Results

| Check | Result |
|---|---|
| `shell=True` in `cli.py` | 0 matches ✅ |
| Provider imports | 0 matches ✅ |
| Admin UI / Playwright references | 0 matches ✅ |
| Network library calls (`httpx`, `requests`, `aiohttp`) | 0 matches ✅ |
| AST-level subprocess call audit | Clean ✅ |

---

## Architecture

### Data Flow

```
User (terminal)
    │
    ▼
fcc-ralph <command> [options]
    │
    ▼
core/ralph/cli.py
    │  _run_cli() → parse → dispatch
    │
    ├── plan    → TaskPlanner.plan() → RunLifecycle.prepare_run() → workspace
    ├── review  → TaskLibrary.list_tasks() / find_task()
    ├── approve → TaskLibrary.save_task()  (status → APPROVED)
    ├── run     → IterationRunner.run_iteration()  (dry-run by default)
    ├── status  → TaskLibrary + CheckpointStore + AgentProfileRegistry
    └── report  → TaskLibrary + CheckpointStore → markdown file
```

### CLI as Thin Surface

The CLI does **not** reimplement runtime logic. Each handler is a thin wrapper
that calls existing `core.ralph` services. The CLI module:
- Has zero imports from `providers/`, `api/`, `messaging/`, or Admin UI
- Uses only stdlib `argparse` (no `click`/`typer` dependency)
- All execution safety is delegated to `IterationRunner` / `ExecutionConfig`

### Key Design Decisions

1. **`_run_cli()` catches `SystemExit`** — Rather than changing every
   `_error()` call to return instead of `sys.exit()`, `_run_cli()` wraps the
   dispatch in `try/except SystemExit` and returns the exit code. This keeps
   the `_error()` helper simple while making the function testable.

2. **`run` uses `IterationRunner` directly** — `RunLifecycle.RunTable` is
   in-memory and doesn't survive CLI restarts. The `run` command reconstructs
   run state from persisted metadata and calls `IterationRunner` for each
   approved task, bypassing `RunExecutor`'s dependency on a live `RunTable`.

3. **`--json` before subcommand** — argparse global flags must appear before
   the subcommand name. All test invocations use
   `--workspace=X --json plan "goal"` order.

---

## Current State

### Test Count Growth

| Phase | Test Count |
|---|---|
| Phase 1 (models, roles, run_table, scoring, verification, loop_guard) | ~90 |
| Phase 2 (model_router, planner) | ~43 |
| Phase 3 (verification_runner, smoke_adapter, critic, arbiter, quality_gate) | 68 |
| Phase 3.5 additions | 15 |
| **Total before Phase 4** | **217** |
| Phase 4 (task_library, context_builder, memory, agent_profiles, run_lifecycle, checkpoint, workspace, task_groups, frontmatter) | 82 |
| Phase 4.5 additions | 8 |
| Phase 5 (execution, prompt_builder, claude_execution, iteration_runner, run_executor) | 46 |
| Phase 5.5 additions | 19 |
| Phase 5.6 additions | 22 |
| **Total before Phase 6** | **~391** |
| Phase 6 additions | 32 |
| **Total** | **~423** |

### Known Remaining Issues

| Issue | Impact | Addressed In |
|---|---|---|
| `RunLifecycle.RunTable` is in-memory | `run` command bypasses `RunExecutor` for execution | Phase 8 (persistent RunTable) |
| `--real` execution prints warning but still dry-runs | No actual Claude Code launch from CLI | Phase 8 (full Ralph Loop) |
| Critic acceptance criteria are keyword-heuristic | May miss semantic mismatches | Phase 4+ (LLM-based critic) |
| No persistent memory for quality gate state | Quality gate results are in-memory only | Phase 4 |
| No Admin UI | Run status visible only via CLI | Phase 7 |
| No Playwright | Browser-based KPI verification not possible | Phase 9 |

---

## Is Phase 7 Safe to Start?

**Yes**, with the same restrictions as Phase 6:

- CLI is additive — no existing modules were modified beyond adding the
  `fcc-ralph` entry point in `pyproject.toml`
- All Phase 6 code lives in `core/ralph/cli.py` and `tests/core/ralph/test_cli.py`
- Zero regression risk for existing FCC services

### Recommended Phase 7 Scope

Phase 7 should focus on the **Admin UI for Ralph Runtime**:

- Read-only dashboard showing run status, task progress, checkpoint history
- No write operations (approval remains CLI-only for safety)
- No Playwright integration (deferred to Phase 9)
- Optional: extend `fcc-ralph report` with HTML output format

### Risks for Phase 7

| Risk | Mitigation |
|---|---|
| Admin UI imports could pull in network dependencies | Keep Admin UI in `api/` (existing pattern), not `core/ralph/` |
| Dashboard could encourage bypassing approval workflow | Dashboard is read-only; approval requires explicit CLI command |
| Scope creep toward interactive task management | Defer edit/create/delete operations to Phase 8+ |

---

*End of Phase 6 report. Proceed to Phase 7 when ready.*
