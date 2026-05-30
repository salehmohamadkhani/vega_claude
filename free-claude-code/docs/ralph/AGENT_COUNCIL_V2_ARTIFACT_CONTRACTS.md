# Agent Council V2 — Artifact Contracts

**Date:** 2026-05-30
**Status:** Design specification
**Purpose:** Define the shared artifacts that agents pass between each other with validation criteria

---

## Overview

Artifacts are the formal contracts that agents use to communicate. Each artifact has a defined owner, schema, consumer agents, and pass/fail criteria. Artifacts are versioned and tracked by the Project Memory Keeper. An artifact that fails validation blocks all downstream consumers until the owner agent resolves it.

### Design Principles

1. **Single owner** — exactly one agent is authorized to produce each artifact.
2. **Explicit schema** — every artifact has required fields. Missing fields fail validation.
3. **Consumer-driven** — the artifact must satisfy all consumers, not just the producer.
4. **Versioned** — artifact changes are tracked; breaking changes require re-negotiation.
5. **Gate-checked** — the Quality Gate Keeper verifies each artifact exists and passes validation before downstream agents can consume it.

---

## Artifact Catalog

### 1. business_brief

| Field | Value |
|---|---|
| **artifact_id** | `business_brief` |
| **owner_agent** | `chief_vision_officer` (vision section), `business_strategist` (business model section) |
| **required_fields** | `vision_statement`, `mission_statement`, `value_proposition`, `target_market_summary`, `business_model`, `revenue_model`, `strategic_goals`, `success_metrics`, `key_assumptions`, `risks`, `timeline_estimate` |
| **consumers** | All agents (universal input) |
| **validation_method** | Quality Gate Keeper checks: all fields present, non-empty, internally consistent |
| **pass_criteria** | All required fields present; vision and business model do not contradict; success metrics are measurable |
| **fail_criteria** | Missing required fields; vision contradicts business model; success metrics not quantifiable |

### 2. market_research_report

| Field | Value |
|---|---|
| **artifact_id** | `market_research_report` |
| **owner_agent** | `market_researcher` |
| **required_fields** | `market_size_tam`, `market_size_sam`, `market_size_som`, `market_trends`, `segment_analysis`, `opportunity_assessment`, `threat_assessment`, `data_sources`, `methodology_notes` |
| **consumers** | Business Strategist, Product Manager, Competitor Analyst, User Researcher |
| **validation_method** | Data sources verified; claims checked against cited sources; TAM/SAM/SOM consistency check |
| **pass_criteria** | All fields present; sources cited; market sizing has methodology; trends have evidence |
| **fail_criteria** | No sources cited; TAM > SAM or SAM > SOM; claims contradict available data |

### 3. competitor_map

| Field | Value |
|---|---|
| **artifact_id** | `competitor_map` |
| **owner_agent** | `competitor_analyst` |
| **required_fields** | `direct_competitors[]`, `indirect_competitors[]`, `feature_comparison_matrix`, `pricing_comparison`, `positioning_map`, `competitive_advantages`, `competitive_disadvantages`, `market_gaps`, `data_collection_date` |
| **consumers** | Product Manager, Business Strategist, Brand Strategist, Pricing Analyst |
| **validation_method** | Minimum 3 direct competitors identified; feature matrix has evidence; pricing sourced |
| **pass_criteria** | At least 3 competitors mapped; feature comparison is specific; pricing data included; gaps identified |
| **fail_criteria** | No direct competitors (unrealistic); feature matrix empty; no pricing data; no gaps found |

### 4. target_personas

| Field | Value |
|---|---|
| **artifact_id** | `target_personas` |
| **owner_agent** | `user_researcher` |
| **required_fields** | `personas[]`, each with: `name`, `demographics`, `goals`, `pain_points`, `jobs_to_be_done`, `current_solutions`, `tech_comfort_level`, `decision_criteria`, `use_frequency`, `willingness_to_pay` |
| **consumers** | Product Manager, UX Designer, Brand Strategist, Content Strategist, Growth Analyst, Customer Success Manager |
| **validation_method** | Minimum 2 personas; each persona has all fields; JTBD are specific not generic |
| **pass_criteria** | 2+ distinct personas; pain points are evidence-backed; JTBD are actionable; personas are differentiated |
| **fail_criteria** | Single persona only; personas are identical; pain points are generic; JTBD too vague to act on |

