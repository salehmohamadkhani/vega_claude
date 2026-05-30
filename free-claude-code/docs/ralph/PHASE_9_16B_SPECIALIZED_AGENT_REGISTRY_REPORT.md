# Phase 9.16B — Specialized Agent Registry Expansion Report

**Date:** 2026-05-30
**Status:** COMPLETE
**Operator:** SEPCC (Ralph Runtime)
**Predecessor:** Phase 9.16A (Agent Council V2 Core Foundation, `ea6baad`)
**Successor:** Phase 9.16C (TBD)

---

## 1. Why Phase 9.16B Exists

Phase 9.16B expands the Agent Council V2 registry from 17 layer-level agents to 56 specialized agents based on the `AGENT_COUNCIL_V2_TAXONOMY.md` specification. Each agent now represents a concrete role with specific inputs, outputs, dependencies, reviewers, fail conditions, and activation triggers — modeling a realistic artificial product-building company.

This phase is **deterministic** — no LLM calls, no network access, no execution. It adds the agent profiles, grouping methods, artifact chain validation, and project-type activation maps that enable richer agent set composition.

## 2. Changes Summary

### Source (3 files modified)

| File | Change |
|---|---|
| `core/ralph/agent_council/models.py` | Expanded `is_strategic` to include Layer 15 (Growth / Analytics) — 1 line |
| `core/ralph/agent_council/registry.py` | Expanded from 17 to 56 agents, added grouping methods, added artifact chain validation, fixed `find_orphan_artifacts` terminal set |
| `core/ralph/agent_council/activation.py` | Updated all 8 project-type agent maps, added project-type rationale, added cyclic-depth guard in `_compute_parallel_groups` |

### Tests (4 files modified/rewritten)

| File | Tests | Status |
|---|---|---|
| `tests/core/ralph/test_agent_council_registry.py` | 56 tests — 56-agent count, uniqueness, 17-layer coverage, grouping, artifact chain | All passing |
| `tests/core/ralph/test_agent_council_activation.py` | 35 tests — all 8 project types, agent assertions, decisions, rationale, parallel groups | All passing |
| `tests/core/ralph/test_agent_council_dependency_graph.py` | 25 tests — graph, topological sort, no cycles, upstream/downstream, parallel groups | All passing |
| `tests/core/ralph/test_agent_council_artifact_contracts.py` | 21 tests — 33 contracts, owner validation, validation errors, lookups | All passing |
| `tests/core/ralph/test_agent_council_models.py` | 18 tests (unchanged) | All passing |
| `tests/core/ralph/test_agent_council_evidence.py` | 29 tests (unchanged) | All passing |
| `tests/core/ralph/test_agent_council_research_map.py` | 12 tests (unchanged) | All passing |
| **Total** | **196 agent council tests, all passing** | |

## 3. Agent Expansion: 17 → 56

### Per-Layer Distribution

| Layer | Name | Agents | IDs |
|---|---|---|---|
| 1 | Strategy & Vision | 3 | chief_vision_officer, chief_product_ethics_officer, strategic_alignment_auditor |
| 2 | Business Strategy | 3 | business_strategist, monetization_strategist, legal_compliance_officer |
| 3 | Market Research | 4 | market_researcher, competitor_analyst, user_researcher, pricing_analyst |
| 4 | Product Management | 3 | product_manager, technical_product_manager, scope_manager |
| 5 | Brand / Content | 4 | brand_strategist, content_strategist, marketing_lead, seo_specialist |
| 6 | UX / UI Design | 5 | ux_designer, ui_designer, design_system_architect, interaction_designer, accessibility_auditor |
| 7 | Architecture | 3 | software_architect, api_architect, data_architect |
| 8 | Frontend Engineering | 3 | senior_frontend_developer, frontend_performance_engineer, mobile_developer |
| 9 | Backend Engineering | 3 | senior_backend_developer, api_developer, integration_engineer |
| 10 | Data Engineering | 3 | database_developer, data_engineer, ml_engineer |
| 11 | Quality Assurance | 4 | qa_engineer, test_automation_engineer, performance_tester, visual_qa_engineer |
| 12 | Security / Compliance | 3 | security_engineer, penetration_tester, dependency_auditor |
| 13 | DevOps / Infrastructure | 3 | devops_engineer, infrastructure_engineer, release_manager |
| 14 | Observability / Reliability | 2 | observability_engineer, sre_engineer |
| 15 | Growth / Analytics | 3 | growth_analyst, analytics_engineer, conversion_optimizer |
| 16 | Support / Operations | 2 | customer_success_manager, documentation_specialist |
| 17 | Orchestration / Arbitration | 5 | orchestrator, project_memory_keeper, final_arbiter, conflict_resolver, quality_gate_keeper |
| **Total** | | **56** | |

