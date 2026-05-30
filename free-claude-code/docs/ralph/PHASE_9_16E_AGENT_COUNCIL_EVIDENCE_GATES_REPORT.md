# Phase 9.16E — Agent Council Evidence Gates & Runtime Readiness Checks

**Date:** 2026-05-30
**Status:** COMPLETE
**Operator:** SPC (Ralph Runtime)
**Predecessor:** Phase 9.16D (Council Plan Task Planning Injection, `bb4a229`)
**Successor:** Phase 9.16F (TBD)

---

## 1. Why Phase 9.16E Exists

Phase 9.16D connected Agent Council plans to Ralph's task planning. But there was no mechanism to prevent:

- Beautiful reports with missing artifacts
- Fake-pass tasks (echo-only verification)
- Shallow verification (file existence checks only)
- Missing files hidden behind summaries
- Agent claims without supporting evidence
- Implementation tasks that don't prove outputs exist
- QA tasks that don't verify real behavior
- Final arbiter approvals without concrete evidence
- Runtime artifacts (.fcc/, .fcc-ralph/, .claude/, env, logs) being staged

Phase 9.16E adds a deterministic evidence gate layer that validates tasks, plans, and runtime state have enough evidence to proceed.

## 2. Files Created/Modified

### Created (4 files)

| File | Purpose |
|---|---|
| `core/ralph/agent_council/evidence_gates.py` | 12 default gates + models (EvidenceGateRequirement, EvidenceGateFinding, EvidenceGateResult) + enums |
| `core/ralph/agent_council/gate_runner.py` | Gate runner (run_evidence_gates, summarize, context serialization) |
| `tests/core/ralph/test_agent_council_evidence_gates.py` | 58 tests — all gates, models, enums, edge cases |
| `tests/core/ralph/test_agent_council_gate_runner.py` | 30 tests — runner, summary, context, enrichment |
| `tests/core/ralph/test_cli_council_gates.py` | 9 tests — CLI, JSON, determinism |

### Modified (4 files)

| File | Change |
|---|---|
| `core/ralph/agent_council/planning_context.py` | Added gate expectations lookup, `extract_gate_expectations()`, `build_gate_context_block()`, `add_gate_context_to_planning_dict()` |
| `core/ralph/agent_council/planner_integration.py` | `build_agent_council_task_context()` enriched with gate context; prompt formatter includes gate block |
| `core/ralph/cli.py` | `council-gates` subcommand + `_cmd_council_gates()` handler |
| `tests/core/ralph/test_agent_council_planner_integration.py` | Added `TestGateContextEnrichment` (4 tests) |

## 3. Evidence Gate Model Design

### Enums

| Enum | Values |
|---|---|
| `EvidenceGateSeverity` | `info`, `warning`, `error`, `critical` |
| `EvidenceGateStatus` | `passed`, `warning`, `failed`, `blocked`, `not_applicable` |

### Models

| Model | Key Fields |
|---|---|
| `EvidenceGateRequirement` | gate_id, name, description, required_evidence_types, required_paths, required_artifacts, applies_to_agents, applies_to_task_roles, applies_to_layers, blocking, severity, min_evidence_count, min_file_size_bytes, exclusive_paths, exclusive_patterns |
| `EvidenceGateFinding` | gate_id, status, message, details, affected_paths, affected_artifacts, required_action, severity |
| `EvidenceGateResult` | gate_id, findings, overall_status, gates_run/passed/warned/failed/blocked/skipped, blocking_issues, warnings, summary, is_ready, has_warnings |
| `GateEvaluationContext` | project_type, active_agent_ids, active_task_roles, required_artifacts, missing_artifacts, evidence_items, available_paths, verification_commands, acceptance_criteria, research_references, staged_paths, strict_mode |

## 4. Default Gates (12 gates)

| # | Gate | Purpose | Blocking |
|---|---|---|---|
| 1 | `artifact_exists_gate` | Required output artifacts must exist or be explicitly marked unavailable | Yes |
| 2 | `artifact_non_empty_gate` | Text/code/report artifacts must not be empty | No |
| 3 | `claim_has_evidence_gate` | Important claims must have at least one EvidenceItem | No |
| 4 | `implementation_file_gate` | Implementation tasks must produce or modify expected files | No |
| 5 | `verification_command_gate` | Verification must include real commands, not echo-only padding | Yes |
| 6 | `qa_behavior_gate` | QA must check behavior, edge cases, or AC, not just file existence | No |
| 7 | `security_evidence_gate` | Security must include concrete checks (dep scan, secret scan, config review, threat model) | Yes |
| 8 | `visual_evidence_gate` | Visual/UI tasks should include visual QA notes when applicable | No* |
| 9 | `research_reference_gate` | Agent decisions citing external patterns should reference Research Corpus | No |
| 10 | `final_arbiter_gate` | Final approval requires implementation, verification, QA, and risk evidence | Yes |
| 11 | `no_fake_echo_gate` | Verification must not rely only on echo keyword padding | Yes |
| 12 | `runtime_artifact_exclusion_gate` | Runtime artifacts (.fcc/, .fcc-ralph/, .claude/, env, logs, raw research repos) must not be staged | Yes |