### 5. product_requirements_doc

| Field | Value |
|---|---|
| **artifact_id** | `product_requirements_doc` |
| **owner_agent** | `product_manager` |
| **required_fields** | `product_overview`, `problem_statement`, `solution_description`, `feature_list[]` (each with priority, effort, dependencies), `user_stories[]`, `acceptance_criteria[]`, `scope_boundaries`, `out_of_scope`, `assumptions`, `constraints`, `dependencies`, `mvp_definition`, `post_mvp_features[]` |
| **consumers** | Software Architect, UX Designer, Security Engineer, QA Engineer, DevOps Engineer, all engineering agents |
| **validation_method** | Feature completeness check; acceptance criteria are testable; MVP is defined; scope is bounded |
| **pass_criteria** | All features have acceptance criteria; MVP is clearly scoped; out-of-scope is explicit; stories follow INVEST |
| **fail_criteria** | Missing acceptance criteria; scope unbounded; MVP undefined; features lack priority |

### 6. user_stories

| Field | Value |
|---|---|
| **artifact_id** | `user_stories` |
| **owner_agent** | `product_manager` |
| **required_fields** | `epics[]`, `stories[]` each with: `id`, `as_a`, `i_want`, `so_that`, `acceptance_criteria[]`, `priority`, `estimate`, `dependencies[]`, `persona_ref` |
| **consumers** | Software Architect, all engineering agents, QA Engineer, UX Designer |
| **validation_method** | Each story linked to a persona; acceptance criteria are specific and testable; priorities assigned |
| **pass_criteria** | All stories have persona refs; acceptance criteria in GIVEN/WHEN/THEN format; dependencies explicit |
| **fail_criteria** | Stories without personas; acceptance criteria untestable; circular dependencies |

### 7. acceptance_criteria

| Field | Value |
|---|---|
| **artifact_id** | `acceptance_criteria` |
| **owner_agent** | `product_manager` |
| **required_fields** | Per feature: `feature_id`, `criteria[]` in GIVEN/WHEN/THEN format, `edge_cases[]`, `non_functional_requirements[]` |
| **consumers** | QA Engineer, Test Automation Engineer, all engineering agents, Final Arbiter |
| **validation_method** | GIVEN/WHEN/THEN format check; edge cases identified; NFRs specified |
| **pass_criteria** | All criteria in structured format; edge cases covered; NFRs measurable |
| **fail_criteria** | Criteria in prose only; no edge cases; NFRs missing |

### 8. brand_strategy

| Field | Value |
|---|---|
| **artifact_id** | `brand_strategy` |
| **owner_agent** | `brand_strategist` |
| **required_fields** | `brand_positioning`, `brand_promise`, `brand_values[]`, `brand_personality`, `brand_voice_attributes`, `target_audience_alignment`, `competitive_differentiation`, `brand_story` |
| **consumers** | UX Designer, UI Designer, Content Strategist, Marketing Lead, Brand Book |
| **validation_method** | Positioning statement is specific; values are actionable; voice attributes are concrete |
| **pass_criteria** | Positioning differentiated from competitors; values non-generic; voice attributes usable by content team |
| **fail_criteria** | Positioning same as competitor; values are clichés; voice too vague to implement |

### 9. brand_book

| Field | Value |
|---|---|
| **artifact_id** | `brand_book` |
| **owner_agent** | `brand_strategist` |
| **required_fields** | `brand_name`, `logo_guidelines`, `color_palette`, `typography`, `imagery_style`, `iconography`, `voice_and_tone`, `brand_application_examples`, `do_and_dont`, `accessibility_notes` |
| **consumers** | UI Designer, Design System Architect, Content Strategist, Marketing Lead, Frontend Developer |
| **validation_method** | Color palette has accessible contrast ratios; typography is web-safe; voice examples provided |
| **pass_criteria** | Complete color system; typography with fallbacks; voice examples for 3+ contexts; accessibility considered |
| **fail_criteria** | Colors not meeting WCAG AA contrast; no fallback fonts; voice examples missing |

