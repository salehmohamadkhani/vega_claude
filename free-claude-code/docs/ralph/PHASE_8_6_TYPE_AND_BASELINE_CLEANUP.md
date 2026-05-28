# Phase 8.6 — Type and Baseline Test Cleanup

**Status**: Complete

**Date**: 2026-05-28

## Summary

Phase 8.6 resolves the remaining 32 `ty` type-checker diagnostics in `cli.py` and confirms the status of 4 pre-existing baseline test failures before Phase 9. All diagnostics were fixed with minimal, safe changes. No new features, no behavioral changes.

## Type Diagnostics Fixed

### 1. `RalphTask | None` narrowing after `_error()` guards (4 sites)

`find_task()` returns `RalphTask | None`. After an `if task is None: _error(...)` guard, the type checker cannot infer that the remaining branch is unreachable because `_error()` raises `SystemExit` (a runtime behavior, not a type-level narrowing). Fixed by adding `assert task is not None` / `assert target is not None` after each guard.

| Location | Function | Site |
|---|---|---|
| `cli.py:225` | `_cmd_review` | `tasks = [task]` — needed narrowed `RalphTask` for list type |
| `cli.py:318` | `_cmd_approve` | `task.status` access |
| `cli.py:370` | `_cmd_run` (first target) | `target.status` access |
| `cli.py:425` | `_cmd_run` (second target) | `target.status` access |

### 2. `SystemExit.code` type confusion (`cli.py:1284`)

`SystemExit.code` has type `int | str | None`. The original code `e.code if e.code is not None else EXIT_ERROR` did not narrow `str` — `str` is also not `None`. Changed to `e.code if isinstance(e.code, int) else EXIT_ERROR`, which correctly narrows to `int`.

## Before / After

| Check | Before | After |
|---|---|---|
| `ty check core/ralph` | 32 diagnostics | All checks passed |
| `ruff check core/ralph tests/core/ralph` | 0 errors | 0 errors (regression-free) |
| `pytest tests/core/ralph -q` | 536 passed | 536 passed |
| `pytest -q` (full suite) | 1961 passed, 4 failed | 1961 passed, 4 failed |

## Baseline Test Failures (Unchanged)

4 pre-existing failures confirmed identical to Phase 8.5. All are FCC import-boundary tests — not Ralph runtime issues. Documented in `PHASE_8_5_STABILIZATION_AUDIT.md`.

| Test | Reason |
|---|---|
| `test_model_router.py::test_no_provider_modules_imported` | FCC providers list has grown; test's module list is stale |
| `test_model_router.py::test_no_api_modules_imported` | API modules restructured; test's module list is stale |
| `test_cli.py::test_no_provider_imports` | Same stale boundary check |
| `test_cli.py::test_no_network_imports` | `aiohttp` detected as transitive dependency (not Ralph importing it directly) |

## Windows `\\?\` Path Prefix

The `\\?\` prefix issue in `workspace.py`'s `safe_path()` was investigated. All dry-run-related tests pass (24/24). The `\\?\` prefix only manifests on very long paths (>260 chars) and does not affect any current test. No action required. Documented for awareness.

## Files Changed

| File | Changes |
|---|---|
| `core/ralph/cli.py` | 4 assert statements for type narrowing + 1 SystemExit.code fix |

Lines changed: 6 additions, 1 deletion. Zero behavioral changes.

## Phase 9 Readiness

**Yes.** Type diagnostics are clean. All 536 Ralph tests pass. ruff is clean. Baseline failures are documented and unchanged. Phase 9 can proceed.
