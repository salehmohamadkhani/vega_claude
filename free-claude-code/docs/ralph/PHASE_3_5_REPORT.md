# Phase 3.5 Report — Stabilization Audit

> Date: 2026-05-26
> Status: Complete — all checks passing, 2 bugs fixed, 0 regressions

---

## Summary

Phase 3.5 is an intermediate stabilization phase between Phase 3 (quality gate)
and Phase 4 (task library / context builder). No major new features were added.
The goal was to audit, normalize, patch, and harden everything built so far
(Phases 1–3).

### What Was Found

| Category | Count | Details |
|---|---|---|
| Bugs fixed | 2 | Global counter in planner; RunTable duplicate entries |
| Config issues fixed | 2 | Bare `pytest` → `uv run pytest` in smoke adapter; missing `telegram`/`discord` targets |
| Edge cases hardened | 6 | Empty smoke plan, skipped verification, hallucination blocking, loop guard override, drift detection, determinism |
| Test files updated | 5 | planner, run_table, critic, quality_gate, arbiter, smoke_adapter |
| New tests added | 15 | See below |
| Architecture drift | 0 | All imports stay within `core.ralph.*` and stdlib |

### Files Changed

| File | Change |
|---|---|
| `core/ralph/planner.py` | Fixed `def self._next_task_id` → `def _next_task_id`; reset counter at start of `generate_tasks()` |
| `core/ralph/run_table.py` | (Fixed in earlier session) Duplicate task_id guard in `add_entry` |
| `core/ralph/smoke_adapter.py` | `pytest` → `uv run pytest`; `--co` → `--collect-only`; added `telegram`/`discord` targets; empty-targets collect-only command |
| `tests/core/ralph/test_planner.py` | Added determinism and stability tests (task IDs, cross-instance, plan pipeline) |
| `tests/core/ralph/test_run_table.py` | Added duplicate entry tests (dedup, update, completion accuracy) |
| `tests/core/ralph/test_smoke_adapter.py` | Updated command assertions; added features.py sync test |
| `tests/core/ralph/test_critic.py` | Added skipped verification and hallucination blocking tests |
| `tests/core/ralph/test_quality_gate.py` | Added skipped-verification, hallucination, and loop-guard-override tests |
| `tests/core/ralph/test_arbiter.py` | Added loop-guard-overrides-critic-approval test |

---

## Step-by-Step Results

### Step 0 — Repo Sanity Check

| Check | Result |
|---|---|
| Git branch | `master` ✅ |
| Remote | `origin` ✅ |
| Working tree | Clean ✅ |

### Step 1 — Full File Audit

Audited all 13 source files in `core/ralph/` plus test files and docs.

**Bugs found:**

1. **Global `_TASK_COUNTER` in `planner.py`** — Module-level global counter caused
   non-deterministic task IDs across calls. Calls to `plan()` or `generate_tasks()`
   would return different IDs if previous calls had incremented the counter.
   Fixed by moving to instance-level counter and resetting at start of each call.

2. **`RunTable.add_entry` unconditional append** — Same `task_id` added to
   `_run_entries[run_id]` list multiple times, inflating completion percentages.
   Fixed in earlier session with existence check before append.

### Step 2 — Line-Ending and Formatting Normalization

| Check | Result |
|---|---|
| Line endings (all Ralph files) | LF only ✅ |
| `ruff format` (12 files) | Clean ✅ |

### Step 3 — Fixed Planner Determinism

- Removed global `_TASK_COUNTER` → instance-level `self._task_counter`
- Counter resets at start of each `generate_tasks()` call
- New tests: cross-instance determinism, plan pipeline stability, ID format

### Step 4 — Hardened RunTable Duplicates

- `add_entry` now checks `entry.task_id not in self._run_entries[entry.run_id]`
  before appending to the run's entry list
- New tests: duplicate rejected, duplicate updates, completion not inflated

### Step 5 — VerificationRunner Audit

No code changes needed. Existing 18 tests already cover:

- Execution disabled by default
- Plan skipped when disabled
- Malformed input (shlex ValueError)
- Empty command, disallowed prefix
- Allowed prefix execution, command with args
- Non-zero exit code, stderr capture, output truncation
- Empty plan, mixed/all pass, timeout, file not found
- Metadata storage, compound prefix matching

### Step 6 — Hardened FCCSmokeAdapter

- All commands changed from `pytest` → `uv run pytest` with `--collect-only`
- Added missing targets: `telegram`, `discord` (extracted from `smoke/features.py`)
- Empty targets now return a collect-only fallback command
- Added explicit sync test against `smoke/features.py` inventory

### Step 7 — Hardened Critic and QualityGate

New edge-case regression tests:

