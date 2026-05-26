# Phase 2 Report — Model Role Router & Task Planner

> Date: 2026-05-26
> Status: Complete — all checks passing

---

## Summary

### What Phase 2 Attempted

Phase 2 moved Ralph Runtime from passive data models into an active planning and model-role-resolution foundation. Two new modules were built:

1. **ModelRoleRouter** — bridges abstract Ralph `ModelRole` values to FCC's concrete provider/model configuration without importing providers or making network calls
2. **TaskPlanner** — converts a `ProjectGoal` into clarifying questions, a project spec, and deterministic RalphTasks using heuristic rules

### What Was Completed

- **`core/ralph/model_router.py`** — `ModelRoleRouter`, `ModelRoleResolution`, `ModelRoleRoutingPolicy`, `ModelRoleRoutingError`, `SettingsLike` protocol
- **`core/ralph/planner.py`** — `TaskPlanner`, `ClarifyingQuestion`, `ProjectSpec`, `TaskPlan`
- **`core/ralph/__init__.py`** — updated exports with new symbols
- **`tests/core/ralph/test_model_router.py`** — 25 tests covering tier resolution, agent_role mapping, thinking, safety, custom policies
- **`tests/core/ralph/test_planner.py`** — 16 tests covering questions, spec building, task generation, determinism, keyword metadata injection, verification plan conversion
- **`docs/ralph/FCC_RALPH_FEATURE_MAP.md`** — added Phase 2 section with mapping table and keyword metadata reference
- **`docs/ralph/FCC_RALPH_RUNTIME_ARCHITECTURE.md`** — added Phase 2 section with architecture diagram and updated roadmap

### What Was NOT Completed

Nothing — all Phase 2 deliverables are complete. Items explicitly deferred:
- No verification command execution (Phase 3)
- No FCC smoke adapter (Phase 3)
- No critic/arbiter skeleton (Phase 3)
- No task library/context builder (Phase 3)
- No Admin UI (Phase 4)
- No Claude Code execution (Phase 5)
- No Playwright (Phase 6)

---

## Files Created

### `core/ralph/model_router.py`

| Purpose | Maps abstract `ModelRole` → FCC-compatible resolved model info |
|---|---|
| **Classes** | `ModelRoleResolution` (frozen dataclass with model_role, claude_model_name, provider_model_ref, provider_id, provider_model, thinking_enabled, source), `ModelRoleRoutingPolicy` (frozen dataclass with tier-per-role defaults), `ModelRoleRouter` (resolve/resolve_agent_role/resolve_all), `ModelRoleRoutingError` |
| **Protocol** | `SettingsLike` — minimal interface for the FCC Settings methods consumed: `resolve_model`, `resolve_thinking`, `parse_provider_type`, `parse_model_name` |
| **Default mapping** | PLANNER → haiku, DOER → sonnet, CRITIC → opus (with thinking), DEBUGGER → sonnet, SUMMARIZER → haiku |

### `core/ralph/planner.py`

| Purpose | Deterministic heuristic-based task planner |
|---|---|
| **Classes** | `ClarifyingQuestion` (id, question, reason, required, category), `ProjectSpec` (goal_id, title, summary, constraints, success_kpis, assumptions, risks, target_areas), `TaskPlan` (goal, spec, questions, tasks), `TaskPlanner` (generate_questions, build_project_spec, generate_tasks, plan) |
| **Task generation** | Always creates 4 tasks: architect (context mapping) → doer (implementation) → verifier (testing) → summarizer (docs/report) |
| **Keyword injection** | Detects api/proxy/provider/model/routing → API metadata; admin/ui/browser/dashboard → UI KPI; messaging/telegram/discord → messaging smoke targets; tests/smoke/kpi → verification commands |

### `tests/core/ralph/test_model_router.py`

25 tests covering:
- Each `ModelRole` resolves to the correct Claude tier (PLANNER→haiku, DOER→sonnet, CRITIC→opus, DEBUGGER→sonnet, SUMMARIZER→haiku)
- Provider ID and provider model are parsed from FCC-style model refs
- Thinking flag is enabled only for opus-tier roles
- `resolve_agent_role()` correctly uses `AGENT_TO_MODEL_ROLE` mapping
- `resolve_all()` returns all model roles
- Error raised for unmapped roles
- No provider modules imported
- No API modules imported
- Custom policy overrides work
- Resolution source field is populated

### `tests/core/ralph/test_planner.py`

16 tests covering:
- Clarifying questions generated from goals with keyword matching
- Project spec built with constraints, KPIs, assumptions, risks
- At least 4 tasks generated
- Tasks are deterministic (same input → same output)
- Tasks are `PENDING`, not approved/running
- Descriptive stable IDs (`TASK-001-*`, `TASK-002-*`, etc.)
- First task is ARCHITECT role
- API/model/provider goals add API smoke targets
- UI/admin goals include UI/KPI-oriented metadata
- Messaging goals include messaging smoke target metadata
- Verification-focused goals include pytest/smoke commands
- Generated tasks convert to VerificationPlans
- No subprocess commands executed by planner
- Full `plan()` pipeline produces complete `TaskPlan`

---

## Files Modified

| File | Change |
|---|---|
| `core/ralph/__init__.py` | Added exports: `ClarifyingQuestion`, `ModelRoleResolution`, `ModelRoleRouter`, `ModelRoleRoutingPolicy`, `ProjectSpec`, `TaskPlan`, `TaskPlanner` |
| `core/ralph/model_router.py` | Auto-fixed by ruff: removed unused `field` import |
| `docs/ralph/FCC_RALPH_FEATURE_MAP.md` | Added Phase 2 section with updated mapping table and keyword metadata reference |
| `docs/ralph/FCC_RALPH_RUNTIME_ARCHITECTURE.md` | Added Phase 2 section with integration diagram and updated roadmap |

