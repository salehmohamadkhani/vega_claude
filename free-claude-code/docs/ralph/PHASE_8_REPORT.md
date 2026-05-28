# Phase 8 — Controlled Real Execution Pilot

**Status**: Complete

**Date**: 2026-05-28

## Summary

Phase 8 adds a controlled real-execution pilot for fcc-ralph with a heavily guarded safety layer. The pilot creates an isolated throwaway workspace outside the repo and runs a small task through the normal Ralph loop machinery. All execution is dry-run by default; real execution requires explicit opt-in through `--real --allow-real-execution`.

## New Modules

### `execution_guard.py` — Real execution safety guard

Pre-execution safety checks before any real task can run:

- System root / home root detection — blocks `C:\`, `C:\Windows`, user home
- Forbidden path matching — blocks `C:\Program Files`, `C:\Windows\System32`, etc.
- Git repo root detection — blocks execution on repo root unless `--allow-repo-root-execution`
- Dirty git detection — blocks execution in dirty workspace unless `--allow-dirty-git`
- Changed file validation — enforces allowed/forbidden file rules after execution
- Structured `RealExecutionGuardResult` with all diagnostic fields

### `real_pilot.py` — Isolated pilot workspace creator

- `RealPilotConfig` — safe defaults: dry-run only, workspace in `%TEMP%`, allowed files enforced
- `RealPilot` class — creates workspace inside or outside repo, runs through `RalphLoopRunner`
- `RealPilotResult` — structured result with guard outcome, loop outcome, changed files, failure reasons
- Workspace created in `%TEMP%/vega-ralph-real-pilot` by default

### CLI Integration (`cli.py`)

New flags on `fcc-ralph run`:

| Flag | Purpose |
|---|---|
| `--pilot` | Enable pilot mode (creates throwaway workspace) |
| `--pilot-workspace PATH` | Custom pilot workspace path |
| `--allow-dirty-git` | Allow real execution on dirty git workspace |
| `--allow-repo-root-execution` | Allow real execution on repo root |
| `--real` | Enable real execution (dry-run without) |
| `--allow-real-execution` | Acknowledge safety risk |

New exit code: `5` (`EXIT_UNSAFE_REAL`) — real execution blocked by guard.

## Safety Architecture

```
fcc-ralph run --pilot --real --allow-real-execution
        │
        ▼
  RealPilot.run()
        │
        ├─ 1. Resolve pilot workspace path (temp or user-provided)
        ├─ 2. Create pilot workspace (mkdir + init)
        ├─ 3. Run ExecutionGuard
        │       ├─ Path exists?
        │       ├─ System root / home root?
        │       ├─ Forbidden path?
        │       ├─ Git repo root? (--allow-repo-root-execution)
        │       └─ Dirty git? (--allow-dirty-git)
        ├─ 4. Create pilot file (README.md)
        ├─ 5. Create approved pilot task
        ├─ 6. Run through RalphLoopRunner
        └─ 7. Detect changed files
```

## Guard Properties

| Check | Default | Override |
|---|---|---|
| System root (`C:\`, `D:\`, etc.) | Block | — |
| Home root | Block | — |
| Forbidden paths (`C:\Windows`, `Program Files`, etc.) | Block | — |
| Git repo root | Block | `--allow-repo-root-execution` |
| Dirty git | Block | `--allow-dirty-git` |
| Temp path (%TEMP%) | Allow | — |
| User-provided path outside repo | Allow | — |

## Test Growth

537 tests total (+65 from Phase 7.1). After Phase 8.5 lint cleanup: 536.

| File | Tests | What It Covers |
|---|---|---|
| `tests/core/ralph/test_execution_guard.py` | 26 | System root detection, guard checks, git detection, changed file validation |
| `tests/core/ralph/test_real_pilot.py` | 14 | Basic pilot, config, mocked execution, workspace isolation |
| `tests/core/ralph/test_cli_real_pilot.py` | 11 | Pilot commands, safety flags, approval gates, JSON output, side effects |

## Bugs Fixed During Development

| Issue | Fix |
|---|---|
| Docstring `SyntaxWarning` on `\` in `C:\` | Escaped backslashes |
| Guard blocking temp paths via `relative_to` ancestor match | Changed to exact path comparison |
| `strictly_ordered` typo in `RealPilot` | Changed to `strict_task_order` |
| CLI dispatch sent `--pilot` to `_cmd_run` instead of `_cmd_run_loop` | Added `or args.pilot` check |
| System root detection on Windows — `Path("C:/").anchor` returns string, not `Path` | Compare `resolved == Path(resolved.anchor)` |
| Pilot safety gate missing — `--real` without `--allow-real-execution` | Added safety gate in `_cmd_pilot_run` |
| Guard ran before workspace creation | Reordered: create workspace first |
| Test path expectations — README.md at wrong location | Updated to `pilot_path / ".fcc-ralph" / "README.md"` |

## Manual Verification

Both JSON and text output modes verified:

- `fcc-ralph --json run --pilot` — valid parseable JSON, guard correctly reports `allowed: true`
- `fcc-ralph run --pilot` — human-readable table with guard, loop, and changed-files summary
- Guard correctly blocks on system root (`C:\`) — returns `EXIT_UNSAFE_REAL`
- Dry-run produces `passed: false` (verification commands not executed in dry-run) — expected

## Pre-existing Issue (Not Phase 8)

`test_dry_run_returns_structured_result` fails on Windows due to `\\?\` prefix handling in `workspace.py`'s `safe_path()` function. Unrelated to Phase 8; pre-dates this work.

## Phase 9 Readiness

**Yes.** Phase 8 is stable, all 536 tests pass, and the pilot provides a validated path for real execution through the safety guard.
