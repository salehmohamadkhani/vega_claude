# Phase 9.16A — Agent Council V2 Core Foundation Report

**Date:** 2026-05-30
**Status:** COMPLETE
**Operator:** SEPCC (Ralph Runtime)
**Predecessor:** Phase 9.15D (Security Corpus Expansion)
**Successor:** Phase 9.16B (Agent Council V2 — agent specialization, TBD)

---

## 1. Why Phase 9.16A Exists

Phase 9.16A implements the deterministic foundation for Agent Council V2: the data models, registry, dependency graph, artifact contracts, activation planner, research map, and evidence model. These are the building blocks that specialized agents and multi-agent workflows will use.

This phase is **pure data modeling** — no LLM calls, no network access, no multi-agent execution. It creates the scaffolding that later phases (9.16B+) will build upon.

## 2. Files Created

### Source (8 files)

| File | Purpose |
|---|---|
| `core/ralph/agent_council/__init__.py` | Package init |
| `core/ralph/agent_council/models.py` | Data models: AgentProfile, AgentLayer, ArtifactContract, AgentCouncilPlan, EvidenceItem, ResearchReference (+6 enums) |
| `core/ralph/agent_council/registry.py` | 17-agent default registry with validation and lookup by ID, layer, artifact, input |
| `core/ralph/agent_council/dependency_graph.py` | Graph construction, topological sort, cycle detection, upstream/downstream, parallel groups, blocked-by-missing |
| `core/ralph/agent_council/artifact_contracts.py` | 23 built-in artifact contracts with validation, owner/consumer mapping |
| `core/ralph/agent_council/activation.py` | Deterministic planner for 8 project types (landing_page through research_project) |
| `core/ralph/agent_council/research_map.py` | Lightweight reader for research indexes under `/opt/vega-cloud/research/indexes/` |
| `core/ralph/agent_council/evidence.py` | Evidence item creation, validation, collection, and summarization |

### Tests (6 files, 142 tests)

| File | Tests |
|---|---|
| `tests/core/ralph/test_agent_council_models.py` | 18 tests — all models, enums, immutability, validation |
| `tests/core/ralph/test_agent_council_registry.py` | 22 tests — default registry, validation, lookups, 17-layer coverage |
| `tests/core/ralph/test_agent_council_dependency_graph.py` | 25 tests — graph, topological sort, cycles, upstream/downstream, parallel groups |
| `tests/core/ralph/test_agent_council_artifact_contracts.py` | 14 tests — 23 contracts validated, owner/consumer lookup, validation errors |
| `tests/core/ralph/test_agent_council_activation.py` | 22 tests — all 8 project types, should_activate decisions, parallel groups |
| `tests/core/ralph/test_agent_council_research_map.py` | 12 tests — availability, loading, queries, graceful degradation, temp indexes |
| `tests/core/ralph/test_agent_council_evidence.py` | 29 tests — creation, validation, collector, rejection, summarization |
| **Total** | **142 tests, all passing** |

## 3. Registry Design

### 17 Layer-Level Agents

| Layer | Agent ID | Activation | Dependencies |
|---|---|---|---|
| 1 | `executive_vision_agent` | ALWAYS | None |
| 2 | `business_strategy_agent` | TRIGGERED | market_research_agent |
| 3 | `market_research_agent` | TRIGGERED | executive_vision_agent |
| 4 | `product_manager_agent` | ALWAYS | executive_vision_agent, market_research_agent |
| 5 | `brand_content_agent` | TRIGGERED | market_research_agent |
| 6 | `ux_ui_product_design_agent` | TRIGGERED | product_manager_agent |
| 7 | `software_architect_agent` | ALWAYS | product_manager_agent |
| 8 | `senior_frontend_developer_agent` | TRIGGERED | ux_ui_product_design_agent, software_architect_agent |
| 9 | `senior_backend_developer_agent` | TRIGGERED | software_architect_agent, database_developer_agent |
| 10 | `database_developer_agent` | TRIGGERED | software_architect_agent |
| 11 | `qa_verification_agent` | ALWAYS | ux_ui_product_design_agent, software_architect_agent |
| 12 | `security_compliance_agent` | ALWAYS | software_architect_agent |
| 13 | `devops_infrastructure_agent` | TRIGGERED | frontend + backend developers |
| 14 | `observability_reliability_agent` | TRIGGERED | devops_infrastructure_agent |
| 15 | `growth_analytics_agent` | TRIGGERED | brand_content_agent |
| 16 | `support_operations_agent` | TRIGGERED | product_manager_agent |
| 17 | `final_arbiter_agent` | CHECKPOINT | qa, security, devops |

### Registry Validation

- **Duplicate agent IDs** → RegistryValidationError
- **Self-dependencies** → RegistryValidationError
- **Unknown dependency IDs** → RegistryValidationError
- **Unknown reviewer IDs** → RegistryValidationError
- **Invalid layer number** (not 1–17) → RegistryValidationError

## 4. Dependency Graph Design

Deterministic graph utilities with no external dependencies:

| Function | Purpose |
|---|---|
| `build_graph()` | Adjacency map: agent_id → downstream consumers |
| `build_reverse_graph()` | Reverse map: agent_id → upstream dependencies |
| `topological_sort()` | Kahn's algorithm — agents ordered by dependency depth |
| `detect_cycles()` | DFS-based cycle detection — empty list = no cycles |
| `upstream_dependencies()` | All transitive agents this agent needs |
| `downstream_consumers()` | All transitive agents that depend on this agent |
| `find_parallel_groups()` | Agents grouped by dependency depth (same depth = parallelizable) |
| `find_parallelizable()` | Agents ready to run given completed set |
| `blocked_by_missing()` | Required inputs not yet available |

## 5. Artifact Contract Design

