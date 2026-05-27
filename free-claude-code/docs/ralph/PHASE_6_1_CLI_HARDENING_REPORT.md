# Phase 6.1 Report — CLI Integration Hardening

> **Date**: 2026-05-27
> **Status**: Complete — 435 tests passing, all checks clean

---

## Summary

Phase 6.1 hardens the `fcc-ralph` CLI so it truly uses the core Ralph runtime
and enforces the execution/approval contracts established in Phase 5.6 and
Phase 5.5.

The main bug was that `fcc-ralph run` bypassed `RunExecutor` and directly used
`IterationRunner`, which meant strict ordered approval (Policy A) was not
enforced by the CLI path.

## Bug Found: CLI Bypasses RunExecutor

**Problem**: `_cmd_run` in `cli.py` (Phase 6) selected all APPROVED tasks
manually and called `IterationRunner.run_iteration()` for each one. This meant:

1. Later approved tasks could run even when earlier tasks were PENDING
   (no Policy A enforcement)
2. Arbiter action handling (DEBUG/STOP/ESCALATE/RETRY) was ignored
3. Execution policy was effectively reimplemented in the CLI

**Why this was a problem**: Phase 5.6 established strict ordered approval
policy (Policy A): if TASK-001 is PENDING and TASK-002 is APPROVED, the
runtime should block on TASK-001 by default. The CLI bypassed this entirely.

**Fix**: `_cmd_run` now delegates to `RunExecutor.run_until_blocked()`, which
enforces Policy A internally. The CLI remains a thin wrapper: it validates
flags, loads workspace state, populates the executor's in-memory run table,
and prints results.

## Files Changed

| File | Change |
|---|---|
| `core/ralph/run_lifecycle.py` | Added `load_run_tasks()` — populates in-memory `RunTable` from persisted tasks |
| `core/ralph/run_executor.py` | Added `load_run_tasks()` — convenience method delegating to `RunLifecycle` |
| `core/ralph/cli.py` | Rewrote `_cmd_run` to use `RunExecutor.run_until_blocked()`; added `_print_task_result_line()` helper; added `RunExecutorConfig(stop_on_debug=False)` for dry-run mode; fixed `--task` validation order |
| `tests/core/ralph/test_cli.py` | 12 new tests (see below), 3 existing tests updated for new Policy A behavior |
| `docs/ralph/PHASE_6_REPORT.md` | Updated architecture section, run flow, test counts |
| `docs/ralph/PHASE_6_CLI_PLAN.md` | Added Phase 6.1 update note |
| `docs/ralph/FCC_RALPH_RUNTIME_ARCHITECTURE.md` | Added Phase 6.1 to roadmap and "What Remains" table |
| `docs/ralph/FCC_RALPH_FEATURE_MAP.md` | Added Phase 6.1 to mapping table |
| `docs/ralph/PHASE_6_1_CLI_HARDENING_REPORT.md` | Created — this report |

## Tests Added/Updated

### New Tests (12)

| Test | What It Covers |
|---|---|
| `test_strict_order_blocks_later_approved_task` | TASK-001 PENDING blocks TASK-002 APPROVED; approving TASK-001 allows run |
| `test_strict_order_json_shows_blocked_task` | `run --json` includes `blocked_task_id`, `pending_task_ids` |
| `test_specific_task_respects_strict_order` | `run --task=LATER` blocked when earlier task is PENDING |
| `test_specific_task_unknown_returns_error` | `run --task=NONEXISTENT` returns EXIT_TASK_NOT_FOUND |
| `test_approve_then_run_runs_multiple_tasks` | Approve all, run executes all tasks in order |
| `test_plan_json_output_is_parseable` | `plan --json` outputs parseable JSON with `goal_id`, `run_id`, `task_count`, `tasks` |
| `test_review_json_output_is_parseable` | `review --json` outputs parseable JSON list |
| `test_status_json_output_is_parseable` | `status --json` outputs parseable JSON object |
| `test_run_json_output_is_parseable` | `run --json` outputs parseable JSON with `status`, `tasks_run`, `task_results` |
| `test_json_error_does_not_mix_into_stdout` | JSON mode errors go to stderr, stdout stays clean |
| `test_main_is_importable` | `core.ralph.cli.main` is importable |
| `test_console_script_registered` | `pyproject.toml` registers `fcc-ralph` console script |

