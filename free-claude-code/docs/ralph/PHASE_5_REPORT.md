# Phase 5 Report — First Execution Layer

> **Date**: 2026-05-26
> **Status**: Complete — 345 tests passing, all checks clean

## Summary

Phase 5 introduces the first execution layer for the Ralph Runtime. It provides execution models, a structured prompt builder, a Claude Code execution adapter (dry-run by default), an iteration runner for single task iterations, and a run executor for multi-task run coordination. Real execution is opt-in and disabled by default — all paths are safe by design.

## Modules Created (5)

### 1. Execution Models — `core/ralph/execution.py` (130 lines)

- `ExecutionMode`: `DRY_RUN` / `REAL`
- `ExecutionStatus`: `NOT_STARTED` / `SKIPPED` / `SUCCEEDED` / `FAILED` / `TIMED_OUT` / `CANCELLED`
- `ExecutionRequest`: run_id, task_id, task_title, prompt, workspace_path, mode, timeout_seconds
- `ExecutionResult`: full result with status, mode, command, timestamps, output summary, changed files
- `ExecutionConfig`: dry_run=True by default, allow_real_execution=False, command_allowlist, max_output_chars, timeout_seconds
- `ExecutionResult.skipped(reason)` factory method
- `ExecutionResult.to_dict()` serialization

### 2. Prompt Builder — `core/ralph/prompt_builder.py` (210 lines)

- `TaskPromptContext`: goal, task, context_snapshot, agent_profile, verification_plan, memory_records, previous_errors, constraints
- `TaskPromptBuilder.build_task_prompt(context)` → 12-section structured prompt:
  1. Goal context
  2. Task definition
  3. Allowed files
  4. Forbidden files
  5. Acceptance criteria
  6. Verification commands
  7. KPIs
  8. Context snapshot
  9. Agent profile
  10. Memory records
  11. Previous errors
  12. Constraints
- Anti-hallucination guard: "Do NOT claim the task is complete unless ALL verification commands pass"
- Fully deterministic — no randomness, no model calls

### 3. Claude Code Execution Adapter — `core/ralph/claude_execution.py` (235 lines)

- `ClaudeCodeCommandBuilder.build_command(request)` → resolves CLI in order: `fcc-claude` > `claude` > `echo` (testing fallback)
- `ClaudeCodeExecutionAdapter.execute(request)`:
  - `DRY_RUN` → returns `SKIPPED` immediately
  - Real execution disabled → returns `SKIPPED` with message
  - Builds command → validates against basename allowlist → runs subprocess (shell=False) → truncates output → parses changed files
- `_is_command_allowed(command_str)`: strips quotes, extracts basename, checks against allowlist (cross-platform)
- `_parse_changed_files(output)`: regex for `Changed: path/to/file` lines
- `_build_output_summary(stdout, stderr)`: count of non-empty lines

### 4. Iteration Runner — `core/ralph/iteration_runner.py` (155 lines)

- `IterationRunResult`: run_id, task_id, iteration, execution_result, quality_gate_result, checkpoint, next_action, passed, failure_reason
- `IterationRunner.run_iteration(run, task, iteration_number, goal)` → 8-step pipeline:
  1. Build prompt via `TaskPromptBuilder`
  2. Execute via `ClaudeCodeExecutionAdapter`
  3. Update context
  4. Run quality gate
  5. Determine next action (passed/retry/debug/escalate/stop)
  6. Save checkpoint
  7. Update run table
  8. Return structured result
- Dry-run: passed=False, "Dry-run: execution was skipped"

### 5. Run Executor — `core/ralph/run_executor.py` (175 lines)

- `RunExecutorResult`: run, task_results, completed, failed, stopped_reason
- `RunExecutor.run_next_task(run, goal)`: finds next PENDING/APPROVED task, auto-approves, marks running, runs one iteration, updates status
- `RunExecutor.run_until_blocked(run, goal, max_tasks)`: loops through tasks, stops on Arbiter STOP/ESCALATE, loop guard stop, max_tasks, or completion
- `_find_next_task(run)`: linear scan for PENDING/APPROVED tasks

## Test Files Created (5)

