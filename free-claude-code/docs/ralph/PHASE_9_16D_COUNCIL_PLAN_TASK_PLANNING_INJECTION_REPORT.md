# Phase 9.16D — Council Plan Task Planning Injection Report

**Date:** 2026-05-30
**Status:** COMPLETE
**Operator:** SPC (Ralph Runtime)
**Predecessor:** Phase 9.16C (Council Plan Generator Integration, `353c7e5`)
**Successor:** Phase 9.16E (TBD)

---

## 1. Why Phase 9.16D Exists

Phase 9.16C made VegaClaw capable of generating deterministic Council Plans. Phase 9.16D connects those plans to Ralph's task planning layer.

Before this phase, Ralph's `TaskPlanner` generated tasks purely from heuristic keyword matching on the project goal. Now Ralph can optionally consume Agent Council V2 plans to produce richer tasks with agent-aware metadata, artifact references, evidence requirements, and risk gates.

The integration is **shallow and backward-compatible** — when no council context is provided, the planner behaves identically to before.

## 2. Files Created/Modified

### Created (2 files)

| File | Purpose |
|---|---|
| `core/ralph/agent_council/planning_context.py` | Context builder + hint extractors (5 functions) |
| `core/ralph/agent_council/planner_integration.py` | Bridge to Ralph planner + prompt formatter (2 functions) |

### Modified (2 files)

| File | Change |
|---|---|
| `core/ralph/planner.py` | TaskPlan gets `agent_council_context` field; `plan()`, `generate_questions()`, `build_project_spec()`, `generate_tasks()` accept optional council context; `_enrich_tasks_with_council_context()` method adds council-aware ACs/KPIs |
| `core/ralph/cli.py` | `plan` subcommand gets `--project-type`, `--use-agent-council`, `--strict-council`, `--json` flags |

### Created Tests (2 files)

| File | Tests |
|---|---|
| `tests/core/ralph/test_agent_council_planning_context.py` | 22 tests — context builder, summarizer, all 4 extractors, determinism |
| `tests/core/ralph/test_agent_council_planner_integration.py` | 26 tests — 3 project types, prompt formatting, backward compat, enrichment, determinism |

## 3. Planning Context Design

### `build_planning_context_from_council_plan(plan) -> dict`

Converts a `CouncilPlanResult` into a dict with 20 keys:
- Identity: `council_plan_available`, `project_type`, `project_goal`, `is_ready_to_execute`, `next_action`, `next_action_label`
- Agents: `active_agent_count`, `total_phases`, `active_agents` (list of agent dicts)
- Structure: `critical_path`, `parallel_groups`
- Artifacts: `required_artifacts` (list of artifact dicts with status/criticality), `missing_artifact_ids`, `artifact_contract_ids`
- Research & Evidence: `research_references`, `evidence_requirements`
- Risks: `risks` (with severity, affected agents/artifacts, mitigation)
- Meta: `warnings`, `summary`

### Hint Extractors

| Function | Purpose |
|---|---|
| `extract_agent_task_hints(ctx)` | Agent → artifact production hints |
| `extract_artifact_task_hints(ctx)` | Artifact ownership and criticality |
| `extract_evidence_task_hints(ctx)` | Evidence collection requirements |
| `extract_risk_task_hints(ctx)` | Risk gates with mitigation |

## 4. Planner Integration Strategy

### TaskPlanner Changes (backward compatible)

| Method | Change |
|---|---|
| `plan()` | New optional `agent_council_context: dict \| None = None` parameter; passes through to all sub-methods |
| `generate_questions()` | Adds council-aware questions about missing artifacts and blocking risks when context is available |
| `build_project_spec()` | Enriches summary with council agent count/type; adds council-derived risks; maps council layers (8-15) to target areas |
| `generate_tasks()` | New `_enrich_tasks_with_council_context()` adds council-aware acceptance criteria and KPIs to architecture, implementation, and verification tasks |

### TaskPlan Changes

New optional field: `agent_council_context: dict[str, object] | None = None`

### Enrichment Logic

When council context is available, tasks get enriched:

**Architecture task:**
- AC: "Architecture document accounts for N Agent Council agents"
- KPI: "Architecture covers N council-defined agent domains"

**Implementation task:**
- AC: Agent → artifact hints (sample of top 3 producers)
- AC: Missing artifact references
- AC: Blocking risk count + mitigation requirement
- KPI: Missing artifacts resolved, blocking risks mitigated

**Verification task:**
- AC: Evidence collection counts
- AC: Critical artifact verification references
- KPI: Evidence/critical artifact coverage

## 5. CLI Integration Status

### Status: IMPLEMENTED

New flags on `fcc-ralph plan`:

