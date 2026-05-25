# Phase 1 Report — FCC-Native Ralph Runtime Foundation

> Date: 2026-05-25
> Status: Complete — all checks passing

---

## Summary

### What Phase 1 Attempted

Phase 1 established the first real FCC-native Ralph Runtime foundation inside FCC. The goal was to extract the useful architecture from the external Ralf project (copilot-ralph-mode) and rebuild the right parts natively inside FCC — without copying Copilot-specific logic, without adding a GitHub Copilot dependency, and without modifying any existing FCC functionality.

### What Was Completed

- **Two architecture documents** in `docs/ralph/`:
  - `FCC_RALPH_FEATURE_MAP.md` — maps FCC vs Ralph capabilities, identifies what we rebuild vs what we skip
  - `FCC_RALPH_RUNTIME_ARCHITECTURE.md` — full architecture, component boundaries, phase roadmap

- **8 core module files** in `core/ralph/`:
  - `roles.py` — `AgentRole` (8 roles), `ModelRole` (5 roles), role mappings
  - `models.py` — `ProjectGoal`, `RalphTask`, `RalphRun`, `RalphIteration`, `CriticDecision`, 3 status enums
  - `run_table.py` — `RunTableEntry`, `RunTable` with add/update/query/completion/serialization
  - `scoring.py` — `ScoreCard` with 0-100 range validation, weighted scoring, hallucination risk penalty
  - `verification.py` — `VerificationPlan`, `VerificationResult`, `build_verification_plan_for_task`
  - `loop_guard.py` — `LoopGuardDecision`, `LoopGuard` with 6 deterministic evaluation rules
  - `__init__.py` — clean public API re-exporting all symbols
  - `README.md` — module documentation

- **6 test files** in `tests/core/ralph/`:
  - `test_models.py` — 18 tests
  - `test_run_table.py` — 13 tests
  - `test_scoring.py` — 14 tests
  - `test_verification.py` — 17 tests
  - `test_loop_guard.py` — 18 tests
  - Plus `__init__.py`

- **All checks passing**:
  - 92 pytest tests passed
  - ruff clean
  - ty clean (strict type checking)
  - Smoke collection working (76 tests discovered, no regressions)

### What Was NOT Completed

Nothing — all Phase 1 deliverables are complete. Items explicitly deferred:
- No task planner (Phase 2)
- No model role router (Phase 2)
- No verification command execution (Phase 3)
- No critic/arbiter agents (Phase 3)
- No memory store (Phase 3)
- No Admin UI (Phase 4)
- No Playwright (Phase 5)

---

## Files Created

### docs/ralph/FCC_RALPH_FEATURE_MAP.md

| Purpose | Catalog of FCC capabilities we reuse, Ralph capabilities we rebuild, and Ralph features we skip |
|---|---|
| **Key sections** | FCC Capabilities We Reuse, Ralph Capabilities We Rebuild Natively, Mapping Table (Ralph → FCC), Testing/KPI Strategy |

### docs/ralph/FCC_RALPH_RUNTIME_ARCHITECTURE.md

| Purpose | Full architecture document with component diagram, ownership boundaries, phase roadmap |
|---|---|
| **Key sections** | Final Architecture (ASCII diagram), ownership rationale, Phase 1 scope, Phase 2+ roadmap |

### core/ralph/__init__.py

| Purpose | Public API for the Ralph Runtime module |
|---|---|
| **Exports** | All 28 public symbols from submodules |

### core/ralph/roles.py

| Purpose | Abstract agent and model role definitions |
|---|---|
| **Classes** | `AgentRole` (8 values: PLANNER, ARCHITECT, DOER, CRITIC, VERIFIER, DEBUGGER, ARBITER, SUMMARIZER), `ModelRole` (5 values: PLANNER, DOER, CRITIC, DEBUGGER, SUMMARIZER) |
| **Constants** | `AGENT_TO_MODEL_ROLE` — default mapping, `AGENT_ROLE_LABELS` — human-readable labels |

### core/ralph/models.py

| Purpose | Deterministic domain dataclasses for the Ralph Runtime |
|---|---|
| **Classes** | `ProjectGoal`, `RalphTask`, `RalphRun`, `RalphIteration`, `CriticDecision` |
| **Enums** | `TaskStatus` (9 values), `RunStatus` (8 values), `IterationStatus` (4 values) |
| **Key behavior** | `RalphRun.__post_init__` auto-sets `current_task_id`, `RalphRun.advance_to_next_task()` returns next task, `RalphTask` validates `max_iterations >= 1`, `CriticDecision` validates `0.0 <= confidence <= 1.0` |

### core/ralph/run_table.py

