# Phase 5.5 Report — Execution Safety Audit and Approval-Gate Hardening

> **Date**: 2026-05-26
> **Status**: Complete — 364 tests passing, all checks clean

## Summary

Phase 5.7 hardens the Phase 5 execution layer based on an external review finding:
**RunExecutor auto-approved PENDING tasks by default**, violating the intended product flow:

```
goal → questions → task list → human review/approval → execution
```

The fix makes approval explicit: PENDING tasks are skipped unless an explicit config flag (`auto_approve_pending_tasks=True`) enables auto-approval.

Additionally, this phase hardens command fallback behavior, dry-run semantics, and prompt safety instructions.

## Bug Found: RunExecutor Auto-Approval

**File**: `core/ralph/run_executor.py`

**Root cause**: `_find_next_task()` treated both `PENDING` and `APPROVED` as "runnable", and `run_next_task()` unconditionally auto-approved pending tasks before execution.

**Fix**:
- Added `RunExecutorConfig` dataclass with `auto_approve_pending_tasks: bool = False`
- `run_next_task()` now returns `None` for PENDING tasks unless `auto_approve_pending_tasks=True`
- `run_until_blocked()` returns a structured `RunExecutorResult` with `approval_required=True` and `pending_task_ids` populated
- `RunExecutorResult` gained `approval_required: bool` and `pending_task_ids: list[str]` fields

## Files Changed

| File | Change |
|---|---|
| `core/ralph/run_executor.py` | Added `RunExecutorConfig`, approval gate logic, updated return types |
| `core/ralph/claude_execution.py` | `build_command()` requires explicit `allow_fallback`, raises `CommandBuilderError` when no CLI found |
| `core/ralph/iteration_runner.py` | Use `ExecutionStatus.SKIPPED` enum (not string), checkpoint records dry-run metadata |
| `core/ralph/prompt_builder.py` | Added scoped-change, forbidden-files, and changed-files report instructions |
| `core/ralph/execution.py` | Added `allow_test_fallback: bool = False` to `ExecutionConfig` |
| `core/ralph/__init__.py` | Export `RunExecutorConfig` |

## Tests Added/Updated (19 new)

| File | Tests Added | What It Covers |
|---|---|---|
| `test_run_executor.py` | 10 | No auto-approve by default, approval-required result, approved task runs, auto-approve with config, mixed status, task ordering, config defaults |
| `test_iteration_runner.py` | 3 | Dry-run failure reason, skipped execution reason, checkpoint records skipped state |
| `test_claude_execution.py` | 5 | No CLI found fails, no echo fallback in real mode, dry-run skips shutil.which and subprocess, real-disabled skips subprocess, echo fallback with config |
| `test_prompt_builder.py` | 3 | Scoped-changes, forbidden-files, changed-files instructions |
| `test_execution.py` | 1 | `allow_test_fallback` default is False |

## Command Execution Safety Status

| Property | Status | Verification |
|---|---|---|
| Default dry-run | ✅ `ExecutionConfig(dry_run=True, allow_real_execution=False)` | Unit test |
| No auto-approve | ✅ `RunExecutorConfig(auto_approve_pending_tasks=False)` | Unit tests |
| No shell=True | ✅ All subprocess calls use `shell=False` | Unit test + grep |
| No echo fallback in real mode | ✅ Raises `CommandBuilderError` if no CLI found | Unit test |
| Test fallback opt-in | ✅ `allow_test_fallback=False` by default | Unit test |
| Command allowlist | ✅ Basename matching, no wildcard exec | Unit tests |
| Output truncation | ✅ `max_output_chars` caps stdout/stderr | Unit test |
| Timeout enforcement | ✅ `subprocess.run(timeout=...)` | Unit test |
| No provider calls | ✅ Ralph Runtime never imports or calls providers | grep |
| Dry-run skips I/O | ✅ shutil.which and subprocess.run not called in dry-run | Unit tests |

## Approval Gate Behavior

| Scenario | Default Behavior |
|---|---|
| All tasks PENDING | `run_next_task()` returns `None`; `run_until_blocked()` returns `approval_required=True` |
| Mix of PENDING + APPROVED | Only APPROVED tasks execute; PENDING tasks block |
| Auto-approve enabled | `RunExecutorConfig(auto_approve_pending_tasks=True)` restores old behavior |
| No tasks at all | Returns `None` / `completed=True` (empty run) |
| All tasks completed | Returns `completed=True` |

## Dry-Run Behavior

- Dry-run execution returns `result.passed == False` with clear `failure_reason`
- Skipped execution does not accidentally pass the quality gate
- Checkpoint metadata records `execution_skipped=True` and `execution_mode="dry_run"`
- Dry-run does not call `shutil.which` or `subprocess.run`

## Check Results

```
$ pytest tests/core/ralph       → 364 passed
$ ruff check core/ralph tests   → All checks passed
$ ty check core/ralph           → All checks passed
$ grep "shell=True" ...         → No matches
$ grep "requests\|httpx\|..."   → No provider imports in ralph module
```

## Remaining Risks

1. **No `allow_test_fallback` validator**: If someone sets both `allow_real_execution=True` and `allow_test_fallback=True`, echo fallback could silently "succeed". This is intentional for development/testing but should be documented.
2. **No CLI health check before execution**: The adapter relies on `shutil.which` at command-build time. A race condition where the CLI is uninstalled between build and execution would hit `FileNotFoundError` (handled gracefully with FAILED status).
3. **Command allowlist is basename-only**: Full path validation is not performed. A malicious user could place a lookalike binary earlier in PATH. Acceptable risk for current scope.
4. **No execution audit log**: Successful real executions are not logged beyond the `ExecutionResult`. Future phases should add structured logging.

## Is Phase 6 Safe to Start?

**Yes**, with the following caveat:

- Phase 6 should be the **CLI surface** (`fcc-ralph plan`, `fcc-ralph review`, `fcc-ralph approve`, `fcc-ralph run`, `fcc-ralph status`, `fcc-ralph report`), not Admin UI.

The approval gate fix means the product flow is now:
```
goal → questions → task list → human review/approval → fcc-ralph approve → execution
```

Admin UI should remain postponed because:
1. The CLI surface is needed first for the feedback loop
2. Admin UI requires frontend infrastructure not yet built
3. The current run/approval flows need CLI testing before UI design

## Recommended Phase 6 Scope

```
CLI surface for Ralph Runtime:
- fcc-ralph plan        — plan tasks from a goal
- fcc-ralph review      — show pending tasks requiring approval
- fcc-ralph approve     — approve specific tasks for execution
- fcc-ralph run          — execute approved tasks (dry-run or real)
- fcc-ralph status       — show run/task status
- fcc-ralph report       — generate execution summary
```