```bash
# Basic council-enabled planning
fcc-ralph plan --use-agent-council --project-type full_stack_app "Build a CRM"

# Strict council mode
fcc-ralph plan --use-agent-council --project-type saas_product --strict-council "Build a SaaS"

# JSON output with council context
fcc-ralph plan --use-agent-council --project-type landing_page --json "Build a landing page"

# Standard planning (no council) — unchanged
fcc-ralph plan "Standard project goal"
```

Flags:
- `--project-type` — Project type for Agent Council (landing_page, full_stack_app, saas_product, etc.)
- `--use-agent-council` — Enable council context injection
- `--strict-council` — Strict mode (missing artifacts block)
- `--json` — JSON output

### Backward Compatibility

**Fully backward compatible.** All existing `fcc-ralph plan` commands work identically. Without `--use-agent-council`, the planner operates exactly as before — no new questions, no enrichment, no spec changes. The council context is `None` and the new code paths are skipped.

## 6. Example Injected Context

### landing_page

```
Spec Summary: "Project: Build a landing page. Covers ui.
               Agent Council: 16 agents activated for project type 'landing_page'."
Target Areas: ['ui', 'frontend_engineering', 'qa_testing', 'devops_infrastructure', 'testing']
Council Questions: (none — no missing artifacts for landing_page)
Implementation AC: "Implement artifacts per Agent Council plan: ..."
```

### full_stack_app

```
Spec Summary: "Project: Build a CRM. Covers ui.
               Agent Council: 39 agents activated for project type 'full_stack_app'."
Target Areas: ['ui', 'frontend_engineering', 'backend_engineering', 'database_data',
               'qa_testing', 'security_compliance', 'devops_infrastructure',
               'observability', 'growth_analytics', 'testing']
Implementation AC: Agent→artifact hints, council risk mitigation
```

## 7. What Is Intentionally Not Implemented Yet

- **Live multi-agent execution** — Agents are planned, not executed (Phase 10+)
- **Dynamic replanning** — Plans are generated once (mid-execution replanning is future)
- **Quality gate enforcement** — Gates are listed as KPIs, not actively enforced
- **Research corpus deep integration** — References are passive
- **Automatic task decomposition from council plan** — The planner still produces 4 standard tasks + enrichment; full agent-to-task mapping is deferred

## 8. Remaining Risks

| Risk | Severity | Mitigation |
|---|---|---|
| Council enrichment adds noise without execution | Low | Enrichment is additive and non-blocking; existing tasks are preserved |
| Large SaaS plans (53 agents) create verbose specs | Low | Only agent count is in the summary; detailed agent lists are in the context dict |
| No feedback loop from execution back to council | Low | Phase 9.16E+ will close this loop |

## 9. Tests Updated

| Test Suite | Tests | Status |
|---|---|---|
| `test_agent_council_planning_context.py` | 22 | All passing |
| `test_agent_council_planner_integration.py` | 26 | All passing |
| Existing Agent Council tests | 321 | All passing |
| Existing Planner tests | 26 | All passing |
| Existing CLI tests | 50+ | All passing |
| Full Ralph test suite | 988/990 passing | 2 pre-existing (Windows-path) |

**Total: 396 Agent Council + Planner + CLI tests, all passing.**

Key proofs:
- [x] Planning context is generated from a CouncilPlanResult
- [x] Context includes active agents and artifacts
- [x] Context includes evidence requirements and risk hints
- [x] All 4 extract functions produce valid output
- [x] Format function produces concise prompt text
- [x] Planner integration returns graceful fallback on invalid project type
- [x] Existing planner behavior is unchanged when Agent Council is disabled
- [x] landing_page context excludes backend/database by default
- [x] full_stack_app context includes frontend/backend/database/security/QA/DevOps
- [x] saas_product includes growth, analytics, support, production readiness
- [x] Planner produces agent-aware tasks with council-enriched ACs/KPIs
- [x] CLI `--use-agent-council` + `--project-type` work end-to-end
- [x] No LLM/API/network calls occur

## 10. Whether Phase 9.16E Is Safe to Start

**Yes — Phase 9.16E is safe to start.**

- All 396 council/planner/CLI tests pass
- 988/990 full suite pass (2 pre-existing)
- Backward compatibility verified — planner works identically without council
- CLI integration is self-contained and non-breaking
- Integration is shallow (adapter + optional enrichment)

---

## Phase Roadmap

| Phase | Status | Description |
|---|---|---|
| 9.16A | DONE | Agent Council V2 Core Foundation |
| 9.16B | DONE | Specialized Agent Registry Expansion |
| 9.16C | DONE | Council Plan Generator Integration |
| **9.16D** | **DONE** | **Council Plan Task Planning Injection** |
| 9.16E | NEXT | TBD |
| 10 | DEFERRED | TBD |