### 10. content_strategy

| Field | Value |
|---|---|
| **artifact_id** | `content_strategy` |
| **owner_agent** | `content_strategist` |
| **required_fields** | `content_pillars[]`, `messaging_framework`, `content_types[]`, `editorial_calendar`, `content_model`, `information_hierarchy`, `localization_strategy`, `tone_per_channel`, `content_governance` |
| **consumers** | Marketing Lead, SEO Specialist, UX Designer, Documentation Specialist |
| **validation_method** | Content pillars mapped to personas; messaging framework complete; content model structured |
| **pass_criteria** | All pillars have sample content; messaging framework covers all personas; content model is structured |
| **fail_criteria** | Pillars not linked to personas; messaging inconsistent across channels; no localization plan |

### 11. UX_flow_map

| Field | Value |
|---|---|
| **artifact_id** | `UX_flow_map` |
| **owner_agent** | `ux_designer` |
| **required_fields** | `user_flows[]` each with: `flow_name`, `entry_point`, `exit_point`, `steps[]`, `decision_points[]`, `error_states[]`, `persona_ref`, `happy_path`, `edge_cases` |
| **consumers** | UI Designer, Interaction Designer, Product Manager, QA Engineer, Content Strategist |
| **validation_method** | Every flow has entry and exit points; all states covered; each flow mapped to a persona |
| **pass_criteria** | Complete flows for all core user journeys; error states designed; decision logic explicit |
| **fail_criteria** | Missing error states; flows don't match personas; decision points ambiguous |

### 12. information_architecture

| Field | Value |
|---|---|
| **artifact_id** | `information_architecture` |
| **owner_agent** | `ux_designer` |
| **required_fields** | `site_map`, `navigation_structure`, `content_hierarchy`, `labeling_system`, `search_schema`, `url_structure`, `breadcrumb_rules` |
| **consumers** | UI Designer, Frontend Developer, Content Strategist, SEO Specialist |
| **validation_method** | Site map is complete; navigation depth ≤ 3 levels; labels are consistent |
| **pass_criteria** | Complete site map; navigation accessible; labels consistent; search schema defined |
| **fail_criteria** | Navigation deeper than 3 levels; inconsistent labels; no search schema |

### 13. wireframes

| Field | Value |
|---|---|
| **artifact_id** | `wireframes` |
| **owner_agent** | `ui_designer` |
| **required_fields** | Per screen: `screen_name`, `layout_grid`, `component_placement`, `content_zones`, `navigation_elements`, `responsive_breakpoints`, `state_variants` (loading, empty, error, success, edge) |
| **consumers** | Frontend Developer, UX Designer, Interaction Designer, Visual QA Engineer |
| **validation_method** | All screens wireframed; responsive breakpoints defined; all states shown |
| **pass_criteria** | Wireframes for all screens; responsive layouts for mobile/tablet/desktop; all UI states covered |
| **fail_criteria** | Screens missing; no responsive layouts; states not designed |

### 14. design_system

| Field | Value |
|---|---|
| **artifact_id** | `design_system` |
| **owner_agent** | `design_system_architect` |
| **required_fields** | `design_tokens` (color, spacing, typography, elevation, motion, breakpoints), `component_library[]` each with: `name`, `variants`, `states`, `props`, `accessibility`, `usage_guidelines`, `code_reference` |
| **consumers** | UI Designer, Frontend Developer, Mobile Developer, Visual QA Engineer |
| **validation_method** | All tokens defined; components have all states; accessibility annotations; code references present |
| **pass_criteria** | Complete token system; 15+ core components; each component has all states; a11y annotations |
| **fail_criteria** | Missing token categories; components without states; no accessibility annotations; no code refs |

### 15. UI_spec

| Field | Value |
|---|---|
| **artifact_id** | `UI_spec` |
| **owner_agent** | `ui_designer` |
| **required_fields** | Per screen: `visual_design`, `component_states`, `responsive_layouts`, `spacing_spec`, `typography_application`, `color_application`, `interaction_notes`, `design_system_compliance` |
| **consumers** | Frontend Developer, Mobile Developer, Interaction Designer, Visual QA Engineer, Accessibility Auditor |
| **validation_method** | All screens have visual designs; design system components used; responsive layouts present |
| **pass_criteria** | Complete visual designs for all screens; design system compliance; responsive breakpoints |
| **fail_criteria** | Screens using non-design-system components; missing responsive layouts; color contrast failures |

