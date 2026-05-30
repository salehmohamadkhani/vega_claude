# Phase 9.16G — CLI Flags & Runtime Loop Wiring for Agent Council Gates

**Date:** 2026-05-30
**Status:** COMPLETE
**Operator:** SPC (Ralph Runtime)
**Predecessor:** Phase 9.16F (Runtime Evidence Enforcement, `05002f9`)
**Successor:** Phase 9.16H (TBD)

---

## 1. Why Phase 9.16G Exists

Phase 9.16F added runtime evidence binding and a shallow QualityGate enforcement adapter. But there was no way to enable enforcement from the CLI or pass gate configuration through the runtime loop. This phase wires the pieces together:

- A `RuntimeGateConfig` model that controls gate behavior
- Wiring from CLI flags → `IterationRunnerConfig` → `QualityGate.evaluate()`
- Runtime loop integration so gate enforcement can block task approval in real execution flows

## 2. Files Created/Modified

### Created (1 file)

| File | Purpose |
|---|---|
| `core/ralph/agent_council/runtime_gate_config.py` | `RuntimeGateConfig` dataclass + `runtime_gate_config_to_dict()` + `runtime_gate_config_from_options()` |

### Modified (3 files)

| File | Change |
|---|---|
| `core/ralph/cli.py` | Added `_build_gate_config_from_args()` helper; `run` subparser gets `--use-agent-council-gates`, `--strict-agent-council-gates`, `--project-type` flags; `_cmd_run` and `_cmd_run_loop` build and pass gate_config |
| `core/ralph/iteration_runner.py` | `IterationRunnerConfig` gets `gate_config` field; `run_iteration()` passes gate params to `QualityGate.evaluate()` |
| `core/ralph/run_executor.py` | `RunExecutorConfig` gets `gate_config` field; gate_config propagated to `IterationRunner` in `__init__` |

### Created Tests (3 files)

| File | Tests |
|---|---|
| `tests/core/ralph/test_agent_council_runtime_gate_config.py` | 16 tests — config model, dict conversion, from_options inference |
| `tests/core/ralph/test_agent_council_runtime_loop_wiring.py` | 16 tests — config in IterationRunner, RunExecutor, QualityGate integration |
| `tests/core/ralph/test_cli_agent_council_gate_flags.py` | 18 tests — CLI parsing, gate config from args, backward compatibility |

## 3. Runtime Gate Config Design

### `RuntimeGateConfig` (frozen dataclass)

| Field | Type | Default | Description |
|---|---|---|---|
| `use_agent_council_gates` | `bool` | `False` | Enable evidence gate enforcement |
| `strict_agent_council_gates` | `bool` | `False` | Blocking gate failures prevent approval |
| `project_type` | `str \| None` | `None` | Project type for council planning |
| `project_goal` | `str \| None` | `None` | Project goal for context building |

### Properties
- `is_enabled` — True when `use_agent_council_gates=True`
- `is_strict` — True when both flags are True

### `runtime_gate_config_from_options()`
- Enforces: `strict_agent_council_gates` implies `use_agent_council_gates`
- Returns a clean `RuntimeGateConfig` from individual flags

## 4. CLI Flags Added

### `fcc-ralph run` subcommand

```bash
# Enable council gate enforcement (warns on gaps)
fcc-ralph run --use-agent-council-gates --project-type full_stack_app

# Strict enforcement (blocking gates prevent approval)
fcc-ralph run --strict-agent-council-gates --project-type landing_page

# Combined with loop
fcc-ralph run --loop --use-agent-council-gates \
    --strict-agent-council-gates --project-type saas_product

# Old behavior unchanged (no flags)
fcc-ralph run --loop
```

New flags:
- `--use-agent-council-gates` — Enable evidence gate enforcement
- `--strict-agent-council-gates` — Strict mode (implies `--use-agent-council-gates`)
- `--project-type` — Project type for council planning context

## 5. Runtime Loop Wiring

### Data Flow

```
CLI flags
    ↓
_build_gate_config_from_args() → RuntimeGateConfig
    ↓
RunExecutorConfig.gate_config / IterationRunnerConfig.gate_config
    ↓
IterationRunner.run_iteration()
    ↓ builds council context if gate_config enabled
    ↓
QualityGate.evaluate(use_agent_council_gates=True, agent_council_context=..., strict_agent_council_gates=True)
    ↓
enforce_runtime_evidence_gates() → EvidenceGateResult
    ↓
should_block_task_approval() → final_status=BLOCKED if True
```