| Test | File | What It Guards |
|---|---|---|
| `test_skipped_verification_does_not_approve` | test_critic.py | SKIPPED with no commands → not approved |
| `test_high_hallucination_risk_blocks_scoring_approval` | test_critic.py | HIGH hallucination → scoring fails |
| `test_skipped_verification_does_not_result_in_passed` | test_quality_gate.py | Default runner disabled → no PASSED |
| `test_high_hallucination_risk_blocks_approval` | test_quality_gate.py | HIGH hallucination through full gate → no PASSED |
| `test_arbiter_loop_guard_stop_overrides_critic_approval` | test_quality_gate.py | LoopGuard STOP → STOP even when critic approves |
| `test_loop_guard_stop_overrides_critic_approval` | test_arbiter.py | Arbiter rule priority: loop guard before critic |

### Step 8 — Architecture Drift

| Check | Result |
|---|---|
| Imports from `providers/` | 0 ✅ |
| Imports from Admin UI | 0 ✅ |
| Imports from Claude Code modules | 0 ✅ |
| Network calls beyond stdlib subprocess | 0 ✅ |
| All `core.ralph.*` imports use relative `.module` form | ✅ |

### Step 9 — Full Test Suite

| Suite | Result |
|---|---|
| `uv run ruff check core/ralph tests/core/ralph` | All checks passed ✅ |
| `uv run pytest tests/core/ralph -q` | 217 passed in 3.70s ✅ |
| `uv run ty check core/ralph` | All checks passed ✅ |
| `uv run python -c "from core.ralph import *"` | Import OK ✅ |
| `uv run pytest smoke --collect-only -q` | 76 tests collected ✅ |

---

## Design Decisions During Phase 3.5

### Planner Counter Reset

**Decision:** Reset `_task_counter` to 0 at the start of each `generate_tasks()` call.

**Rationale:** Without reset, calling `generate_tasks()` or `plan()` twice on the same
instance produces different IDs, violating determinism. The counter only needs to be
unique within a single call — IDs are prepended with TASK-001 through TASK-999 within
each call, which is sufficient for within-run uniqueness.

### `uv run pytest` Not `pytest`

**Decision:** All smoke adapter commands use `uv run pytest` instead of bare `pytest`.

**Rationale:** The rest of the project uses `uv run` for everything (tests, linting,
type checking). Bare `pytest` would bypass the virtual environment and potentially
use a different Python/interpreter. `uv run` ensures the correct venv is used.

### `--collect-only` Not `--co`

**Decision:** Command-line flags use long form `--collect-only` instead of short form `--co`.

**Rationale:** Readability and consistency with the rest of the codebase. The short `--co`
flag works identically but is less clear to readers unfamiliar with pytest.

### Explicit Features Inventory Sync Test

**Decision:** `test_all_known_targets_match_features_inventory` hardcodes the expected
target set extracted from `smoke/features.py`.

**Rationale:** This test will fail if targets are added to `features.py` but not to
the smoke adapter, or vice versa. The expected set is documented in the test with
a comment pointing to the source. The alternative (importing `features.py` directly)
would create a bad dependency direction from `core/ralph/` to `smoke/`.

---

## Current State

### Test Count Growth

| Phase | Test Count |
|---|---|
| Phase 1 (models, roles, run_table, scoring, verification, loop_guard) | ~90 |
| Phase 2 (model_router, planner) | ~43 |
| Phase 3 (verification_runner, smoke_adapter, critic, arbiter, quality_gate) | 68 |
| Phase 3.5 additions | 15 |
| **Total** | **217** |

### Known Remaining Issues

| Issue | Impact | Addressed In |
|---|---|---|
| Critic acceptance criteria are keyword-heuristic | May miss semantic mismatches | Phase 4+ (LLM-based critic) |
| No persistent memory | Quality gate state is in-memory only | Phase 4 |
| No task library / context builder | Tasks must be created manually or via planner | Phase 4 |
| No Claude Code execution | Ralph Loop does not exist yet | Phase 6 |
| No Admin UI | Run status visible only via Python API | Phase 5 |
| No Playwright | Browser-based KPI verification not possible | Phase 7 |

---

## Recommended Phase 4

### Task Library + Context Builder + Memory Store + Agent Profiles

Concrete next step:

```
core/ralph/task_library.py    — Markdown task file loading
core/ralph/context_builder.py — Git-aware task context gathering
core/ralph/memory.py          — Persistent memory store (JSON file)
core/ralph/profiles/           — Agent profile directory
tests/core/ralph/test_task_library.py
tests/core/ralph/test_context_builder.py
tests/core/ralph/test_memory.py
```

**What Phase 4 should NOT include:**
- No Admin UI yet
- No Claude Code execution yet
- No Playwright yet

---

*End of Phase 3.5 report. Proceed to Phase 4 when ready.*
