# Phase 3 Report — Verification Quality Gate Layer

> Date: 2026-05-26
> Status: Complete — all checks passing

---

## Summary

### What Phase 3 Attempted

Phase 3 moved Ralph Runtime from planned-but-unexecuted verification into an active quality gate layer. Five new modules were built:

1. **VerificationRunner** — safe, bounded command execution with strict safety controls (disabled by default, prefix allowlist, timeout, truncation)
2. **FCCSmokeAdapter** — maps Ralph smoke target labels to FCC-compatible pytest commands
3. **CriticEngine** — deterministic (no LLM) review of verification results, scoring, and acceptance criteria
4. **ArbiterEngine** — rule-based dispute resolution between Doer and Critic with 9 priority-ordered rules
5. **QualityGate** — orchestrator that composes plan→runner→scoring→critic→loop guard→arbiter into a single structured result

### What Was Completed

- **`core/ralph/verification_runner.py`** — `VerificationRunner`, `CommandExecutionResult`, `VerificationRunnerConfig`
- **`core/ralph/smoke_adapter.py`** — `FCCSmokeAdapter`, `SmokePlan` with 16 known FCC smoke targets
- **`core/ralph/critic.py`** — `CriticEngine`, `CriticReview` with verification and scoring review methods
- **`core/ralph/arbiter.py`** — `ArbiterEngine`, `ArbiterAction` (APPROVE/RETRY/DEBUG/ESCALATE/STOP), `ArbiterDecision`
- **`core/ralph/quality_gate.py`** — `QualityGate`, `QualityGateResult` with full pipeline orchestration
- **`core/ralph/__init__.py`** — updated exports with 12 new symbols
- **`tests/core/ralph/test_verification_runner.py`** — 18 tests
- **`tests/core/ralph/test_smoke_adapter.py`** — 14 tests
- **`tests/core/ralph/test_critic.py`** — 13 tests
- **`tests/core/ralph/test_arbiter.py`** — 11 tests
- **`tests/core/ralph/test_quality_gate.py`** — 12 tests

### What Was NOT Completed

Nothing — all Phase 3 deliverables are complete. Items explicitly deferred:
- No task library / context builder (Phase 4)
- No memory store (Phase 4)
- No Admin UI (Phase 5)
- No Claude Code execution (Phase 6)
- No Playwright (Phase 7)

---

## Files Created

### `core/ralph/verification_runner.py`

| Purpose | Safe, bounded command execution for verification plans |
|---|---|
| **Classes** | `CommandExecutionResult` (command, status, exit_code, duration, stdout/stderr, timed_out, skipped, failure_reason), `VerificationRunnerConfig` (working_directory, timeout_seconds, max_output_chars, allow_command_execution, allowed_command_prefixes), `VerificationRunner` (run_plan, run_command, _execute, _is_allowed, _truncate) |

Safety features:
- **Disabled by default** — `allow_command_execution=False`
- **shlex.split** — explicit argv parsing, no `shell=True`
- **Allowed prefix matching** — only commands matching registered prefixes execute
- **Timeout enforcement** — configurable per-command timeout via `subprocess.run(timeout=...)`
- **Output truncation** — bounded stdout/stderr capture at `max_output_chars`
- **Structured results** — `CommandExecutionResult` with all execution metadata

### `core/ralph/smoke_adapter.py`

| Purpose | Maps smoke target labels to FCC-compatible command plans |
|---|---|
| **Classes** | `SmokePlan` (frozen: targets, commands, unknown_targets, requires_live_provider), `FCCSmokeAdapter` (known_targets, is_known, validate_targets, build_smoke_plan) |

Known targets (16): providers, api, cli, clients, nvidia_nim_cli, openrouter_free_cli, config, messaging, tools, voice, rate_limit, auth, extensibility,
lmstudio, llamacpp, ollama.

### `core/ralph/critic.py`

| Purpose | Deterministic critic that reviews verification + scoring results |
|---|---|
| **Classes** | `CriticReview` (approved, decision, score_card, pass/fail counts, failed_criteria, warnings), `CriticEngine` (review_verification, review_scoring) |