| File | Tests | What It Covers |
|---|---|---|
| `tests/core/ralph/test_execution.py` | 10 | Default config, custom config, to_dict roundtrip, skipped factory, mode/status values |
| `tests/core/ralph/test_prompt_builder.py` | 11 | All 12 sections present, anti-hallucination phrase, determinism, includes task/context data |
| `tests/core/ralph/test_claude_execution.py` | 10 | Dry-run safety, real execution, allowlist blocking/enforcement, timeout, cwd, output truncation, no shell=True |
| `tests/core/ralph/test_iteration_runner.py` | 8 | Pipeline call ordering, dry-run result structure, provider independence, checkpoint creation |
| `tests/core/ralph/test_run_executor.py` | 7 | Task selection (PENDING/APPROVED), no-task handling, auto-approval, dry-run, insertion order |

## __init__.py Update

Added 12 new exports: `ClaudeCodeCommandBuilder`, `ClaudeCodeExecutionAdapter`, `CommandBuilderError`, `ExecutionAdapterError`, `ExecutionConfig`, `ExecutionMode`, `ExecutionRequest`, `ExecutionResult`, `ExecutionStatus`, `IterationRunResult`, `IterationRunner`, `TaskPromptBuilder`, `TaskPromptContext`, `RunExecutor`, `RunExecutorResult`.

## Safety Properties Verified

| Property | Status |
|---|---|
| Default dry-run | ✅ `ExecutionConfig(dry_run=True, allow_real_execution=False)` |
| No provider calls | ✅ Ralph Runtime never imports or calls providers |
| No shell=True | ✅ All subprocess calls use `shell=False` |
| Command allowlist | ✅ Basename matching against `command_allowlist` |
| Output truncation | ✅ `max_output_chars` caps stdout/stderr |
| Timeout enforcement | ✅ `subprocess.run(timeout=...)` |
| Deterministic prompts | ✅ No randomness or model calls in prompt builder |
| Cross-platform paths | ✅ Windows path quoting handled in allowlist check |

## Bugs Fixed During Development

1. **Windows `shutil.which("echo")`**: `echo` is a shell built-in on Windows, not an executable. Fixed by mocking commands with `sys.executable` in tests.
2. **Command allowlist path quoting**: `shlex.join()` quotes Windows backslash paths. Fixed by stripping quotes before basename extraction in `_is_command_allowed()`.
3. **QualityGate MagicMock type error**: `Checkpoint.from_run_state(score_card=gate_result.score_card)` called `float(MagicMock())`. Fixed by using real `QualityGateResult` objects in tests.
4. **Nested `with` statements (SIM117)**: Combined into single `with (...)` blocks.
5. **For loop in `_is_command_allowed` (SIM110)**: Replaced with `any()`.
6. **Ambiguous variable `l` (E741)**: Replaced with `line`.
7. **PERF401 list.extend pattern in prompt_builder.py (9 occurrences)**: Replaced with generator expressions.

## Check Results

```
$ ruff format --check    → clean
$ ruff check            → clean
$ ty check              → clean
$ pytest                → 345 passed
```

## Updated Files

| File | Change |
|---|---|
| `core/ralph/execution.py` | Created |
| `core/ralph/prompt_builder.py` | Created |
| `core/ralph/claude_execution.py` | Created |
| `core/ralph/iteration_runner.py` | Created |
| `core/ralph/run_executor.py` | Created |
| `core/ralph/__init__.py` | Updated with 15 new exports |
| `tests/core/ralph/test_execution.py` | Created |
| `tests/core/ralph/test_prompt_builder.py` | Created |
| `tests/core/ralph/test_claude_execution.py` | Created |
| `tests/core/ralph/test_iteration_runner.py` | Created |
| `tests/core/ralph/test_run_executor.py` | Created |
| `docs/ralph/FCC_RALPH_RUNTIME_ARCHITECTURE.md` | Updated roadmap, Phase 5 section |
| `docs/ralph/FCC_RALPH_FEATURE_MAP.md` | Updated mapping table, Phase 5 section |

## What's Next

- **Phase 6**: Admin UI for Ralph Runtime — run table browser, task status dashboard, KPI visualization
- **Phase 7**: Full Ralph Loop — connects RunExecutor to Claude Code through FCC proxy, end-to-end task execution
- **Phase 8**: Playwright KPI verifier — browser-based acceptance testing and KPI measurement