### Key Integration Points

1. **`_build_gate_config_from_args()`** — Module-level helper converts CLI args to `RuntimeGateConfig` or `None`
2. **`RunExecutorConfig.gate_config`** — Stores config; propagated to `IterationRunnerConfig.gate_config` in `__init__`
3. **`IterationRunner.run_iteration()`** — Reads `self._config.gate_config`, builds council context from project_type/goal, passes `use_agent_council_gates` + `strict_agent_council_gates` + `agent_council_context` to `QualityGate.evaluate()`
4. **`QualityGate.evaluate()`** — Already accepts these params (from Phase 9.16F). Runs evidence gates and overrides final_status when blocked.

## 6. QualityGate Behavior with Gates Enabled

| Mode | Behavior |
|---|---|
| Disabled (default) | No change. Old behavior preserved. |
| `use_agent_council_gates=True` (non-strict) | Gates run, warnings added to summary. Blocking gate failures → FAILED (not BLOCKED). |
| `use_agent_council_gates=True` + `strict_agent_council_gates=True` | Gates run. Blocking gate failures → BLOCKED. Task approval prevented. |

## 7. Backward Compatibility Behavior

**Fully backward compatible.**

- Without `--use-agent-council-gates` or `--strict-agent-council-gates` flags, old behavior is preserved.
- `_build_gate_config_from_args()` returns `None` when neither flag is set.
- `IterationRunnerConfig.gate_config` defaults to `None`.
- `RunExecutorConfig.gate_config` defaults to `None`.
- `QualityGate.evaluate()` defaults unchanged (`use_agent_council_gates=False`).
- All existing tests pass without modification.

## 8. Example Commands

### Gated landing page run (non-strict)

```bash
fcc-ralph plan "Build a landing page for a whiteboard business"
fcc-ralph approve --all
fcc-ralph run --use-agent-council-gates --project-type landing_page
```

### Strict gated full-stack run

```bash
fcc-ralph plan "Build a small CRM"
fcc-ralph approve --all
fcc-ralph run --loop --use-agent-council-gates \
    --strict-agent-council-gates --project-type full_stack_app \
    --max-iterations 3
```

### Old behavior (no gates)

```bash
fcc-ralph plan "Standard project"
fcc-ralph approve --all
fcc-ralph run --loop --max-iterations 3
```

## 9. Tests

| Test File | Tests | Coverage |
|---|---|---|
| `test_agent_council_runtime_gate_config.py` | 16 | Config model, dict conversion, from_options, frozen, JSON serialization |
| `test_agent_council_runtime_loop_wiring.py` | 16 | IterationRunnerConfig, RunExecutorConfig, QualityGate integration, echo-only blocking, backward compat |
| `test_cli_agent_council_gate_flags.py` | 18 | CLI parsing, gate config from args, help text, old behavior unchanged |

**Total: 627 council + gate config + wiring + CLI + quality gate + planner tests, all passing.**
Full Ralph suite: 1198/1201 (3 pre-existing failures).

## 10. What Is Intentionally Not Implemented Yet

- **Auto-extraction of project_type from goal** — User must pass `--project-type` on the run command
- **Gate enforcement in pilot mode** — Pilot mode path not yet updated
- **Persistent gate enforcement state** — Gate results are computed each iteration but not stored across sessions
- **Gate-based auto-retry** — Failed gates don't trigger automatic retry loops yet
- **Per-task gate config override** — Global config only

## 11. Remaining Risks

| Risk | Severity | Mitigation |
|---|---|---|
| `--project-type` required on run command for gate enforcement | Low | Clear help text; degrades gracefully without it |
| Council context built on every iteration | Low | Context building is deterministic and fast (~ms) |
| No persistent gate state | Low | Gates are recomputed each iteration; state is in iteration results |

## 12. Whether Phase 9.16H Is Safe to Start

**Yes — Phase 9.16H is safe to start.**

- All 627 tests pass
- 1198/1201 full suite pass (3 pre-existing)
- Backward compatibility verified
- Wire-through is minimal and non-invasive

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
| **9.16G** | **DONE** | **CLI Flags & Runtime Loop Wiring for Agent Council Gates** |
| 9.16H | NEXT | TBD |
| 10 | DEFERRED | TBD |