### 16. architecture_spec

| Field | Value |
|---|---|
| **artifact_id** | `architecture_spec` |
| **owner_agent** | `software_architect` |
| **required_fields** | `tech_stack`, `system_diagram`, `service_boundaries`, `data_flow`, `deployment_topology`, `non_functional_requirements`, `technology_decisions` with rationale, `constraints`, `trade_offs`, `future_considerations` |
| **consumers** | All engineering agents, API Architect, Data Architect, Security Engineer, DevOps Engineer |
| **validation_method** | Tech stack justified; service boundaries clear; NFRs specified; trade-offs documented |
| **pass_criteria** | Complete tech stack with rationale; clear service boundaries; NFRs measurable; trade-offs explicit |
| **fail_criteria** | Tech choices without rationale; monolith not justified; NFRs missing; no trade-off analysis |

### 17. API_contract

| Field | Value |
|---|---|
| **artifact_id** | `API_contract` |
| **owner_agent** | `api_architect` |
| **required_fields** | `endpoints[]` each with: `method`, `path`, `request_schema`, `response_schema`, `error_schema`, `auth_required`, `rate_limit`, `pagination`, `filtering`, `sorting`, `versioning_strategy`, `deprecation_policy`, `webhooks[]` |
| **consumers** | Senior Frontend Developer, Senior Backend Developer, Mobile Developer, QA Engineer, Documentation Specialist |
| **validation_method** | OpenAPI 3.x format; all endpoints have request/response/error schemas; auth specified |
| **pass_criteria** | Complete OpenAPI spec; all endpoints have schemas; error format standardized; versioning defined |
| **fail_criteria** | Missing endpoints for product features; schemas incomplete; no error standardization; no versioning |

### 18. database_schema_spec

| Field | Value |
|---|---|
| **artifact_id** | `database_schema_spec` |
| **owner_agent** | `database_developer` |
| **required_fields** | `tables[]` each with: `name`, `columns[]`, `primary_keys`, `foreign_keys`, `indexes`, `constraints`, `migration_strategy`, `seed_data`, `backup_strategy`, `retention_policy` |
| **consumers** | Senior Backend Developer, API Developer, Data Engineer, Security Engineer |
| **validation_method** | Schema supports all product features; indexes on query paths; constraints enforced; migration path clear |
| **pass_criteria** | Normalized schema (at least 3NF); indexes on foreign keys; migration strategy defined; seed data available |
| **fail_criteria** | Denormalized without justification; missing indexes; no migration plan; no retention policy |

### 19. security_requirements

| Field | Value |
|---|---|
| **artifact_id** | `security_requirements` |
| **owner_agent** | `security_engineer` |
| **required_fields** | `threat_model`, `auth_scheme`, `authz_model`, `data_protection_requirements`, `encryption_standards`, `secret_management`, `vulnerability_scanning`, `security_headers`, `cors_policy`, `csp_policy`, `dependency_scanning`, `audit_logging` |
| **consumers** | All engineering agents, DevOps Engineer, Legal Compliance Officer, Penetration Tester |
| **validation_method** | Threat model covers OWASP Top 10; auth/authz specified; encryption standards named; audit logging designed |
| **pass_criteria** | Complete threat model; auth scheme defined; encryption at rest and in transit; CSP/CORS configured |
| **fail_criteria** | No threat model; auth not specified; plaintext secrets; missing security headers |

### 20. frontend_implementation_plan

| Field | Value |
|---|---|
| **artifact_id** | `frontend_implementation_plan` |
| **owner_agent** | `senior_frontend_developer` |
| **required_fields** | `component_tree`, `state_management_approach`, `routing_spec`, `api_integration_plan`, `performance_budget`, `bundle_optimization`, `testing_strategy`, `accessibility_implementation`, `build_configuration`, `deployment_instructions` |
| **consumers** | Frontend Performance Engineer, Mobile Developer, QA Engineer, DevOps Engineer |
| **validation_method** | All UI screens mapped to components; state management justified; performance budget set; a11y plan present |
| **pass_criteria** | Complete component tree; state management approach documented; bundle budget defined; a11y plan actionable |
| **fail_criteria** | Components not mapped to UI screens; no performance budget; a11y not addressed; build config missing |

