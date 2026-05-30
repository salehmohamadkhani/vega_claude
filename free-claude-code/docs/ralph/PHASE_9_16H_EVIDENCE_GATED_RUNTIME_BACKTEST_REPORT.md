# Phase 9.16H — Evidence-Gated Runtime Backtest

**Date:** 2026-05-30
**Status:** COMPLETE
**Operator:** SPC (Ralph Runtime)
**Predecessor:** Phase 9.16G (CLI Flags & Runtime Loop Wiring, `202ec83`)
**Successor:** Phase 9.16I (TBD)

---

## 1. Why Phase 9.16H Exists

Phases 9.16E through 9.16G built evidence gates, runtime enforcement, and CLI wiring. This phase validates the entire chain end-to-end using deterministic JSON fixtures — no LLM calls, no real execution, no network access. It proves that gate enforcement correctly blocks bad task results and approves good ones.

## 2. Backtest Fixtures Created

6 JSON fixtures in `tests/core/ralph/fixtures/agent_council_runtime_backtest/`:

| # | Fixture | Scenario | Expected Result |
|---|---|---|---|
| 1 | `echo_only_verifier_result.json` | Verifier with echo-only commands | BLOCKED |
| 2 | `missing_file_implementation_result.json` | Implementation with no produced files | WARNING |
| 3 | `valid_implementation_result.json` | Implementation with real files and commands | PASS/WARN |
| 4 | `valid_verification_result.json` | Verifier with deterministic commands and edge-case AC | PASS/WARN |
| 5 | `final_arbiter_without_evidence_result.json` | Final arbiter without QA/security/perf evidence | BLOCKED (strict) |
| 6 | `runtime_artifact_staged_result.json` | Files include .fcc/, .claude/, .env, logs, secrets | BLOCKED |

## 3. Cases Tested (50 tests, 7 test classes)

### TestBacktestEvidenceExtraction (7 tests)
- All fixtures extract without crashing
- Echo-only verification detected at extraction level (`status=BLOCKED`)
- Missing files detected (`has_files=False`)
- Valid implementation has files (`has_files=True`)
- Valid verification has real commands (`has_real_commands=True`)
- Runtime artifacts extracted as file evidence
- Correct task roles extracted

### TestBacktestGateEnforcement (11 tests)
- All fixtures run through 12 gates without crash
- Echo-only verifier → `verification_command_gate` FAILED/BLOCKED
- Echo-only → `gates_failed + gates_blocked > 0`
- Valid implementation → not blocked by `should_block_task_approval()`
- Valid implementation → `implementation_file_gate` PASSED/WARNING
- Valid verification → `verification_command_gate` PASSED/WARNING
- Final arbiter without evidence → `final_arbiter_gate` FAILED/BLOCKED (strict)
- Runtime artifacts → `runtime_artifact_exclusion_gate` BLOCKED (strict)
- Runtime artifacts → BLOCKED even in non-strict mode
- All forbidden path categories (.fcc/, .fcc-ralph/, .claude/, .env, logs/) detected

### TestBacktestDisabledGates (3 tests)
- Echo-only extracted correctly even without enforcement
- QualityGate.evaluate() defaults work with all 6 fixtures, no council-gates in summary
- Enabled gates add `council-gates` tag to summary

### TestBacktestMetadata (3 tests)
- All fixtures produce valid metadata dicts
- All metadata is JSON-serializable
- Summarize works for all fixtures

### TestBacktestMatrix (4 tests)
- All 6 expected fixtures exist on disk
- Matrix covers all fixtures
- Every fixture loads as valid JSON with required keys
- Parametrized: should_block_task_approval matches expectation for 9 matrix entries

### TestNoNetworkOrLLM (2 tests)
- Fixtures contain no URLs, API keys, or executable content
- Test file has no network import statements

## 4. Expected Block/Pass Matrix

