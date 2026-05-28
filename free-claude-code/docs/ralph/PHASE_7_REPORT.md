# Phase 7 — CLI-Driven Ralph Loop

**Status**: Complete (7.1 stabilization)

**Date**: 2026-05-28

## Summary

Phase 7 adds a multi-iteration Ralph loop (`fcc-ralph run --loop`) that orchestrates task execution through IterationRunner, QualityGate, Arbiter, and CheckpointStore components. The loop enforces strict ordered approval (Policy A): run the contiguous approved prefix, stop at the first pending task, never skip.

## Existing Partial Work Found

5 untracked files were already present at the start of Phase 7.1:

- `core/ralph/loop_policy.py` — Loop policy dataclass + LoopStopReason enum. Compiles cleanly, **unchanged**.
- `core/ralph/loop_runner.py` — `RalphLoopRunner` class. Required stabilization fixes.
- `tests/core/ralph/test_cli_loop.py` — Integration tests. Required alignment with policy.
- `tests/core/ralph/test_loop_policy.py` — Policy unit tests. **Untouched**, all pass.
- `tests/core/ralph/test_loop_runner.py` — Runner unit tests. **Untouched**, all pass.

Modified but unstaged from prior work:
- `core/ralph/cli.py` — Added `_cmd_run_loop`, `_print_loop_result`, `_print_loop_json`. Required stabilization.
- `docs/ralph/FCC_RALPH_RUNTIME_ARCHITECTURE.md` — Already modified, not updated further in Phase 7.1.

## Loop Policy Behavior

Defined in `loop_policy.py`:

- **Dry-run by default** (safe)
- **Require approval** for all tasks (Policy A)
- **Strict task order** — tasks run in generated order, PENDING blocks later tasks
- **Stop on debug/escalate** by default
- **Max 3 iterations per task** default
- **No auto-approval**

## CLI Loop Behavior

`fcc-ralph run --loop`:

- Delegates execution to `RalphLoopRunner`
- Accepts `--max-iterations`, `--max-tasks`, `--stop-on-debug`, `--stop-on-escalate`
- `--real` requires `--allow-real-execution` (still dry-runs in Phase 7)
- JSON output via `--json`: always valid parseable JSON on stdout, even for approval-required/error states
- Exit codes: 0 success, 1 error, 4 approval-required, 5 unsafe-real

### Contiguous Approved Prefix (Stabilization Fix)

The runner processes only the **contiguous prefix** of APPROVED tasks from the start of the task list. The first PENDING task (in strict mode) blocks all later tasks. If TASK-001 is APPROVED and TASK-002 is PENDING, TASK-001 runs, then the loop returns `approval_required` for TASK-002.

## Tests Fixed

5 tests in `test_cli_loop.py` required alignment with strict ordered approval:

- `test_run_loop_with_approved_task_runs` — Changed to approve all 4 tasks before running
- `test_run_loop_task_status_updated` — Changed to approve all 4 tasks before running
- `test_max_iterations_flag` — Changed to approve all 4 tasks before running
- `test_max_tasks_flag` — Changed to approve all 4 tasks before running
- `test_run_loop_json_pending_output` — Fixed to parse JSON from stdout (runner now produces JSON for approval-required instead of `_error()` to stderr)

Added new test: `test_later_approved_blocked_by_earlier_pending` — verifies TASK-001 runs, TASK-002 blocks.

## Commands Run

| Command | Result |
|---------|--------|
| `python -m py_compile core/ralph/*.py` | Pass |
| `uv run pytest tests/core/ralph -q` | 486 passed |
| `uv run pytest smoke --collect-only -q` | 76 collected |
| `uv run fcc-ralph --help` | Pass |

## Phase 7.1 Stabilization Changes

### `loop_runner.py` — Strict ordered approval refinement

Renamed `_check_strict_order` to `_find_first_pending_index`. The new method iterates the full task list to find the first PENDING task index, rather than only checking `tasks[0]`. The early-return logic in `run()` blocks the entire loop only when index 0 is PENDING (no earlier approved tasks to run). Later PENDING tasks are surfaced as `blocked_task_id` after the approved prefix executes.

### `cli.py` — JSON output hardening

The `_cmd_run_loop` handler passes all tasks (including pending) to the runner, which enforces Policy A internally. This ensures `--json` mode always produces parseable JSON on stdout, even for approval-required states. No plain-text `_error()` calls in the loop path before the runner for approval-related states.

### Test improvements (`test_cli_loop.py`)

- **Strengthened state assertions**: Tests now verify task status changes after run, not just exit codes.
- **`test_run_loop_with_pending_returns_approval_required`**: Verifies no task status changed (nothing ran).
- **`test_run_loop_pending_blocked`**: Verifies both first (PENDING) and second (APPROVED) tasks remain unchanged — later approved task does not bypass.
- **`test_later_approved_blocked_by_earlier_pending`**: Verifies TASK-001 ran (status changed from APPROVED) and TASK-002 remains PENDING.
- **`test_run_loop_json_pending_output`**: Checks `blocked_task_id` field in JSON output.
- **New `test_run_loop_json_all_pending_output`**: Verifies all-pending state produces valid parseable JSON on stdout, not plain text.

## Remaining Risks

- Dry-run quality gate returns DEBUG on all iterations (no verification results), so `stop_on_debug=True` by default halts after one iteration. `stop_on_debug=False` is needed for multi-iteration dry-runs. The CLI sets `stop_on_debug=False` via the RunExecutor path but the loop mode respects the flag as-is. This may surprise users in dry-run.
- `pass/fail` on last iteration: NOT PASSED but `next_action` is reported by the quality gate after max iterations.
- Report command writes to `.fcc-ralph/reports/` but no archive/rotation exists.
- Architecture doc (`FCC_RALPH_RUNTIME_ARCHITECTURE.md`) has not been updated for Phase 7 changes.

## Phase 8 Readiness

**Yes.** Phase 8 is safe to start. The Ralph loop is stable, all tests pass, and the CLI integration works correctly.