\* Visual evidence warns rather than blocks (screenshots not always available)

## 5. Gate Runner Behavior

### `run_evidence_gates()`

Accepts planning context + optional evidence/state data. Runs all 12 default gates (or a specified subset). Each gate receives a `GateEvaluationContext` built from the planning context.

### Non-strict mode
- Missing non-critical evidence → WARNING
- Missing critical evidence → FAILED (but not BLOCKED unless the gate is explicitly blocking)
- Overall status: PASSED/WARNING/FAILED, never BLOCKED unless explicit blocking gate fails

### Strict mode
- Missing critical evidence on blocking gates → BLOCKED
- Gate metadata determines which gates are blocking

### `summarize_gate_result()` → human-readable multi-line summary
### `gate_result_to_context()` → JSON-serializable dict with findings, counts, blocking_issues

## 6. Planning Context Integration

Gate expectations are injected into the planning context via `add_gate_context_to_planning_dict()`, adding:

- `evidence_gate_expectations` — list of gate rules applicable to active agents
- `gate_prompt_block` — concise gate block for prompt injection
- `blocking_gates` — gates that must pass
- `warning_gates` — gates that produce warnings only
- `gate_summary` — summary string
- `readiness_gate_status` — initially "pending"

The prompt formatter includes the gate block for injection into task planning prompts.

## 7. CLI Integration Status

### Status: IMPLEMENTED

```bash
# Basic gate evaluation
fcc-ralph council-gates --project-type full_stack_app --goal "Build a CRM"

# JSON output
fcc-ralph council-gates --project-type landing_page --goal "Build a landing page" --json

# Strict mode
fcc-ralph council-gates --project-type full_stack_app --goal "Build a CRM" --strict
```

Flags: `--project-type`, `--goal`, `--strict`, `--json`

## 8. Example Gate Results

### landing_page (clean)
```
Overall: WARNING
Gates: 7 passed, 2 warned, 3 skipped
Warnings: Security evidence NA (no security agents), Research reference NA, Visual evidence NA
```

### full_stack_app (clean)
```
Overall: WARNING
Gates: 4 passed, 7 warned, 1 skipped
Blocking: None
Warnings: Artifact non-empty (no files to check), claim evidence, implementation file,
          QA behavior, security evidence, visual evidence, research reference
```

### full_stack_app + security agents (with strict mode)
```
Overall: BLOCKED
Blocking: final_arbiter_gate — Final Arbiter requires evidence from QA, security, perf testing
          security_evidence_gate — Security agents active but no security checks
```

## 9. Tests

| Test File | Tests | Coverage |
|---|---|---|
| `test_agent_council_evidence_gates.py` | 58 | All enums, models, 12 gates (pass/fail/warn/block/NA), strict/non-strict, invalid evidence |
| `test_agent_council_gate_runner.py` | 30 | Runner with real context, specific gate lists, evidence items, staged paths, summary, context serialization |
| `test_cli_council_gates.py` | 9 | All flags, JSON output, strict mode, determinism, all project types |
| Updated planner integration tests | +4 | Gate context enrichment in context and prompts |

**Total: 505 Agent Council + Planner + CLI tests, all passing.**
Full Ralph suite: 1096/1099 (3 pre-existing failures).

## 10. What Is Intentionally Not Implemented Yet

- **Shell command execution in gates** — Gates use context data, not filesystem inspection
- **Dynamic gate addition** — Gates are hardcoded; no plugin system yet
- **Gate integration with Ralph QualityGate pipeline** — Gates are separate; Phase 9.16F
- **Real file system checks** — Gates check provided context, not live disk state
- **Developer override** — Gates can't be bypassed yet; future phases

## 11. Remaining Risks

| Risk | Severity | Mitigation |
|---|---|---|
| Gates run on context data, not live disk | Medium | Gate runner accepts available_paths/file_sizes — caller provides live data |
| No integration with QualityGate pipeline yet | Low | Phase 9.16F will bridge |
| 12 gates may produce many warnings on minimal contexts | Low | Gates are non-blocking; warnings are informational |

## 12. Whether Phase 9.16F Is Safe to Start

**Yes — Phase 9.16F is safe to start.**

- All 505 tests pass
- 1096/1099 full suite pass (3 pre-existing)
- Gates are standalone and don't modify existing behavior
- Planning context enrichment is additive

---

## Phase Roadmap

| Phase | Status | Description |
|---|---|---|
| 9.16A | DONE | Agent Council V2 Core Foundation |
| 9.16B | DONE | Specialized Agent Registry Expansion |
| 9.16C | DONE | Council Plan Generator Integration |
| 9.16D | DONE | Council Plan Task Planning Injection |
| **9.16E** | **DONE** | **Agent Council Evidence Gates & Readiness Checks** |
| 9.16F | NEXT | TBD |
| 10 | DEFERRED | TBD |