Review logic:
- Verification command pass/fail counts against 100% threshold
- Smoke target pass/fail counts against 100% threshold
- Acceptance criteria keyword matching against stdout summary
- ScoreCard evaluation with configurable minimum passing score
- Confidence estimation based on pass rates

### `core/ralph/arbiter.py`

| Purpose | Deterministic dispute resolution between Doer and Critic |
|---|---|
| **Classes** | `ArbiterAction` (APPROVE/RETRY/DEBUG/ESCALATE/STOP), `ArbiterDecision` (action, reason, summary, suggested_fixes), `ArbiterEngine` (decide) |

9-rule priority system:
1. Loop guard STOP → STOP
2. Loop guard ESCALATE → ESCALATE
3. Loop guard DEBUG → DEBUG
4. Critic approves + score acceptable → APPROVE
5. Critic rejected with very low confidence (≤0.4) → DEBUG
6. Too many critic rejections (≥3) → STOP
7. Too many retries (≥5) → ESCALATE
8. Moderate retries (≥3) → DEBUG
9. Otherwise → RETRY

### `core/ralph/quality_gate.py`

| Purpose | Orchestrates the full quality gate pipeline for a task |
|---|---|
| **Classes** | `QualityGateResult` (task_id, verification_plan/result, score_card, critic_reviews, loop_guard_decision, arbiter_decision, final_status, summary, all_passed), `QualityGate` (evaluate) |

Pipeline: `RalphTask → VerificationPlan → VerificationRunner → ScoreCard → CriticReview → LoopGuard → Arbiter → QualityGateResult`

---

## Files Modified

| File | Change |
|---|---|
| `core/ralph/__init__.py` | Added imports and exports for 12 new symbols: `ArbiterAction`, `ArbiterDecision`, `ArbiterEngine`, `CriticEngine`, `CriticReview`, `FCCSmokeAdapter`, `QualityGate`, `QualityGateResult`, `SmokePlan`, `CommandExecutionResult`, `VerificationRunner`, `VerificationRunnerConfig` |
| `core/ralph/verification_runner.py` | Fixed ruff issues (combined if branches, `dict.fromkeys`, removed unused `os` import); fixed type narrowing for stdout/stderr |
| `core/ralph/critic.py` | Fixed `CriticReview.approved` to come from `CriticDecision.approved` for consistency |
| `docs/ralph/FCC_RALPH_FEATURE_MAP.md` | Added Phase 3 section with module table, VerificationRunner/FCCSmokeAdapter/CriticEngine/ArbiterEngine/QualityGate descriptions, updated mapping table, updated remaining phases |
| `docs/ralph/FCC_RALPH_RUNTIME_ARCHITECTURE.md` | Added Phase 3 section with module table, architecture integration diagram, safety properties; updated roadmap and remaining table |

---

## Tests/Checks Run

### `uv run pytest tests/core/ralph -q`

| Result | Pass |
|---|---|
| **204 passed** in 3.70s | ✅ |

Coverage breakdown:
- Phase 1/2 tests: 133 passed (unchanged)
- `test_verification_runner.py`: 18 tests (new)
- `test_smoke_adapter.py`: 14 tests (new)
- `test_critic.py`: 13 tests (new)
- `test_arbiter.py`: 11 tests (new)
- `test_quality_gate.py`: 12 tests (new)

### `uv run ruff check core/ralph tests/core/ralph`

| Result |
|---|
| **All checks passed!** ✅ |

### `uv run ty check core/ralph`

| Result |
|---|
| **All checks passed!** ✅ |

Strict type checking with no errors, no warnings.

### `uv run pytest smoke --collect-only -q`

| Result |
|---|
| **76 tests collected** in 0.71s ✅ |

No regressions or collection errors.

---

## Design Decisions

### VerificationRunner Safety by Default

**Decision:** Command execution is DISABLED by default. Every test that needs command execution must explicitly create a
`VerificationRunnerConfig(allow_command_execution=True)` with allowed prefixes.

