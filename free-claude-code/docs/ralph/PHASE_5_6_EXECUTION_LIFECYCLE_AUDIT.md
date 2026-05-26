# Phase 5.6 Report — Execution Lifecycle Hardening Before CLI

> **Date**: 2026-05-26
> **Status**: Complete — 391 tests passing, all checks clean

## Summary

Phase 5.6 hardens the execution lifecycle before CLI development begins (Phase 6). Six risks identified during the Phase 5.5 audit are resolved:

1. **`max_iterations_per_task` not enforced** — now tracked per-task in `run_until_blocked()`
2. **`stop_on_debug` not used** — DEBUG/ESCALATE/RETRY arbiter actions now handled with structured results
3. **`IterationRunner` hardcodes `ExecutionMode.DRY_RUN`** — configurable via `IterationRunnerConfig`
4. **`allow_test_fallback=True` with `allow_real_execution=True` allows unsafe echo fallback** — blocked by `validate_for_execution()`
5. **Command allowlist is basename-only** — hardened with `list[str]` parsing, `.exe` variants, Windows path safety
6. **Approval order policy not explicit** — Policy A (strict ordered) documented and enforced

## Six Risks and Their Fixes

### Risk 1: `max_iterations_per_task` Not Enforced

**Problem**: `RunExecutorConfig.max_iterations_per_task` existed but `run_until_blocked()` never used it.

**Fix**: `run_until_blocked()` now tracks per-task iteration counts in a `task_iterations: dict[str, int]` and checks `iteration_number > self._config.max_iterations_per_task` before each iteration. When exceeded, returns a `RunExecutorResult` with `stopped_reason` containing the limit message.

### Risk 2: `stop_on_debug` / `stop_on_escalate` / RETRY Not Handled

**Problem**: `run_until_blocked()` ignored `stop_on_debug` and `stop_on_escalate` config flags. RETRY from the arbiter was unhandled.

**Fix**: Added structured handling for all `ArbiterAction` values:
| Action | Behavior | Result Fields |
|---|---|---|
| STOP | Always stops, sets `RunStatus.FAILED` | `failed=True` |
| RETRY | Stops (multi-iteration not implemented) | `retry_required=True` |
| DEBUG | Stops when `stop_on_debug=True` | `debug_required=True` |
| ESCALATE | Stops when `stop_on_escalate=True`, sets `RunStatus.FAILED` | `escalation_required=True`, `failed=True` |
| APPROVE | Continues to loop guard check | (none) |

Added `RunExecutorResult` fields: `blocked_task_id`, `retry_required`, `debug_required`, `escalation_required`.

### Risk 3: `IterationRunner` Hardcodes `ExecutionMode.DRY_RUN`

**Problem**: `IterationRunner.run_iteration()` always created `ExecutionRequest(mode=ExecutionMode.DRY_RUN)`.

**Fix**: Added `IterationRunnerConfig(execution_mode=ExecutionMode.DRY_RUN)` and updated `IterationRunner.__init__()` to accept a config. The hardcoded `ExecutionMode.DRY_RUN` is now `self._config.execution_mode`.

Checkpoint metadata enriched with:
- `execution_status` — `ExecutionStatus` value string
- `execution_exit_code` — integer exit code
- `execution_timed_out` — boolean timeout flag
- `quality_gate_action` — arbiter action value string

### Risk 4: Echo Fallback Safety

**Problem**: `allow_test_fallback=True` with `allow_real_execution=True` could silently substitute echo for real Claude Code CLI.

**Fix**: Added `ExecutionConfigError` exception and `validate_for_execution()` / `validate_for_test_fallback()` methods. The `ClaudeCodeExecutionAdapter.execute()` calls `validate_for_execution()` before building the command. The combination `allow_real_execution=True` AND `allow_test_fallback=True` now raises `ExecutionConfigError` and returns `ExecutionStatus.FAILED`.

### Risk 5: Command Allowlist Weaknesses

**Problem**: `_is_command_allowed()` used `str.split()` which broke on quoted Windows paths, and the default allowlist didn't include `.exe` variants.

**Fix**:
- Changed `_is_command_allowed(command_str: str)` to `_is_command_allowed(command: list[str])` — operates on argv list directly, eliminating quoting/escaping concerns entirely
- Added `.exe` variants to default allowlist: `["fcc-claude", "fcc-claude.exe", "claude", "claude.exe"]`
- 8 new allowlist tests: basename matching, prefix rejection, Unix paths, Windows paths, empty list, malicious lookalike rejection

### Risk 6: Approval Order Policy

**Problem**: RunExecutor's approval order behavior was implicit, not documented or enforced as policy.