## 4. New Registry Methods

| Method | Purpose |
|---|---|
| `list_strategy_agents()` | Return agents from strategic layers (1-5, 15-16) — 22 agents |
| `list_technical_agents()` | Return agents from technical layers (6-14, 17) — 34 agents |
| `list_review_agents()` | Return CHECKPOINT-mode agents |
| `list_implementation_agents()` | Return layers 8-10 (frontend/backend/data) — 9 agents |
| `list_critical_path_agents()` | Return always-activated agents on the critical path |
| `list_always_activated()` | Return ALWAYS-mode agents |
| `find_orphan_artifacts()` | Find produced artifacts with no consumers (excluding terminal outputs) |
| `find_unproduced_inputs()` | Find required inputs not produced by any agent or known external |

## 5. Activation Planner Changes

Updated all 8 project-type agent maps:

| Project Type | Active Agents | Key Additions |
|---|---|---|
| `landing_page` | ~15 | frontend, brand, SEO, conversion |
| `static_site` | ~20 | Content strategy, accessibility_auditor, frontend_performance_engineer |
| `frontend_app` | ~23 | api_architect, interaction_designer, analytics_engineer, growth_analyst |
| `full_stack_app` | ~30+ | Full security (penetration_tester, dependency_auditor), full QA (performance_tester, visual_qa_engineer), observability_engineer, quality_gate_keeper |
| `saas_product` | 48+ | All 5 orchestration agents, monetization, legal_compliance, SRE, growth, support |
| `ai_tool` | ~20 | ml_engineer, chief_product_ethics_officer, performance_tester |
| `internal_tool` | ~14 | Core engineering + QA + security (no brand/market research) |
| `research_project` | ~8 | Minimal: vision, market research, ethics, final arbiter |

Added `get_project_rationale()` for per-type activation reasoning.

## 6. Dependency Cycle Fix

A critical design issue was discovered and resolved: the 56-agent registry had mutual dependency cycles between Layer 7 (Architecture) and Layer 12 (Security):

- `software_architect` depended on `security_engineer` (needing `security_requirements`)
- `security_engineer` depended on `software_architect` (needing `architecture_spec`)
- This created 3 distinct cycles through the graph

**Fix:** Removed `security_engineer` from `software_architect`'s dependencies and `security_requirements` from its `required_inputs`. The real-world flow (architect drafts → security reviews → security produces requirements) is now correctly modeled as a DAG, matching the taxonomy's parallel execution model.

Additionally, a cyclic-depth guard was added to `ActivationPlanner._compute_parallel_groups()` to prevent infinite recursion if cycles are ever introduced.

## 7. Artifact Contracts: 23 → 33

10 new contracts added:
- `user_needs_analysis` (user_researcher)
- `product_roadmap` (product_manager)
- `content_strategy` (content_strategist)
- `data_architecture_spec` (data_architect)
- `accessibility_requirements` (accessibility_auditor)
- `pentest_report` (penetration_tester)
- `dependency_audit_report` (dependency_auditor)
- `visual_QA_report` (visual_qa_engineer)
- `performance_report` (performance_tester)
- `growth_strategy` (growth_analyst)
- `analytics_spec` (analytics_engineer)
- `observability_spec` (observability_engineer)
- `ethics_audit_report` (chief_product_ethics_officer)
- `compliance_requirements` (legal_compliance_officer)

## 8. Test Coverage

- **196 tests total** across 7 test files — all passing
- No LLM calls, no network access, deterministic
- Tests cover: agent count, uniqueness, layers, lookups, grouping, artifact chain validation, dependency cycles, topological sort, parallel groups, project types, activation decisions, contract validation

## 9. What Phase 9.16B Does NOT Include

- No browser automation (no Playwright)
- No multi-agent execution
- No LLM calls
- No network access
- No Phase 10 work
- No modification to `/opt/vega-cloud/fcc-upstream`
- No port 8082 changes
- No research repo code execution

## 10. Phase 9.16B Is Complete

All 10 steps from the phase spec are done:
- ✅ Step 1: Route and repo state verified
- ✅ Step 2: Existing foundation files read
- ✅ Step 3: Registry expanded from 17 to 56 agents
- ✅ Step 4: Registry grouping and profile validation added
- ✅ Step 5: Activation planner updated for richer agent sets
- ✅ Step 6: Research mapping strengthened for expanded agents
- ✅ Step 7: Comprehensive tests written (196 total, all passing)
- ✅ Step 8: This report created
- ✅ Step 9: py_compile and ruff pass cleanly
- ✅ Step 10: Commit and push