### 21. backend_implementation_plan

| Field | Value |
|---|---|
| **artifact_id** | `backend_implementation_plan` |
| **owner_agent** | `senior_backend_developer` |
| **required_fields** | `service_design`, `api_implementation_approach`, `middleware_stack`, `background_jobs`, `error_handling_strategy`, `logging_strategy`, `testing_strategy`, `performance_targets`, `deployment_considerations` |
| **consumers** | API Developer, Integration Engineer, Database Developer, QA Engineer, DevOps Engineer |
| **validation_method** | All API endpoints implemented; error handling standardized; middleware documented; background jobs defined |
| **pass_criteria** | Service design complete; middleware stack justified; error handling consistent; logging structured |
| **fail_criteria** | Endpoints not covered; error handling ad-hoc; no background job strategy; logging unstructured |

### 22. test_plan

| Field | Value |
|---|---|
| **artifact_id** | `test_plan` |
| **owner_agent** | `qa_engineer` |
| **required_fields** | `test_levels` (unit/integration/E2E/performance/security/accessibility), `test_cases[]`, `test_data`, `test_environments`, `automation_scope`, `regression_suite`, `defect_management`, `exit_criteria` |
| **consumers** | Test Automation Engineer, Performance Tester, Visual QA Engineer, all engineering agents |
| **validation_method** | All acceptance criteria have test cases; test levels defined; exit criteria explicit |
| **pass_criteria** | Test cases cover all acceptance criteria; automation scope defined; regression suite specified; exit criteria measurable |
| **fail_criteria** | Acceptance criteria without tests; no regression suite; exit criteria vague; no test data |

### 23. QA_report

| Field | Value |
|---|---|
| **artifact_id** | `QA_report` |
| **owner_agent** | `qa_engineer` |
| **required_fields** | `test_summary`, `passed_count`, `failed_count`, `blocked_count`, `skipped_count`, `defects[]`, `test_coverage`, `regression_results`, `automation_results`, `recommendations`, `release_readiness_assessment` |
| **consumers** | Release Manager, Final Arbiter, Product Manager, all engineering agents |
| **validation_method** | All test results reported; defects have severity/priority; coverage meets threshold; recommendations specific |
| **pass_criteria** | All critical tests pass; coverage ≥ 80%; all defects triaged; release recommendation clear |
| **fail_criteria** | Critical tests failing; coverage below threshold; untriaged defects; vague recommendations |

### 24. visual_QA_report

| Field | Value |
|---|---|
| **artifact_id** | `visual_QA_report` |
| **owner_agent** | `visual_qa_engineer` |
| **required_fields** | `visual_regression_results`, `responsive_breakpoint_results`, `cross_browser_results`, `dark_mode_results`, `animation_fidelity`, `design_system_compliance`, `pixel_comparison_summary`, `defects[]` |
| **consumers** | UI Designer, Senior Frontend Developer, QA Engineer, Final Arbiter |
| **validation_method** | All screens checked across breakpoints; dark mode verified; animations match spec |
| **pass_criteria** | No visual regressions; responsive layouts match designs; dark mode consistent; ≥ 95% design fidelity |
| **fail_criteria** | Visual regressions detected; breakpoint layout failures; dark mode broken; major design deviations |

### 25. performance_report

| Field | Value |
|---|---|
| **artifact_id** | `performance_report` |
| **owner_agent** | `performance_tester` |
| **required_fields** | `load_test_results`, `stress_test_results`, `endurance_test_results`, `scalability_analysis`, `bottleneck_analysis`, `response_time_percentiles`, `throughput`, `error_rate`, `resource_utilization`, `recommendations` |
| **consumers** | Software Architect, Senior Backend Developer, DevOps Engineer, Final Arbiter |
| **validation_method** | Tests run at expected load; bottlenecks identified; recommendations specific |
| **pass_criteria** | Response times within targets; error rate < 0.1%; bottlenecks documented; scalability headroom confirmed |
| **fail_criteria** | Response times exceed targets; error rate unacceptable; bottlenecks unidentified; no scalability analysis |