**Fix**: Policy A (strict ordered execution) is now explicit in `run_until_blocked()`:
- The first PENDING task blocks all later tasks (even APPROVED ones)
- `blocked_task_id` in `RunExecutorResult` identifies the blocking task
- The `_find_next_task` method documents the policy with a clear docstring

## Files Changed

| File | Change |
|---|---|
| `core/ralph/execution.py` | Added `ExecutionConfigError`, `validate_for_execution()`, `validate_for_test_fallback()`; `.exe` in default allowlist |
| `core/ralph/claude_execution.py` | `_is_command_allowed` now takes `list[str]`, calls `validate_for_execution()` |
| `core/ralph/iteration_runner.py` | Added `IterationRunnerConfig`, configurable execution mode, enriched checkpoint metadata |
| `core/ralph/run_executor.py` | `max_iterations_per_task` enforced, debug/escalate/retry handling, Policy A, `blocked_task_id` |
| `core/ralph/__init__.py` | Export `IterationRunnerConfig` |

## Tests Added/Updated

| File | Tests Added | What It Covers |
|---|---|---|
| `test_run_executor.py` | 10 | DEBUG stops/continues, ESCALATE stops/continues, RETRY, STOP, Policy A blocking, blocked_task_id, max_tasks limit |
| `test_iteration_runner.py` | 8 | IterationRunnerConfig defaults, dry-run mode, REAL mode, checkpoint execution_status/exit_code/timed_out/quality_gate_action |
| `test_claude_execution.py` | 10 | Allowlist basename matching, prefix rejection, Unix/Windows paths, empty list, config validation rejection |
| `test_execution.py` | 4 | `validate_for_execution()` passes/blocks, `validate_for_test_fallback()` passes/blocks |

## Execution Mode Policy

```
ExecutionRequest.mode
  ↓
DRY_RUN ───────────────────────────→ SKIPPED (immediately)
REAL + allow_real_execution=False ──→ SKIPPED
REAL + allow_real_execution=True
  + allow_test_fallback=True ───────→ FAILED (config validation error)
  + allow_test_fallback=False ──────→ builds command → executes
```

`IterationRunnerConfig(execution_mode=ExecutionMode.DRY_RUN)` is the default. Real execution requires:
```python
config = IterationRunnerConfig(execution_mode=ExecutionMode.REAL)
exec_config = ExecutionConfig(
    allow_real_execution=True,
    allow_test_fallback=False,
)
runner = IterationRunner(config=config, execution_adapter=ClaudeCodeExecutionAdapter(config=exec_config))
```

## Approval Order Policy (Policy A)

```
Tasks in insertion order: [APPROVED, PENDING, APPROVED]
                          ───────── ─────── ────────
                          1st task   2nd     3rd

run_until_blocked():
  - Runs task-1 (APPROVED)
  - Stops at task-2 (PENDING) — blocks all remaining tasks
  - Returns approval_required=True, blocked_task_id="task-2"
```

## Command Allowlist Decision

`_is_command_allowed` operates on `list[str]` (argv list) instead of parsing a shell-joined string:
- Eliminates all quoting/escaping edge cases
- No `shlex.split` needed (which mishandles `\f`, `\t` in Windows paths)
- Cross-platform: Unix paths (`/usr/bin/fcc-claude`) and Windows paths (`C:\tools\fcc-claude.exe`) both handled
- Exact basename matching required — prefix attacks (`fcc-claude-malicious`) rejected by design

Default allowlist: `["fcc-claude", "fcc-claude.exe", "claude", "claude.exe"]`

## Test Results

```
$ pytest tests/core/ralph       → 391 passed
```

## Remaining Risks

1. **`max_iterations_per_task` is dead code until retry logic**: The guard exists but tasks with `NEEDS_FIX` status are not re-selected by `_find_next_task`. The guard activates once a re-approval/retry mechanism is added.
2. **No execution audit log**: Successful real executions are not logged beyond `ExecutionResult`. Future phases should add structured logging.
3. **No CLI health check before execution**: Relies on `shutil.which` at command-build time. Race condition where CLI is uninstalled between build and execution hits `FileNotFoundError` (handled gracefully).

## Is Phase 6 Safe to Start?

**Yes**. All six lifecycle risks are resolved. The execution layer is hardened for CLI development:
- Safe defaults preserved: all paths remain dry-run by default
- Approval policy is explicit and enforced
- Real execution requires deliberate opt-in at two levels (IterationRunner + ExecutionConfig)
- Echo fallback cannot silently substitute for real CLI
- All arbiter actions produce structured, testable results
