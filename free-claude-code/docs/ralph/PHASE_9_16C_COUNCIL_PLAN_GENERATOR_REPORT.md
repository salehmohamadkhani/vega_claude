# Phase 9.16C — Council Plan Generator Integration with Ralph Runtime

**Date:** 2026-05-30
**Status:** COMPLETE
**Operator:** SPC (Ralph Runtime)
**Predecessor:** Phase 9.16B (Specialized Agent Registry Expansion, `df01c57`)
**Successor:** Phase 9.16D (TBD)

---

## 1. Why Phase 9.16C Exists

Phase 9.16C integrates Agent Council V2 into Ralph Runtime at the planning layer. Before this phase, Agent Council V2 provided activation planning for 8 project types but lacked a structured "Council Plan" — a single document answering all 10 planning questions Ralph needs before execution.

This phase makes VegaClaw capable of generating a deterministic Council Plan that answers:
1. What project type is this?
2. Which agents should activate?
3. Which agents are on the critical path?
4. Which agents can run in parallel?
5. Which artifacts are required?
6. Which artifacts are missing?
7. Which research references are relevant?
8. Which evidence must be collected?
9. Which risks should block execution?
10. What should Ralph do next?

All planning is **deterministic** — no LLM calls, no network access, no agent execution.

## 2. Files Created/Modified

### Created (4 files)

| File | Purpose |
|---|---|
| `core/ralph/agent_council/plan.py` | Council Plan models: CouncilPlanRequest, CouncilPlanResult, CouncilPlanAgentNode, CouncilPlanArtifactNode, CouncilPlanRisk, CouncilPlanEvidenceRequirement, CouncilPlanResearchReference, CouncilPlanNextAction, RiskSeverity |
| `core/ralph/agent_council/plan_generator.py` | Deterministic plan generator: CouncilPlanGenerator class + generate_council_plan() factory |
| `core/ralph/agent_council/runtime_adapter.py` | Ralph Runtime adapter: build_council_plan_for_goal(), summarize_council_plan(), council_plan_to_context() |
| `docs/ralph/PHASE_9_16C_COUNCIL_PLAN_GENERATOR_REPORT.md` | This report |

### Created Tests (4 files)

| File | Tests |
|---|---|
| `tests/core/ralph/test_agent_council_plan.py` | 22 tests — all models, enums, immutability, validation |
| `tests/core/ralph/test_agent_council_plan_generator.py` | 32 tests — 8 project types, unknown type handling, strict mode, agent overrides, research map, cycle detection |
| `tests/core/ralph/test_agent_council_runtime_adapter.py` | 17 tests — context dict, summary, serialization, determinism |
| `tests/core/ralph/test_cli_council_plan.py` | 18 tests — CLI flags, JSON output, all project types, determinism |

### Modified (1 file)

| File | Change |
|---|---|
| `core/ralph/cli.py` | Added `council-plan` subcommand with `--project-type`, `--goal`, `--strict`, `--json`, `--exclude-agent`, `--include-agent` flags + `_cmd_council_plan()` handler |

## 3. Council Plan Model Design

### CouncilPlanRequest

Minimum fields:
- `project_goal: str` — Human-readable goal description
- `project_type: str` — Optional type hint (empty = infer from goal)
- `constraints: tuple[str, ...]` — Project constraints
- `available_artifacts: tuple[str, ...]` — Pre-existing artifacts
- `requested_agents: tuple[str, ...]` — Force-include agents
- `excluded_agents: tuple[str, ...]` — Force-exclude agents
- `research_root: str` — Path to research corpus root (empty = use default)
- `strict_mode: bool` — If True, missing critical artifacts block execution

### CouncilPlanResult