### 26. deployment_plan

| Field | Value |
|---|---|
| **artifact_id** | `deployment_plan` |
| **owner_agent** | `devops_engineer` |
| **required_fields** | `ci_cd_pipeline`, `environment_strategy` (dev/staging/prod), `infrastructure_spec`, `containerization`, `orchestration`, `secrets_management`, `rollback_strategy`, `health_checks`, `monitoring_integration` |
| **consumers** | Infrastructure Engineer, Release Manager, SRE Engineer, Observability Engineer |
| **validation_method** | Pipeline covers build/test/deploy; environments defined; secrets managed; rollback tested |
| **pass_criteria** | Complete CI/CD pipeline; environment parity; secrets not in config; rollback procedure documented |
| **fail_criteria** | Manual deployment steps; no staging environment; secrets in config; no rollback plan |

### 27. release_readiness_report

| Field | Value |
|---|---|
| **artifact_id** | `release_readiness_report` |
| **owner_agent** | `release_manager` |
| **required_fields** | `release_version`, `changelog`, `all_gates_status`, `QA_report_summary`, `security_review_summary`, `performance_review_summary`, `open_issues`, `rollback_procedure`, `go_no_go_recommendation`, `stakeholder_signoffs` |
| **consumers** | Final Arbiter, Product Manager, DevOps Engineer |
| **validation_method** | All gates checked; open issues triaged; rollback procedure current; changelog complete |
| **pass_criteria** | All gates passing or waived with justification; open issues non-blocking; rollback tested; changelog complete |
| **fail_criteria** | Critical gate failing; blocking issues open; rollback not tested; changelog incomplete |

### 28. final_arbiter_decision

| Field | Value |
|---|---|
| **artifact_id** | `final_arbiter_decision` |
| **owner_agent** | `final_arbiter` |
| **required_fields** | `decision` (APPROVE/RETRY/BLOCK/ESCALATE), `evidence_summary`, `conflicts_resolved`, `conditions`, `risk_acknowledgement`, `rationale`, `affected_artifacts`, `next_steps` |
| **consumers** | All agents (final decision), Chief Vision Officer (advisory) |
| **validation_method** | All evidence cited; conflicts documented; rationale explicit; conditions specific |
| **pass_criteria** | Decision supported by evidence; all conflicts addressed; conditions actionable; rationale clear |
| **fail_criteria** | Decision without evidence; unresolved conflicts; vague conditions; no rationale |

---

## Additional Artifacts

### 29. ethics_audit_report

| Field | Value |
|---|---|
| **artifact_id** | `ethics_audit_report` |
| **owner_agent** | `chief_product_ethics_officer` |
| **required_fields** | `privacy_assessment`, `bias_audit`, `accessibility_audit`, `dark_pattern_audit`, `sustainability_assessment`, `findings[]`, `remediation_required`, `compliance_status` |
| **consumers** | Product Manager, Final Arbiter, Legal Compliance Officer |
| **validation_method** | All audit dimensions covered; findings specific; remediation actionable |
| **pass_criteria** | No critical ethics violations; privacy respected; bias assessed; accessibility addressed |
| **fail_criteria** | Critical ethics violations unaddressed; bias confirmed but not remediated; dark patterns detected |

### 30. compliance_requirements

| Field | Value |
|---|---|
| **artifact_id** | `compliance_requirements` |
| **owner_agent** | `legal_compliance_officer` |
| **required_fields** | `applicable_regulations[]`, `data_protection_requirements`, `consent_requirements`, `data_retention_policy`, `data_deletion_policy`, `breach_notification_procedure`, `jurisdiction_notes`, `required_documents[]` |
| **consumers** | Security Engineer, Database Developer, DevOps Engineer, Product Manager |
| **validation_method** | Regulations mapped to product features; required documents listed; procedures defined |
| **pass_criteria** | All applicable regulations identified; procedures defined; documents specified |
| **fail_criteria** | Missing regulatory analysis; no breach procedure; no data retention/deletion policy |