| Purpose | In-memory run table tracking task lifecycle |
|---|---|
| **Classes** | `RunTableEntry` — single entry with score/verification/error tracking; `RunTable` — collection with operations |
| **Key methods** | `add_entry`, `update_status`, `update_score`, `record_error`, `get_entry`, `get_entries_for_run`, `list_active_entries`, `list_failed_entries`, `completion_percentage`, `serializable`, `clear` |

### core/ralph/scoring.py

| Purpose | Deterministic 0-100 scoring model with hallucination risk penalty |
|---|---|
| **Classes** | `ScoreCard` (5 score fields + hallucination risk + notes), `HallucinationRisk` (LOW/MEDIUM/HIGH) |
| **Key methods** | `final_weighted_score(weights)` — configurable weights, `is_passing(threshold=80)` — high hallucination risk blocks unless OVERRIDE in notes |

### core/ralph/verification.py

| Purpose | Verification planning models (no execution in Phase 1) |
|---|---|
| **Classes** | `VerificationStatus`, `VerificationPlan` (commands/smoke/kpis/flags), `VerificationResult` (status + results dicts) |
| **Key functions** | `build_verification_plan_for_task(task)` — converts RalphTask verification metadata into a structured plan |
| **Key methods** | `VerificationPlan.is_empty()`, `VerificationResult.all_passed()`, `VerificationResult.summary_line()` |

### core/ralph/loop_guard.py

| Purpose | Deterministic loop guard — no AI calls, no subprocesses |
|---|---|
| **Classes** | `LoopAction` (5 values), `LoopGuardDecision`, `LoopGuard` |
| **Key methods** | `evaluate(current_iteration)` — 6 rules evaluated in order (STOP → ESCALATE → DEBUG → RETRY → CONTINUE), `record_error/verification_failure/progress_summary/critic_rejection`, `reset` |
| **Thresholds** | 3 repeated errors → ESCALATE, 5 verification failures → DEBUG, 10-char min summary → RETRY, 3 critic rejections → STOP |

### core/ralph/README.md

| Purpose | Module-level documentation |
|---|---|
| **Content** | What this is, separation of concerns table, Phase 1 status, basic usage example |

---

## Files Modified

| File | Reason |
|---|---|
| `core/ralph/roles.py` | Replaced `typing.Final` with `Final` from `typing` → ruff UP035 auto-fix; updated to use `dict`/`list` instead of `Dict`/`List` |
| `core/ralph/models.py` | Added `__post_init__` to `RalphRun` to fix bug: `current_task_id` was `None` when tasks passed via constructor. Also: ruff auto-fix replaced `typing.*` with builtins, `datetime.timezone.utc` → `UTC` |
| `core/ralph/run_table.py` | Ruff auto-fix: replaced `typing.*` with builtins, `Optional[X]` → `X \| None` |
| `core/ralph/scoring.py` | Ruff auto-fix: removed unused `typing.List` import |
| `core/ralph/verification.py` | Ruff auto-fix: replaced `typing.*` with builtins |
| `core/ralph/loop_guard.py` | Ruff auto-fix: removed unused imports (`field`, `List`, `Optional`), replaced `List` → `list` |
| `core/ralph/__init__.py` | Sorted `__all__` alphabetically (RUF022) |
| `tests/core/ralph/test_verification.py` | Fixed test that incorrectly assumed `VerificationPlan(smoke_targets=[...])` sets `requires_live_provider=True` (that's the builder's job, not the constructor) |

---

## Tests/Checks Run

### `uv run pytest tests/core/ralph -q`

| Result | Pass |
|---|---|
| **92 passed** in 2.79s | ✅ |

Key coverage:
- Model creation, defaults, validation, status parsing (18 tests)
- Run table add/update/query/completion/serialization (13 tests)
- Score range validation, weighting, risk penalties, passing thresholds (14 tests)
- Verification plan building from commands/smoke/kpis, result pass/fail/summary (17 tests)
- Loop guard continue/stop/escalate/debug/retry/reset/edge cases (18 tests)

### `uv run ruff check core/ralph tests/core/ralph`

| Result |
|---|
| **All checks passed!** ✅ |

57 issues auto-fixed via `ruff check --fix`. Remaining 1 issue (`RUF022 __all__ not sorted`) fixed manually.

### `uv run ty check core/ralph`

| Result |
|---|
| **All checks passed!** ✅ |

Strict type checking with no errors, no warnings.

### `uv run pytest smoke --collect-only -q`

| Result |
|---|
| **76 tests collected** in 1.73s ✅ |

No regressions or collection errors. Smoke tests unaffected by Phase 1 changes.

---

## Baseline / Environment Issues

No issues encountered. The FCC project environment was fully functional:
- Python 3.14.0 (CPython)
- uv package manager working
- All 77 dependencies installed cleanly
- ruff, ty, pytest all functional
- Smoke collection discovers all tests without error

---

## Design Decisions

### Module Path: `core/ralph/`

