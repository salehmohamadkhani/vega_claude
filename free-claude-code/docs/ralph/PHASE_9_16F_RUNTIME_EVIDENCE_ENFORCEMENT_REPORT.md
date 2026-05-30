# Phase 9.16F — Runtime Evidence Enforcement & Task Result Binding

**Date:** 2026-05-30
**Status:** COMPLETE
**Operator:** SPC (Ralph Runtime)
**Predecessor:** Phase 9.16E (Agent Council Evidence Gates, `537a93a`)
**Successor:** Phase 9.16G (TBD)

---

## 1. Why Phase 9.16F Exists

Phase 9.16E created 12 deterministic evidence gates but they ran in isolation — there was no connection to actual task execution results. This phase binds evidence gates to runtime task outputs so that:

- Implementation tasks must prove files exist or were modified
- Verification tasks must prove real deterministic checks ran (not echo-only)
- QA tasks must prove behavior or edge cases were checked
- Final arbiter approval must depend on prior implementation, verification, QA, security, and risk evidence
- Fake echo-only verification is rejected
- Runtime-generated folders (.fcc/, .fcc-ralph/, .claude/, env, logs) are never treated as valid commit artifacts
- Existing behavior remains compatible when Agent Council enforcement is disabled

## 2. Files Created/Modified

### Created (2 files)

| File | Purpose |
|---|---|
| `core/ralph/agent_council/runtime_evidence.py` | Runtime evidence models + `extract_runtime_evidence_from_task_result()` |
| `core/ralph/agent_council/runtime_gate_enforcer.py` | Gate enforcement adapter: `enforce_runtime_evidence_gates()`, `should_block_task_approval()`, `runtime_gate_result_to_metadata()` |

### Modified (1 file)

| File | Change |
|---|---|
| `core/ralph/quality_gate.py` | `QualityGate.evaluate()` gets optional `agent_council_context`, `use_agent_council_gates`, `strict_agent_council_gates` params; council enforcement block added before return |

### Created Tests (2 files)

| File | Tests |
|---|---|
| `tests/core/ralph/test_agent_council_runtime_evidence.py` | 27 tests — models, dict extraction, object extraction, echo-only detection, QA/security behavior, forbidden paths |
| `tests/core/ralph/test_agent_council_runtime_gate_enforcer.py` | 25 tests — enforcement, strict/non-strict, metadata, approval blocking, backward compatibility |

## 3. Runtime Evidence Binding Design

### RuntimeEvidenceSource (14 values)

Covers: file_existence, file_non_empty, file_modified, command_output, test_result, qa_behavior, security_check, visual_qa, research_reference, arbiter_decision, acceptance_criteria, artifact_produced, staged_file, unknown

### RuntimeTaskEvidenceBundle

Extracted from task results via `extract_runtime_evidence_from_task_result()`. Handles:
- Dict-like task results
- Dataclass/object task results (IterationRunResult, ExecutionResult, QualityGateResult)
- Nested task extraction (task.verification_commands, task.acceptance_criteria)
- Changed/created files from execution results
- Quality gate arbitration status
- Graceful degradation on unknown shapes

### Echo-Only Detection

Commands starting with `echo ` are flagged unless they also contain real tool keywords (`$()`, backticks, pipes, `&&`, `||`, `test `, `grep `, `pytest`, `ruff`).

Verifier tasks with all-echo-only commands get `RuntimeEvidenceBindingStatus.BLOCKED`.

## 4. Gate Enforcement Adapter

### `enforce_runtime_evidence_gates()`

1. Extracts runtime evidence from task result
2. Builds or inherits planning context
3. Collects staged path violations
4. Converts evidence bindings to EvidenceItems
5. Runs all 12 evidence gates against the task's actual outputs

### `should_block_task_approval()`

Returns True when:
- Overall gate status is BLOCKED
- Any finding is BLOCKED
- Blocking issues exist

### `runtime_gate_result_to_metadata()`

JSON-serializable dict with enforcement status, gate counts, blocking issues, warnings, and per-gate findings.

## 5. Runtime/Quality-Gate Integration Status

### Status: SHALLOW INTEGRATION

`QualityGate.evaluate()` accepts three new optional parameters:
- `agent_council_context` — planning context dict
- `use_agent_council_gates` — enable enforcement (default: False)
- `strict_agent_council_gates` — blocking gates prevent approval (default: False)