### 31. growth_strategy

| Field | Value |
|---|---|
| **artifact_id** | `growth_strategy` |
| **owner_agent** | `growth_analyst` |
| **required_fields** | `acquisition_channels[]`, `activation_funnel`, `retention_model`, `referral_mechanics`, `monetization_optimization`, `kpis`, `experimentation_roadmap` |
| **consumers** | Marketing Lead, Product Manager, Analytics Engineer, Conversion Optimizer |
| **validation_method** | Funnel stages defined; KPIs measurable; experiments planned |
| **pass_criteria** | Complete funnel with metrics; acquisition channels prioritized; KPIs measurable; experiment roadmap |
| **fail_criteria** | Funnel not measurable; no retention model; KPIs vague; no experiment plan |

### 32. observability_spec

| Field | Value |
|---|---|
| **artifact_id** | `observability_spec` |
| **owner_agent** | `observability_engineer` |
| **required_fields** | `logging_schema`, `metrics[]`, `traces`, `dashboards[]`, `alerts[]`, `error_tracking`, `slo_definitions[]`, `on_call_rotation` |
| **consumers** | SRE Engineer, DevOps Engineer, Senior Backend Developer |
| **validation_method** | SLOs defined; alerts have runbooks; dashboards cover key metrics |
| **pass_criteria** | Complete logging schema; metrics for all services; SLOs for critical paths; alert runbooks |
| **fail_criteria** | No structured logging; critical metrics missing; SLOs undefined; no runbooks |

### 33. project_memory

| Field | Value |
|---|---|
| **artifact_id** | `project_memory` |
| **owner_agent** | `project_memory_keeper` |
| **required_fields** | `decisions_log[]`, `trade_offs[]`, `rationale[]`, `context_handoff`, `lessons_learned[]`, `phase_summaries[]`, `open_questions[]` |
| **consumers** | All agents (context injection), Final Arbiter, Orchestrator |
| **validation_method** | All phase decisions recorded; trade-offs documented; handoff current |
| **pass_criteria** | Complete decision trail; trade-offs with rationale; current handoff; lessons captured |
| **fail_criteria** | Decisions not recorded; rationale missing; stale handoff; no lessons learned |

---

## Artifact Dependency Graph