FCC already has `core/` as "Neutral shared application core" (see `core/__init__.py`). The Ralph Runtime is a core orchestration capability, not a plugin or integration — it belongs in `core/`. Alternative paths considered:

| Path | Rejected Because |
|---|---|
| `plugins/ralph/` | Would suggest optional/pluggable nature; Ralph Runtime is a core capability |
| `ralph/` (top-level) | Would pollute the top-level namespace; FCC keeps pure Python packages at top |
| `api/ralph/` | API layer is too high; runtime logic belongs in core |

### Dataclasses vs Pydantic

**Decision: dataclasses** for all Ralph Runtime models.

Rationale:
1. FCC's existing `core/` modules use plain dicts, TypedDicts, and `@dataclass` — not Pydantic
2. FCC reserves Pydantic for `config/settings.py` (config layer) and provider configs; the core runtime layer deliberately avoids Pydantic coupling
3. Ralph Runtime models are deterministic value objects — they don't need Pydantic's validation/serialization machinery
4. Dataclasses have zero dependencies, which keeps `core/ralph/` importable by any other module without creating a Pydantic import chain

### FCC Ownership of Provider/Model Routing Preserved

- `AgentRole` and `ModelRole` are abstract enums — they contain no provider names, no API keys, no FCC configuration
- `AGENT_TO_MODEL_ROLE` maps agent roles to model capability roles, not to providers
- The future `ModelRoleRouter` (Phase 2) will resolve `ModelRole` → FCC provider/model string via FCC Settings
- The Ralph Runtime never calls providers directly, never reads credentials, never manages API keys

### Ralf Runtime Separated from Copilot-Specific Behavior

- No `copilot` references anywhere in the code
- No `.github/agents/` conventions
- No shell loop code
- No `argparse` CLI duplication
- The `AgentRole` enum uses abstract names (PLANNER, ARCHITECT, DOER, etc.) rather than Copilot-specific role names
- Task structure (`RalphTask`) is FCC-native: `smoke_targets`, `kpis`, `allowed_files` — not Copilot prompt-file based

---

## Current Limitations

| Limitation | Impact | Addressed In |
|---|---|---|
| No real execution | Run table entries are created manually; no task planner | Phase 2 |
| No model calls | Scoring is deterministic; no actual LLM evaluation | Phase 2 |
| No verification command execution | Plans are modeled but not run | Phase 3 |
| No Playwright | Browser-based KPI verification not possible | Phase 5 |
| No Admin UI | Run status visible only via Python API | Phase 4 |
| In-memory only | No persistence across restarts | Phase 2+ |
| No critic/arbiter | Multi-agent deliberation not yet implemented | Phase 3 |

---

## Recommended Phase 2

The natural next step is:

### ModelRoleRouter + TaskPlanner Skeleton

**Concrete next step:**
```
core/ralph/model_router.py  — ModelRoleRouter that reads FCC Settings model config
core/ralph/planner.py       — TaskPlanner that breaks a ProjectGoal into RalphTasks
tests/core/ralph/test_model_router.py
tests/core/ralph/test_planner.py
```

**Why this order:**
1. ModelRoleRouter is the bridge between Ralph Runtime and FCC's provider layer — it proves the integration works
2. TaskPlanner is the first "active" component — it produces RalphTasks from a goal description
3. Both are deterministic enough to test without real provider calls (use a mock model config)

**What Phase 2 should NOT include:**
- No Claude Code execution yet
- No real provider calls yet
- No Admin UI yet
- No Playwright yet

Phase 2's ModelRoleRouter should read `RALPH_PLANNER_MODEL`, `RALPH_DOER_MODEL`, etc. from FCC Settings (extending the fields added conceptually in Phase 1) and resolve them through `config/settings.py`'s existing model resolution logic.

---

## Risk Notes

| Category | Assessment |
|---|---|
| **Type/lint issues** | ✅ Clean — ruff (0 errors), ty (0 errors) |
| **Packaging** | ✅ `core/ralph/` is inside the existing `core/` package which is already included in `pyproject.toml` wheel packages. No pyproject.toml modification needed. |
| **Python 3.14 compatibility** | ✅ All code uses `from __future__ import annotations`, builtin generics (`list[str]` not `List[str]`), `X | None` syntax, `datetime.UTC`. Fully compatible. |
| **ruff compatibility** | ✅ Using ruff-idiomatic patterns; `RUF022` requires sorted `__all__` (fixed) |
| **ty compatibility** | ✅ Strict type checking passes with zero errors |
| **Import side effects** | ✅ No module-level `__init__` code beyond imports. No side effects. |
| **FCC regression risk** | ✅ Zero risk — no existing FCC files were modified. All new files in new directories. |
| **Future Pydantic migration** | Low. If needed, dataclasses can be wrapped in Pydantic models for API serialization (Phase 4). |

---

*End of Phase 1 report. Proceed to Phase 2 when ready.*