Minimum fields:
- `project_type: str`
- `project_goal: str`
- `active_agents: tuple[CouncilPlanAgentNode, ...]` — Agents to activate with phase/role/deps
- `critical_path: tuple[str, ...]` — Longest dependency chain
- `parallel_groups: tuple[tuple[str, ...], ...]` — Concurrent execution groups
- `required_artifacts: tuple[CouncilPlanArtifactNode, ...]` — Artifacts with status/criticality
- `missing_artifacts: tuple[str, ...]` — Artifacts without a producer
- `artifact_contracts: tuple[str, ...]` — Contract IDs in scope
- `research_references: tuple[CouncilPlanResearchReference, ...]`
- `evidence_requirements: tuple[CouncilPlanEvidenceRequirement, ...]`
- `risks: tuple[CouncilPlanRisk, ...]`
- `next_action: CouncilPlanNextAction`
- `is_ready_to_execute: bool`
- `summary: str` — Human-readable one-line summary
- `warnings: tuple[str, ...]` — Non-blocking issues
- `total_phases: int`
- `total_active_agents: int`

Properties:
- `is_blocked` — True when plan cannot execute
- `next_action_label` — Human-readable next action description
- `agent_count_by_layer` — Dict of layer→count

### Next Action Values

| Value | Meaning |
|---|---|
| `ready_for_runtime_planning` | Plan is complete; proceed to task planning |
| `needs_missing_artifacts` | Critical artifacts missing; must be produced first |
| `needs_scope_clarification` | Project goal is too vague; needs more detail |
| `blocked_by_dependency_cycle` | Agent dependency cycle detected |
| `blocked_by_unknown_project_type` | Project type not in known set (strict mode only) |
| `blocked_by_missing_required_agent` | Required agents (CVO, orchestrator, PM) not active |

## 4. Plan Generator Design

### CouncilPlanGenerator

The generator uses all existing Agent Council infrastructure:
- **Agent Registry** (56 agents, 17 layers) — for agent lookup and validation
- **Artifact Contracts** (39 contracts) — for artifact validation and ownership
- **Activation Planner** (8 project types) — for agent selection and parallel groups
- **Dependency Graph** — for cycle detection, topological sort, critical path
- **Research Map** — for research reference collection (when available)
- **Evidence Model** — for basic evidence requirement generation

### Generation Flow

1. Resolve project type (explicit or inferred from goal keywords)
2. Detect dependency cycles (block if found)
3. Get activation plan from ActivationPlanner
4. Apply agent inclusion/exclusion overrides
5. Check required agents in strict mode
6. Build agent nodes with phases and dependencies
7. Build artifact nodes with status (pending/available) and criticality
8. Identify truly missing artifacts (no producer in active set)
9. Generate risks (blocking/high/medium/low)
10. Collect research references from research map
11. Generate evidence requirements
12. Determine next action
13. Build critical path
14. Build human-readable summary
15. Collect relevant artifact contract IDs

### Project Type Inference

When `project_type` is empty, keyword-based inference from the goal string:
- `saas`, `subscription`, `multi-tenant` → `saas_product`
- `ai`, `ml`, `machine learning`, `llm` → `ai_tool`
- `landing page`, `landing` → `landing_page`
- `static site`, `blog` → `static_site`
- `spa`, `single page app` → `frontend_app`
- `internal tool`, `admin tool` → `internal_tool`
- `research`, `study` → `research_project`
- `full stack`, `web app`, `crm`, `dashboard` → `full_stack_app` (default)

More specific types are checked first to avoid false matches.

### Risk Generation

- **Missing critical artifacts** (strict mode only) — BLOCKING
- **Unknown project type** (strict mode only) — BLOCKING
- **SaaS complexity** — MEDIUM (50+ agents across all 17 layers)
- **AI/ML ethics** — HIGH (ethics audit required)
- **Warnings** — LOW (informational)

## 5. Runtime Adapter Design

Three functions provide a shallow integration layer for Ralph Runtime:

### `build_council_plan_for_goal(goal, project_type="", strict_mode=False)`

Simplest entry point. Constructs a minimal `CouncilPlanRequest` and delegates to the generator.