| Fixture | Strict | Expected Blocked | Actual Blocked | Match |
|---|---|---|---|---|
| echo_only_verifier | Yes | BLOCKED | BLOCKED | ✅ |
| missing_file_impl | Yes | Not blocked | Not blocked | ✅ |
| valid_impl | No | Not blocked | Not blocked | ✅ |
| valid_verification | No | Not blocked | Not blocked | ✅ |
| valid_verification | Yes | Not blocked | Not blocked | ✅ |
| final_arbiter_no_evidence | Yes | BLOCKED | BLOCKED | ✅ |
| runtime_artifacts | Yes | BLOCKED | BLOCKED | ✅ |
| runtime_artifacts | No | BLOCKED | BLOCKED | ✅ |

## 5. Blocked Cases (Verified)

1. **Echo-only verification** — `verification_command_gate` FAILED/BLOCKED. `RuntimeEvidenceBindingStatus.BLOCKED`.
2. **Implementation missing files** — Detected at extraction level, `implementation_file_gate` warns.
3. **Final arbiter without evidence** — `final_arbiter_gate` FAILED/BLOCKED in strict mode. Missing evidence from QA, security, performance testing.
4. **Runtime artifacts** — `.fcc/`, `.fcc-ralph/`, `.claude/`, `.env`, `logs/`, `secrets/` all trigger `runtime_artifact_exclusion_gate` → BLOCKED even in non-strict mode.

## 6. Pass Cases (Verified)

1. **Valid implementation** — Files present, real commands, edge-case criteria. Not blocked.
2. **Valid verification** — Deterministic commands (pytest, ruff, ty). Real verification keywords. `verification_command_gate` PASSED/WARNING.

## 7. CLI Backtest Status

**Skipped.** A `fcc-ralph gate-backtest` CLI command would duplicate what pytest already executes. The backtest is a test suite, not a runtime tool. All 50 tests run through pytest with clear pass/fail output.

Smoke commands pass:
- `fcc-ralph --help` ✅
- `fcc-ralph council-gates --project-type landing_page --goal "..."` ✅
- `fcc-ralph plan --use-agent-council --project-type landing_page "..."` ✅

## 8. Bugs Found and Fixed

No bugs found in the gate enforcement chain. All 50 backtest assertions passed on first run (after one trivial docstring fix).

## 9. Backward Compatibility Status

**Fully backward compatible.**
- All backtests use the same runtime gate enforcer API as production code.
- QualityGate.evaluate() defaults unchanged.
- Existing tests pass without modification.
- Fixtures are self-contained JSON files with no external dependencies.

## 10. What Is Intentionally Not Implemented Yet

- **`fcc-ralph gate-backtest` CLI** — pytest is the correct tool for running tests
- **Live filesystem checks** — Backtests use fixture dicts, not real disk state
- **Multi-task evidence aggregation** — Single-task enforcement only
- **Persistent backtest history** — Results are ephemeral

## 11. Remaining Risks

| Risk | Severity | Mitigation |
|---|---|---|
| Fixtures may need updates if Task models change | Low | Fixtures are dicts, not dataclasses — they degrade gracefully |
| Not all gate states are tested in combination | Low | 12 gates × 6 fixtures covers the critical paths |

## 12. Whether Phase 9.16I Is Safe to Start

**Yes — Phase 9.16I is safe to start.**

- All 677 council/gate/backtest/quality/planner/CLI tests pass.
- 1248/1251 full Ralph suite pass (3 pre-existing).
- Backtest proves gate enforcement works end-to-end.
- No regressions, no breaking changes.

---

## Phase Roadmap

| Phase | Status | Description |
|---|---|---|
| 9.16A | DONE | Agent Council V2 Core Foundation |
| 9.16B | DONE | Specialized Agent Registry Expansion |
| 9.16C | DONE | Council Plan Generator Integration |
| 9.16D | DONE | Council Plan Task Planning Injection |
| 9.16E | DONE | Agent Council Evidence Gates & Readiness Checks |
| 9.16F | DONE | Runtime Evidence Enforcement & Task Result Binding |
| 9.16G | DONE | CLI Flags & Runtime Loop Wiring for Agent Council Gates |
| **9.16H** | **DONE** | **Evidence-Gated Runtime Backtest** |
| 9.16I | NEXT | TBD |
| 10 | DEFERRED | TBD |