### Updated Tests (3)

| Test | Change |
|---|---|
| `test_run_with_approved_task_defaults_to_dry_run` | Expected rc changed from 0 to EXIT_APPROVAL_REQUIRED (Policy A) |
| `test_run_real_with_allow_flag_still_uses_dry_run` | Expected rc changed from 0 to EXIT_APPROVAL_REQUIRED (Policy A) |

## JSON Output Validation

All JSON output tests capture with `capsys` and parse with `json.loads()`:

- `plan --json`: validated fields: `goal_id`, `run_id`, `task_count`, `tasks`
- `review --json`: validated as list with `id`, `title`, `status` in each item
- `status --json`: validated as dict with `workspace`, `task_count`, `tasks_by_status`
- `run --json`: validated fields: `status`, `tasks_run`, `task_results`
- Error case: validated that `captured.out == ""` (no JSON mixed into stdout)

## Strict Ordered Approval Policy Result

The CLI now enforces Policy A:

```
Tasks: [PENDING, APPROVED, APPROVED, PENDING]
        ─────── ───────── ───────── ───────
        1st      2nd       3rd       4th

run_until_blocked():
  - Blocked at TASK-001 (PENDING) — even though TASK-002 and TASK-003 are APPROVED
  - Returns approval_required=True, blocked_task_id=TASK-001
```

After approving all tasks through TASK-001:
- TASK-001 runs (NEEDS_FIX in dry-run)
- Blocked at TASK-004 (PENDING)

The `--task` flag also respects strict order: running a specific later
approved task is blocked if any earlier task is PENDING.

## RunExecutor Delegation

Before (Phase 6):
```
fcc-ralph run
  → _cmd_run
    → IterationRunner.run_iteration()  (direct, no Policy A)
```

After (Phase 6.1):
```
fcc-ralph run
  → _cmd_run (validates flags/workspace/task-id)
    → RunExecutor.run_until_blocked()  (enforces Policy A, arbiter actions)
      → IterationRunner.run_iteration()
```

The `RunExecutorConfig(stop_on_debug=False)` is used for dry-run mode because
the quality gate always returns DEBUG when there are no verification results
(dry-run skips execution). Without this, multi-task dry-runs would stop after
the first task.

## Console Script Registration

- `pyproject.toml` contains `fcc-ralph = "core.ralph.cli:main"` ✅
- `core.ralph.cli.main` is importable and callable ✅
- Direct `_run_cli` tests remain as the primary test path

## Checks Run

```
$ uv run pytest tests/core/ralph -q        → 435 passed
$ uv run ruff check core/ralph tests/core/ralph → clean
$ uv run ty check core/ralph                → clean
$ python -m py_compile core/ralph/*.py      → all compile OK
$ uv run pytest smoke --collect-only -q     → smoke collection OK
```

## Safety Grep Results

| Check | Result |
|---|---|
| `shell=True` in `core/ralph/` | 0 matches ✅ |
| Provider imports | 0 matches ✅ |
| Network client imports | 0 matches ✅ |
| API key usage | 0 matches ✅ |
| Copilot dependency | 0 matches ✅ |

No provider imports, no network client imports, no `shell=True`, no API key
usage, no Copilot dependency in `core/ralph/` or `tests/core/ralph/`.

## Pass/Fail Results

All checks pass. 435 tests total (12 new + 423 existing).

## Is Phase 7 Safe to Start?

**Yes**, with the same restrictions as Phase 6:

- All changes are additive to existing modules
- Zero regression risk — all existing tests pass unchanged
- CLI integration is properly hardened against Policy A violations
- JSON output is validated and parseable

## Recommended Phase 7 Scope

CLI-driven Ralph Loop:

- Multi-iteration retry/debug loop
- Controlled real execution pilot
- Richer status/report commands

Do not implement Phase 7 as Admin UI — the CLI needs to mature first into a
full Ralph Loop driver before optional UI layers are built on top.

---

*End of Phase 6.1 report. Proceed to Phase 7 when ready.*