---

## Tests/Checks Run

### `uv run pytest tests/core/ralph -q`

| Result | Pass |
|---|---|
| **133 passed** in 3.14s | ✅ |

Coverage breakdown:
- Phase 1 core tests: 92 tests (unchanged, still pass)
- `test_model_router.py`: 25 tests (new)
- `test_planner.py`: 16 tests (new)

### `uv run ruff check core/ralph tests/core/ralph`

| Result |
|---|
| **All checks passed!** ✅ |

4 issues auto-fixed: unused imports, import sorting, missing `strict=True` in `zip()`. Zero remaining.

### `uv run ty check core/ralph`

| Result |
|---|
| **All checks passed!** ✅ |

Strict type checking with no errors, no warnings.

### `uv run pytest smoke --collect-only -q`

| Result |
|---|
| **76 tests collected** in 0.78s ✅ |

No regressions or collection errors.

---

## Design Decisions

### SettingsLike Protocol

**Decision:** Define a `SettingsLike` protocol in `model_router.py` instead of importing FCC's `Settings` class directly.

Rationale:
1. Tests can pass a lightweight `FakeSettings` stub without Pydantic env-file side effects
2. The protocol documents exactly which Settings methods the router consumes
3. Real `Settings` objects satisfy the protocol via structural subtyping — no adapter needed
4. No dependency on `config/settings.py` internals

### No Import from `api/model_router.py`

**Decision:** The Ralph `ModelRoleRouter` does not import FCC's `ModelRouter` from `api/`.

Rationale:
1. `core/ralph/` should not depend on `api/` — that would create a bad dependency direction (core ← api is correct, not api ← core)
2. FCC's `ModelRouter` is designed for incoming HTTP request routing (Claude model name → provider model). Ralph's router starts from `ModelRole` → Claude tier hint, then uses the same `Settings` methods
3. Keeping Ralph's router self-contained ensures it can be tested and imported without the API layer

### TaskPlanner is Heuristic, Not ML

**Decision:** Phase 2 uses purely rule-based keyword matching for task generation.

Rationale:
1. Deterministic output — same goal always produces the same tasks and questions
2. No LLM cost — zero API calls
3. Testable — every branch is exercised by a test case
4. Extensible — future phases can add an LLM-driven planner that calls this as a fallback or seed

### Task IDs are Stable

**Decision:** `TASK-001-context-map`, `TASK-002-implementation`, etc.

Rationale:
1. Readable and debuggable — you can tell what a task is about from its ID
2. Deterministic — same input always produces the same IDs
3. Unlike `uuid4().hex[:12]` which changes every run, stable IDs make test assertions reliable

---

## Current Limitations

| Limitation | Impact | Addressed In |
|---|---|---|
| No real execution | Tasks are planned but not executed | Phase 3+ |
| No FCC smoke adapter | Smoke targets are strings, not connected to FCC smoke runner | Phase 3 |
| No verification command execution | Plans are modeled but not run | Phase 3 |
| No critic/arbiter | Multi-agent deliberation not yet implemented | Phase 3 |
| No task library/context builder | Tasks must be created manually or via planner | Phase 3 |
| No Admin UI | Run status visible only via Python API | Phase 4 |
| No Claude Code launch | Ralph Loop does not exist yet | Phase 5 |
| No Playwright | Browser-based KPI verification not possible | Phase 6 |

---

## Risks

| Category | Assessment |
|---|---|
| **Type/lint issues** | ✅ Clean — ruff (0 errors), ty (0 errors) |
| **FCC regression risk** | ✅ Zero risk — all changes are additive in new files. No existing FCC files modified outside `core/ralph/` and `docs/ralph/`. |
| **Import side effects** | ✅ No module-level `__init__` code beyond imports. No side effects. |
| **Provider/API coupling** | ✅ None — `ModelRoleRouter` uses `Settings` protocol, not provider modules or API layer |
| **Network calls** | ✅ Zero — both modules are purely deterministic |
| **Subprocess execution** | ✅ Zero — no `subprocess`, `os.system`, or `Popen` in either module |

---

## Recommended Phase 3

### VerificationRunner + FCC Smoke Adapter + Critic/Arbiter Skeleton

Concrete next step:

```
core/ralph/verifier.py          — VerificationRunner that executes commands (no LLM)
core/ralph/smoke_adapter.py     — Adapter connecting Ralph smoke targets to FCC smoke runner
core/ralph/critic.py            — Critic skeleton (deterministic, rule-based)
core/ralph/arbiter.py           — Arbiter skeleton (resolves Doer↔Critic disputes)
tests/core/ralph/test_verifier.py
tests/core/ralph/test_critic.py
tests/core/ralph/test_arbiter.py
```

**Why this order:**

1. **VerificationRunner** is the natural next step — Phase 1 modeled verification plans, Phase 2 plans tasks with verification commands. Phase 3 should be able to *run* those commands (safely, with timeouts and output capture, no LLM).
2. **FCC Smoke Adapter** bridges Ralph smoke targets to FCC's existing smoke test runner — this is where Ralph Runtime touches FCC infrastructure for the first time.
3. **Critic/Arbiter** add multi-agent deliberation — a deterministic critic that can review task output against acceptance criteria, and an arbiter that resolves disputes without real LLM calls.

**What Phase 3 should NOT include:**
- No Claude Code execution yet
- No Admin UI yet
- No Playwright yet

Phase 3's Verifier should use `subprocess.run()` with timeouts (safe, bounded) for verification commands. The Critic should remain deterministic (pattern matching, acceptance criteria checking) — real LLM-based criticism can wait until Phase 4+.

---

*End of Phase 2 report. Proceed to Phase 3 when ready.*