Rationale:
1. Prevents accidental command execution during import or initialization
2. Forces explicit opt-in, making safety visible in test code
3. Matching Phase 2's pattern of safe defaults (ModelRoleRouter doesn't call providers)

### Prefix Matching, Not Shell-Based

**Decision:** Use `shlex.split` + prefix list matching instead of `shell=True` or regex patterns.

Rationale:
1. No shell injection — `shlex.split` handles quoting and escaping
2. Narrow allowlist — must match from the first argv element
3. Testable — prefix matching is a simple list comparison
4. Consistent with FCC's security posture

### No FCC Smoke Import

**Decision:** The `FCCSmokeAdapter` maintains its own `_KNOWN_SMOKE_TARGETS` dict rather than importing from `smoke/features.py`.

Rationale:
1. `core/ralph/` should not import from `smoke/` — that would create a bad dependency direction
2. The adapter only needs target labels and pytest command patterns, not `FeatureCoverage` dataclasses
3. Self-contained — can be tested without FCC smoke infrastructure
4. Known targets are a stable, finite set extracted from `smoke/features.py`

### Decision From CriticDecision, Not Re-Computed

**Decision:** `CriticReview.approved` is derived from `CriticDecision.approved`, not re-computed from the pass/fail analysis.

Rationale:
1. Consistent single source of truth — the decision reflects all the special-case logic (no-checks-defined returns False, etc.)
2. The override/custom-case logic in `CriticDecision` is the authoritative verdict
3. Simpler maintainability — adding a new rule only requires changing one place

### Arbiter Rules Are Priority-Ordered

**Decision:** The arbiter uses a 9-rule priority system where the first matching rule wins.

Rationale:
1. Deterministic and predictable — same inputs always produce the same output
2. Explicit prioritization: safety (loop guard) → quality (critic) → escalation (retry/debug limits)
3. Testable — each rule can be exercised independently with controlled inputs
4. Extensible — new rules can be inserted at the appropriate priority level

---

## Current Limitations

| Limitation | Impact | Addressed In |
|---|---|---|
| Critic acceptance criteria are keyword-heuristic | May miss semantic mismatches | Phase 4+ (LLM-based critic) |
| No persistent memory | Quality gate state is in-memory only | Phase 4 |
| No task library / context builder | Tasks must be created manually or via planner | Phase 4 |
| No Claude Code launch | Ralph Loop does not exist yet | Phase 6 |
| No Admin UI | Run status visible only via Python API | Phase 5 |
| No Playwright | Browser-based KPI verification not possible | Phase 7 |

---

## Risks

| Category | Assessment |
|---|---|
| **Type/lint issues** | ✅ Clean — ruff (0 errors), ty (0 errors) |
| **FCC regression risk** | ✅ Zero risk — all changes are additive in new files. No existing FCC files modified outside `core/ralph/` and `docs/ralph/`. |
| **Import side effects** | ✅ No module-level `__init__` code beyond imports. No side effects. |
| **Command execution safety** | ✅ Disabled by default; prefix allowlist; timeout; truncation; no `shell=True` |
| **Provider/API coupling** | ✅ None — FCCSmokeAdapter has its own target registry, doesn't import from `smoke/` |
| **Network calls** | ✅ Zero — all modules are deterministic; VerificationRunner only runs allowed commands |
| **Subprocess execution in tests** | ✅ Only when explicitly configured with `allow_command_execution=True` and allowed prefixes |

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

**Why this order:**

1. **Task Library** loads tasks from `.ralph/tasks/` markdown files — needed before the Ralph Loop can dispatch real work
2. **Context Builder** gathers git diff, file tree, and goal context — feeds both planning and execution
3. **Memory Store** persists run table, quality gate results, and scoring history across sessions
4. **Agent Profiles** define per-agent instructions, temperature, and file access rules

**What Phase 4 should NOT include:**
- No Admin UI yet
- No Claude Code execution yet
- No Playwright yet

---

*End of Phase 3 report. Proceed to Phase 4 when ready.*