```
business_brief ─────────────────────────────────────────────────────────────────────────────┐
    │                                                                                        │
    ├─ market_research_report ──────────────────────────────────────────────────────────┐    │
    │   ├─ competitor_map ──────────────────────────────────────────────────────────┐    │    │
    │   ├─ target_personas ─────────────────────────────────────────────────────┐    │    │    │
    │   └─ user_journey_maps ────────────────────────────────────────────────┐   │    │    │    │
    │                                                                         │   │    │    │    │
    ├─ brand_strategy ───────────────────────────────────────────────────┐    │   │    │    │    │
    │   ├─ brand_book ───────────────────────────────────────────────┐    │   │    │    │    │
    │   └─ content_strategy ─────────────────────────────────────┐    │   │    │    │    │
    │                                                              │    │   │    │    │    │
    ├─ product_requirements_doc ◄──────────────────────────────────┤    │   │    │    │    │
    │   ├─ user_stories ───────────────────────────────────────┐   │    │   │    │    │    │
    │   ├─ acceptance_criteria ────────────────────────────┐    │   │    │   │    │    │    │
    │   │                                                   │    │   │    │   │    │    │    │
    ├─ UX_flow_map ◄────────────────────────────────────────┤    │   │    │   │    │    │    │
    │   └─ information_architecture ────────────────────┐    │   │    │   │    │    │    │
    │                                                     │    │   │    │   │    │    │    │
    ├─ design_system ◄────────────────────────────────────┤    │   │    │   │    │    │    │
    │                                                     │    │   │    │   │    │    │    │
    ├─ UI_spec ◄──────────────────────────────────────────┤    │   │    │   │    │    │    │
    │   ├─ wireframes ────────────────────────────────┐    │   │    │   │    │    │    │
    │                                                     │    │   │    │   │    │    │    │
    ├─ architecture_spec ◄────────────────────────────────┤    │   │    │   │    │    │    │
    │   ├─ API_contract ─────────────────────────────┐    │   │    │   │    │    │    │
    │   └─ database_schema_spec ──────────────────┐   │    │   │    │   │    │    │    │
    │                                                │   │    │   │    │   │    │    │    │
    ├─ security_requirements ◄───────────────────────┤   │    │   │    │   │    │    │    │
    │                                                │   │    │   │    │   │    │    │    │
    ├─ frontend_implementation_plan ◄────────────────┤   │    │   │    │   │    │    │    │
    ├─ backend_implementation_plan ◄─────────────────┤   │    │   │    │   │    │    │    │
    │                                                │   │    │   │    │   │    │    │    │
    ├─ test_plan ◄───────────────────────────────────┤   │    │   │    │   │    │    │    │
    │   ├─ QA_report ────────────────────────────┐   │   │    │    │   │    │    │    │
    │   ├─ visual_QA_report ─────────────────────┤   │   │    │    │   │    │    │    │
    │   └─ performance_report ───────────────────┤   │   │    │    │   │    │    │    │
    │                                                │   │   │    │    │   │    │    │    │
    ├─ compliance_requirements ◄─────────────────────┤   │   │    │    │   │    │    │    │
    ├─ ethics_audit_report ◄─────────────────────────┤   │   │    │    │   │    │    │    │
    │                                                │   │   │    │    │   │    │    │    │
    ├─ deployment_plan ◄─────────────────────────────┤   │   │    │    │   │    │    │    │
    │   └─ release_readiness_report ─────────────┐   │   │    │    │   │    │    │    │
    │                                                │   │   │    │    │   │    │    │    │
    ├─ growth_strategy ◄─────────────────────────────┤   │   │    │    │   │    │    │    │
    ├─ observability_spec ◄──────────────────────────┤   │   │    │    │   │    │    │    │
    │                                                │   │   │    │    │   │    │    │    │
    └─ final_arbiter_decision ◄──────────────────────┘   │   │    │    │   │    │    │    │
        (consumes all reports above)                     │   │    │    │   │    │    │    │

    project_memory (records everything, runs continuously)│   │    │    │   │    │    │    │
```

---

## Validation Gate Checklist

The Quality Gate Keeper validates artifacts at each gate:

| Gate | Artifacts Required | Validation |
|---|---|---|
| **Vision Gate** | `business_brief` | All sections present; vision and business model consistent |
| **Research Gate** | `market_research_report`, `competitor_map`, `target_personas` | Sources cited; competitors mapped; personas distinct |
| **Product Gate** | `product_requirements_doc`, `user_stories`, `acceptance_criteria` | Features complete; stories follow INVEST; criteria testable |
| **Design Gate** | `brand_book`, `UX_flow_map`, `information_architecture`, `wireframes`, `design_system`, `UI_spec` | Flows complete; IA depth ≤ 3; design system tokens defined; responsive layouts |
| **Architecture Gate** | `architecture_spec`, `API_contract`, `database_schema_spec`, `security_requirements` | Tech stack justified; API complete; schema normalized; threat model present |
| **Implementation Gate** | `frontend_implementation_plan`, `backend_implementation_plan` | Components mapped; endpoints covered; middleware specified |
| **Quality Gate** | `test_plan`, `QA_report`, `visual_QA_report`, `performance_report`, `ethics_audit_report` | Tests pass; coverage ≥ 80%; performance targets met; ethics cleared |
| **Security Gate** | `security_review`, `pentest_report`, `dependency_audit_report` | No critical CVEs; OWASP Top 10 tested; dependencies audited |
| **Release Gate** | `deployment_plan`, `release_readiness_report`, `compliance_requirements` | Pipeline defined; rollback tested; regulations satisfied |
| **Final Gate** | All above + `final_arbiter_decision` | All gates passed; evidence complete; decision clear |

---

## Constraint Compliance

- ✅ No source code changed
- ✅ Designed for Agent Council V2 consumption
- ✅ Contracts are machine-validatable
- ✅ Ownership is unambiguous
- ✅ Consumers and producers are explicit
- ✅ Phase 10 not started