When enabled:
1. Builds a task result wrapper from the task + verification results
2. Calls `enforce_runtime_evidence_gates()`
3. Overrides `final_status` to `BLOCKED` if `should_block_task_approval()` is True
4. Adds `council-gates=ok` or `council-gates=blocked` to summary
5. Gracefully degrades on exceptions (adds `council-gates=error`)

When disabled (default): behavior is identical to before.

## 6. CLI Integration Status

### Status: DEFERRED (not required for phase scope)

The runtime enforcement is integrated at the QualityGate level. CLI flags can be added in a future phase when the run/loop commands are updated to pass through the council enforcement parameters.

The existing `fcc-ralph council-gates` command provides static gate evaluation. Runtime binding happens automatically when QualityGate.evaluate() is called with the new parameters.

## 7. Backward Compatibility Status

**Fully backward compatible.**

- `QualityGate.evaluate()` defaults remain unchanged (`use_agent_council_gates=False`).
- All existing tests pass without modification.
- `quality_gate_test` suite passes unchanged.
- Council enforcement is opt-in at every level.

## 8. Example Blocked Cases

### Echo-Only Verification

```
Task: verifier, commands: ['echo "Verified: all good"']
Evidence extraction: is_echo_only=True → status=BLOCKED
Gate enforcement: verification_command_gate → BLOCKED
should_block_task_approval() → True
QualityGate final_status → BLOCKED
```

### Implementation Missing Files

```
Task: doer, changed_files=[], no quality gate output
Evidence extraction: no file bindings found → has_files=False
Gate enforcement: implementation_file_gate → FAILED
should_block_task_approval() → False (non-strict)
```

### Runtime Artifacts Staged

```
Task: changed_files=[".fcc/config.json", ".fcc-ralph/runs/test.json"]
Staged violation detection: .fcc/, .fcc-ralph/ → violations found
Gate enforcement: runtime_artifact_exclusion_gate → BLOCKED
should_block_task_approval() → True
```

### Final Arbiter Without Prior Evidence

```
Task: final_arbiter active, no evidence from QA, security, perf testing
Gate enforcement: final_arbiter_gate → BLOCKED (strict) / FAILED (non-strict)
should_block_task_approval() → True (strict)
```

## 9. Tests

| Test File | Tests | Coverage |
|---|---|---|
| `test_agent_council_runtime_evidence.py` | 27 | Models, dict/object extraction, echo-only detection, QA/security, forbidden paths |
| `test_agent_council_runtime_gate_enforcer.py` | 25 | Enforcement, strict/non-strict, metadata, approval, backward compat, QualityGate integration |
| Existing Agent Council tests | 505 | Unchanged |
| Existing Quality Gate tests | ~20 | Unchanged |

**Total: 577 council + quality gate + planner + CLI tests, all passing.**
Full Ralph suite: 1148/1151 (3 pre-existing failures).

## 10. What Is Intentionally Not Implemented Yet

- **CLI flags for run/loop commands** — `--use-agent-council-gates` and `--strict-agent-council-gates` can be added when the CLI layer is updated for Phase 9.16G
- **Deep runtime loop integration** — Enforcement is at the QualityGate level; the loop runner doesn't auto-extract evidence yet
- **File system level verification** — Gates check provided context, not live disk state
- **Automatic evidence collection** — Evidence must be manually provided or extracted from task results
- **Multi-task evidence aggregation** — Single-task enforcement only

## 11. Remaining Risks

| Risk | Severity | Mitigation |
|---|---|---|
| `_TaskResultWrapper` is minimal | Low | Only wraps what enforcement needs; full wrapper can be built in 9.16G |
| No live filesystem checks | Medium | Caller provides `available_paths` and `available_file_sizes`; future phase can auto-collect |
| Council context may be stale at runtime | Low | Enforcement builds minimal context from bundle when no plan available |

## 12. Whether Phase 9.16G Is Safe to Start

**Yes — Phase 9.16G is safe to start.**

- All 577 tests pass
- 1148/1151 full suite pass (3 pre-existing)
- Quality gate integration is shallow and opt-in
- Backward compatibility verified

---

## Phase Roadmap

| Phase | Status | Description |
|---|---|---|
| 9.16A | DONE | Agent Council V2 Core Foundation |
| 9.16B | DONE | Specialized Agent Registry Expansion |
| 9.16C | DONE | Council Plan Generator Integration |
| 9.16D | DONE | Council Plan Task Planning Injection |
| 9.16E | DONE | Agent Council Evidence Gates & Readiness Checks |
| **9.16F** | **DONE** | **Runtime Evidence Enforcement & Task Result Binding** |
| 9.16G | NEXT | TBD |
| 10 | DEFERRED | TBD |