23 built-in contracts based on `AGENT_COUNCIL_V2_ARTIFACT_CONTRACTS.md`:

| Group | Contracts |
|---|---|
| Vision & Strategy | `business_brief`, `strategic_direction` |
| Market Research | `market_research_report`, `competitor_map`, `target_personas`, `user_journey_maps` |
| Product Management | `product_requirements_doc`, `user_stories`, `acceptance_criteria` |
| Brand & Design | `brand_strategy`, `brand_book` |
| UX / UI | `UX_flow_map`, `design_system`, `UI_spec` |
| Architecture | `architecture_spec`, `API_contract`, `database_schema_spec` |
| Security | `security_requirements` |
| QA | `test_plan`, `QA_report` |
| Deployment | `deployment_plan`, `release_readiness_report` |
| Final | `final_arbiter_decision` |

Each contract defines: owner agent, required_fields, consumers, validation_method, pass_criteria, fail_criteria.

### Contract Validation

- Required fields must be non-empty
- Owner agent must exist in registry (when registry is provided)
- Consumer agents must exist in registry (when registry is provided)
- At least one consumer must be defined
- Pass/fail criteria must be defined

## 6. Activation Planner Design

Supports 8 project types with deterministic agent activation:

| Project Type | Agents Activated | Key Characteristic |
|---|---|---|
| `landing_page` | 10 | No backend, no DB |
| `static_site` | 11 | Frontend + security |
| `frontend_app` | 12 | SPA with API dependency |
| `full_stack_app` | 15 | Frontend + backend + DB |
| `saas_product` | 17 | All layers including growth + support |
| `ai_tool` | 11 | ML-capable but minimal |
| `internal_tool` | 10 | No brand, no market research |
| `research_project` | 4 | Vision + research + PM + arbiter |

Key validation rules verified by tests:
- `full_stack_app` activates frontend, backend, database, security, QA, DevOps
- `landing_page` does NOT require backend/database
- `internal_tool` skips brand and market research
- All project types include executive_vision_agent and final_arbiter_agent
- `saas_product` is the most comprehensive (17 agents)

## 7. Research Corpus Integration Point

The `ResearchMap` class reads indexes from `/opt/vega-cloud/research/indexes/`:

- Parses `AGENT_TO_REPO_INDEX.md` for agent→repo mappings
- Parses `PATTERN_INDEX.md` for pattern→repo mappings
- Provides `find_for_agent()`, `find_for_layer()`, `find_patterns()` queries
- Degrades gracefully if research root is missing (returns empty tuples/dicts)
- Never clones repos, never runs repo code, no network access

## 8. Evidence Model

Simple evidence utilities that will later connect to QualityGate:

- `create_evidence()` — validated creation with mandatory source_path + claim
- `validate_evidence()` — checks for empty source, claim, or type
- `reject_unsupported_claims()` — filters invalid evidence items
- `EvidenceCollector` — collects, validates, summarizes by type/agent/quality
- `attach_to_decision()` — filters and attaches evidence to agent decisions

## 9. Tests Added

```
142 passed in 2.19s
```

All 6 test files run without LLM calls, API access, or network access.

### What's Tested

- Registry loads with 17 agents across all 17 layers
- No duplicate agent IDs
- Dependencies are valid (no unknown references)
- Dependency graph topological sort works correctly (deps before consumers)
- Cycle detection correctly identifies cycles
- Artifact contracts validate (all 23 have required fields, consumers, pass/fail criteria)
- Activation planner returns expected agents for each project type
- `full_stack_app` includes frontend + backend + database + security + QA + DevOps
- `landing_page` excludes backend and database
- Research map handles missing research root gracefully
- Evidence model rejects empty claims/sources
- No LLM/API/network calls needed for any foundation test

## 10. What Is Intentionally NOT Implemented Yet

| Feature | Why Deferred | Target Phase |
|---|---|---|
| Full 56-agent taxonomy | Foundation uses 17 layer-level agents; detailed agents added later | 9.16B |
| LLM-powered agent execution | This phase is data models only | 9.16C+ |
| Multi-agent workflow execution | Planning layer first, execution later | 9.16D+ |
| QualityGate integration | Evidence model exists but not wired to QualityGate | 9.16D+ |
| Artifact content generation | Contracts define structure; content is agent-produced | 9.16C+ |
| Agent Council Runtime (Orchestrator loop) | Needs execution engine | 9.16D+ |
| Playwright / browser automation | Phase 10 | Phase 10 |
| Admin UI | Deferred | Deferred |

## 11. Remaining Risks

| Risk | Severity | Mitigation |
|---|---|---|
| Registry covers only 17 of 56 taxonomy agents | 🟡 Medium | Expandable design — `AgentRegistry(agents=custom_tuple)` accepts any agent list |
| Activation planner is static (8 project types) | 🟡 Medium | Planner can be extended with new project types and dynamic selection logic |
| Research map parser is simple regex-based | 🟢 Low | Graceful degradation; parser can be upgraded without API changes |
| No artifact persistence yet | 🟢 Low | Artifact contracts define structure; persistence is an execution-layer concern |
| Evidence model not yet connected to QualityGate | 🟢 Low | Collector is standalone; wire-up is a single integration step |

## 12. Is Phase 9.16B Safe to Start?

**✅ YES.** The core foundation is complete and tested.

- 142 tests pass
- All 8 source modules compile cleanly
- Ruff checks pass with zero errors
- Registry, dependency graph, artifact contracts, activation planner, research map, and evidence model are all functional
- Zero regressions in existing codebase (2 pre-existing Windows-only failures in `test_execution_guard.py`)

**Recommended Phase 9.16B scope:** Expand the registry from 17 to 56 agents based on the full taxonomy, add specialized agent profiles, and implement the initial Orchestrator decision pipeline.