```python
plan = build_council_plan_for_goal("Build a SaaS CRM")
# plan.is_ready_to_execute → True
# plan.total_active_agents → 53
# plan.next_action → READY_FOR_RUNTIME_PLANNING
```

### `summarize_council_plan(plan) -> str`

Produces a human-readable multi-line summary with:
- Project goal and type
- Ready/blocked status and next action
- Active agents grouped by layer
- Phase and critical path counts
- Required and missing artifacts
- Risks with severity labels
- Research references and evidence counts
- Warnings

### `council_plan_to_context(plan) -> dict[str, object]`

Converts plan to a JSON-serializable dict suitable for Ralph's planning context. Includes all fields as structured lists/dicts rather than dataclass instances.

## 6. CLI Integration Status

### Status: IMPLEMENTED

New subcommand: `fcc-ralph council-plan`

```bash
# Basic usage
fcc-ralph council-plan --project-type full_stack_app --goal "Build a small CRM"

# JSON output
fcc-ralph council-plan --project-type landing_page --goal "Build a landing page" --json

# Strict mode
fcc-ralph council-plan --project-type full_stack_app --goal "Build a CRM" --strict

# Agent overrides
fcc-ralph council-plan --project-type full_stack_app --goal "Test" \
    --exclude-agent brand_strategist --include-agent legal_compliance_officer

# With research root
fcc-ralph council-plan --project-type ai_tool --goal "Build an AI chatbot" \
    --research-root /opt/vega-cloud/research
```

Flags:
- `--project-type` — Project type (landing_page, full_stack_app, saas_product, etc.)
- `--goal` — Project goal description
- `--strict` — Enable strict mode
- `--json` — Output in JSON format
- `--exclude-agent` — Agent ID to exclude (repeatable)
- `--include-agent` — Agent ID to include (repeatable)
- `--research-root` — Path to research corpus root

Exit codes:
- `0` — Plan is ready to execute
- `1` — Plan is blocked

## 7. How This Connects Agent Council to Ralph Runtime

Before Phase 9.16C:
- Agent Council existed in isolation
- ActivationPlanner could select agents for a project type
- No structured plan output for Ralph to consume

After Phase 9.16C:
- Ralph can call `build_council_plan_for_goal()` before `fcc-ralph plan`
- The Council Plan informs task planning with:
  - Which agents are active → maps to Ralph task roles
  - Critical path → task ordering constraints
  - Parallel groups → concurrent task scheduling
  - Missing artifacts → pre-flight checklist
  - Risks → quality gate criteria
  - Evidence requirements → verification targets
  - Research references → context for agent execution

The integration is shallow by design — Ralph's existing `plan/review/approve/run` loop is unchanged. The Council Plan is a planning-time advisory that Ralph can consume via the context dict.

## 8. Example Plans

### landing_page

```
Project Type: landing_page
Active Agents: 16 (Layers 1,3,4,5,6,8,11,13,15,17)
Phases: 10
Critical Path: chief_vision_officer → product_manager → ... → final_arbiter
Missing Artifacts: 0
Next Action: ready_for_runtime_planning
Ready: Yes
```

No backend, database, or security agents. Focused on brand, UX/UI, frontend, SEO, and deployment.

### full_stack_app

```
Project Type: full_stack_app
Active Agents: 39 (Layers 1-17)
Phases: 12
Critical Path: chief_vision_officer → product_manager → software_architect → ... → final_arbiter
Required Artifacts: business_brief, product_requirements_doc, architecture_spec, API_contract, database_schema_spec, security_requirements, test_plan, deployment_plan, etc.
Missing Artifacts: 0
Next Action: ready_for_runtime_planning
Ready: Yes
```

All core engineering layers: frontend, backend, database, QA, security, DevOps, observability, growth.

### saas_product

```
Project Type: saas_product
Active Agents: 53 (all 17 layers)
Phases: 12
Critical Path: chief_vision_officer → ... → final_arbiter (long)
Additional agents: monetization, legal compliance, SRE, customer success, documentation, quality gates
Risks: SaaS complexity (MEDIUM)
Next Action: ready_for_runtime_planning
Ready: Yes
```

Maximum coverage: all 17 layers with monetization, legal compliance, growth, support, SRE, and full orchestration with quality gates.

## 9. Tests Added/Updated

| Test File | Tests | Coverage |
|---|---|---|
| `test_agent_council_plan.py` | 22 | All models, enums, immutability, next_action_label, agent_count_by_layer |
| `test_agent_council_plan_generator.py` | 32 | 8 project types, unknown type fallback, inference from goal, strict/non-strict modes, agent overrides, research map, cycle detection, plan structure, no-network verification, generator class |
| `test_agent_council_runtime_adapter.py` | 17 | Context dict keys, agent/artifact serialization, summary content, determinism, performance |
| `test_cli_council_plan.py` | 18 | All flags, JSON output, all project types, strict mode, help text, determinism |

**Total: 89 new tests, all passing.**

Combined Agent Council test suite: **321 tests, all passing.**

Key proofs:
- [x] unknown project type falls back (non-strict) or blocks (strict)
- [x] landing_page excludes backend/database by default
- [x] full_stack_app includes frontend/backend/database/security/QA/DevOps
- [x] saas_product includes growth, analytics, support, security, production readiness
- [x] strict mode blocks missing critical artifacts
- [x] non-strict mode allows execution with warnings
- [x] missing research root does not crash
- [x] research references attach when indexes exist
- [x] dependency cycles block execution
- [x] runtime adapter returns a valid context dict
- [x] summary is human-readable with all required sections
- [x] no LLM/API/network calls occur
- [x] CLI command works with all flag combinations
- [x] Plan generation is deterministic (same input → same output)

## 10. What Is Intentionally Not Implemented Yet

- **Deep Ralph Runtime loop integration** — The adapter provides context; Ralph's existing loop is unchanged. Phase 9.16D or later will integrate the Council Plan into the actual execution flow.
- **Live agent execution** — The plan is static and deterministic. Phase 10+ will activate agents.
- **Dynamic replanning** — Plans are generated once per request. Mid-execution replanning is a future feature.
- **Research corpus deep integration** — Research references are best-effort reads from index files. Deep research repo analysis belongs in later phases.
- **Quality gate enforcement** — Gate status tracking is modeled but not enforced at the planning layer.
- **Multi-project portfolio planning** — Single project only.

## 11. Remaining Risks

| Risk | Severity | Mitigation |
|---|---|---|
| Ralph loop doesn't consume Council Plan yet | Low | Phase 9.16D will integrate |
| Research indexes may be stale or missing | Low | Graceful degradation (empty results, no crash) |
| 53 agents for SaaS may be overwhelming | Low | Parallel groups keep execution manageable; not all agents produce output simultaneously |
| CLI `--json` requires `--json` on both parent and subparser for flexibility | Low | Handled; `council-plan` subparser accepts its own `--json` |

## 12. Whether Phase 9.16D Is Safe to Start

**Yes — Phase 9.16D is safe to start.**

- All 321 Agent Council tests pass
- Full Ralph test suite: 939 pass (2 pre-existing failures in test_execution_guard.py unrelated)
- No regressions in existing functionality
- Council Plan generator is deterministic and well-tested
- Integration is shallow (runtime adapter only)
- CLI command is self-contained

---

## Phase Roadmap

| Phase | Status | Description |
|---|---|---|
| 9.16A | DONE | Agent Council V2 Core Foundation |
| 9.16B | DONE | Specialized Agent Registry Expansion |
| **9.16C** | **DONE** | **Council Plan Generator Integration with Ralph Runtime** |
| 9.16D | NEXT | TBD |
| 10 | DEFERRED | TBD |
