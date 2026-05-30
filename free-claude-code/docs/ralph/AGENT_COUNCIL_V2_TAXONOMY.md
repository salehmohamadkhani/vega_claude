# Agent Council V2 — Taxonomy

**Date:** 2026-05-30
**Status:** Design specification
**Purpose:** Define the full agent taxonomy for an artificial product-building company

---

## Overview

Agent Council V2 models an **artificial product-building company** as a set of specialized, interdependent AI agents. Each agent owns a specific domain. Agents pass structured artifacts between each other. Agents operate in parallel where possible and wait where dependencies exist. A Final Arbiter evaluates evidence from all agents before declaring a project complete.

### Design Principles

1. **Domain ownership** — each agent is the single authority on its specialty.
2. **Explicit dependencies** — every agent declares what it needs before it can start.
3. **Structured artifacts** — agents communicate through validated contracts, not ad-hoc messages.
4. **Parallel by default** — agents without mutual dependencies run concurrently.
5. **Fail-forward** — agents declare fail conditions; the council routes around failures.
6. **Project-scoped selection** — not all 100+ agents are activated for every project. The Orchestrator selects the relevant subset.

### Agent Layers

```
Layer 1  — Executive / Vision
Layer 2  — Business Strategy
Layer 3  — Market Research
Layer 4  — Product Management
Layer 5  — Brand / Content / Marketing
Layer 6  — UX / UI / Product Design
Layer 7  — Software Architecture
Layer 8  — Frontend Engineering
Layer 9  — Backend Engineering
Layer 10 — Database / Data Engineering
Layer 11 — QA / Testing / Verification
Layer 12 — Security / Compliance
Layer 13 — DevOps / Infrastructure
Layer 14 — Observability / Reliability
Layer 15 — Growth / Analytics
Layer 16 — Support / Operations
Layer 17 — Orchestration / Arbitration / Project Memory
```

### Agent Selection Logic

Projects are analyzed for required domains. An e-commerce project activates: Business Strategy, Market Research, Product Management, UX/UI Design, Frontend, Backend, Database, QA, Security, DevOps, Growth, and Arbitration. A CLI tool project might activate only: Product Management, Architecture, Backend, QA, and Arbitration.

The Orchestrator (Layer 17) determines which agents to activate based on the project brief.

---

## Layer 1 — Executive / Vision

### AGENT: chief_vision_officer

| Field | Value |
|---|---|
| **agent_id** | `chief_vision_officer` |
| **role_name** | Chief Vision Officer |
| **purpose** | Define the product vision, mission, core value proposition, and strategic direction. |
| **required_inputs** | Project brief or initial idea |
| **produced_artifacts** | `business_brief` (vision section), `strategic_direction` |
| **reviewers** | Business Strategist, Product Manager |
| **fail_conditions** | Vague or unvalidated vision; no differentiation from existing products; misalignment with market reality |
| **activation_trigger** | Always — this is the entry point agent |
| **parallel** | No — must run first as it sets direction |
| **dependencies** | None |

### AGENT: chief_product_ethics_officer

| Field | Value |
|---|---|
| **agent_id** | `chief_product_ethics_officer` |
| **role_name** | Chief Product Ethics Officer |
| **purpose** | Audit product decisions against ethical frameworks: privacy, bias, accessibility, sustainability, dark patterns. |
| **required_inputs** | `business_brief`, `product_requirements_doc`, `design_system` |
| **produced_artifacts** | `ethics_audit_report` |
| **reviewers** | Product Manager, Final Arbiter |
| **fail_conditions** | Unresolved privacy violations; confirmed bias in model/data; accessibility failures; dark pattern usage |
| **activation_trigger** | Products handling user data, AI/ML features, consumer-facing products |
| **parallel** | Yes — runs alongside QA and Security reviews |
| **dependencies** | PRD, design artifacts |

### AGENT: strategic_alignment_auditor

| Field | Value |
|---|---|
| **agent_id** | `strategic_alignment_auditor` |
| **role_name** | Strategic Alignment Auditor |
| **purpose** | Verify that implementation decisions remain aligned with the original vision and strategy. Raise misalignment. |
| **required_inputs** | `business_brief`, `product_requirements_doc`, `architecture_spec`, implementation plans |
| **produced_artifacts** | `alignment_audit_report` |
| **reviewers** | Chief Vision Officer, Final Arbiter |
| **fail_conditions** | Implementation contradicts stated vision; scope creep unacknowledged; stakeholder conflict unresolved |
| **activation_trigger** | Mid-project checkpoint, or when scope changes are proposed |
| **parallel** | Yes — runs at checkpoints, not continuously |
| **dependencies** | Vision + implementation artifacts |

---

## Layer 2 — Business Strategy

### AGENT: business_strategist

| Field | Value |
|---|---|
| **agent_id** | `business_strategist` |
| **role_name** | Business Strategist |
| **purpose** | Define business model, revenue strategy, pricing, go-to-market plan, cost structure, and risk assessment. |
| **required_inputs** | `business_brief`, `market_research_report`, `competitor_map` |
| **produced_artifacts** | `business_brief` (business model section), `business_model_canvas`, `pricing_strategy`, `gtm_plan` |
| **reviewers** | Chief Vision Officer, Product Manager, Market Researcher |
| **fail_conditions** | Unsustainable unit economics; no clear revenue model; pricing below cost; unaddressed regulatory risk |
| **activation_trigger** | Any product that has a business model (commercial products) |
| **parallel** | Yes — runs after Market Research, in parallel with Product Manager |
| **dependencies** | `market_research_report`, `competitor_map` |

### AGENT: monetization_strategist

| Field | Value |
|---|---|
| **agent_id** | `monetization_strategist` |
| **role_name** | Monetization Strategist |
| **purpose** | Design specific monetization mechanics: subscription tiers, freemium boundaries, in-app purchases, marketplace fees, ads. |
| **required_inputs** | `business_brief`, `target_personas`, `competitor_map` |
| **produced_artifacts** | `monetization_spec` |
| **reviewers** | Business Strategist, Product Manager, UX Designer |
| **fail_conditions** | Monetization harms core UX; pricing confuses users; competitor undercutting not addressed |
| **activation_trigger** | Revenue-generating products with complex pricing |
| **parallel** | Yes — runs after business model is defined |
| **dependencies** | `business_brief`, `target_personas` |

### AGENT: legal_compliance_officer

| Field | Value |
|---|---|
| **agent_id** | `legal_compliance_officer` |
| **role_name** | Legal & Compliance Officer |
| **purpose** | Identify legal requirements: GDPR, CCPA, HIPAA, SOC2, PCI-DSS, COPPA, terms of service, privacy policy, data processing agreements. |
| **required_inputs** | `business_brief`, `product_requirements_doc`, `database_schema_spec`, `security_requirements` |
| **produced_artifacts** | `compliance_requirements`, `legal_risk_assessment` |
| **reviewers** | Security Engineer, Database Developer, Product Manager |
| **fail_conditions** | Identified regulatory violation not addressed; missing required legal documents; data handling violates jurisdiction |
| **activation_trigger** | Products handling personal data, payments, health data, or targeting children |
| **parallel** | Yes — runs alongside Security requirements |
| **dependencies** | PRD, data model, security reqs |

---

## Layer 3 — Market Research

### AGENT: market_researcher

| Field | Value |
|---|---|
| **agent_id** | `market_researcher` |
| **role_name** | Market Researcher |
| **purpose** | Research market size, trends, segments, opportunities, threats. Produce data-backed market analysis. |
| **required_inputs** | `business_brief` (vision section) |
| **produced_artifacts** | `market_research_report`, `market_sizing`, `trend_analysis` |
| **reviewers** | Business Strategist, Product Manager |
| **fail_conditions** | No data sources cited; claims contradicted by available evidence; TAM/SAM/SOM not estimated |
| **activation_trigger** | Any product targeting a market (not internal tools) |
| **parallel** | Yes — runs alongside Competitor Analyst |
| **dependencies** | Vision from `business_brief` |

### AGENT: competitor_analyst

| Field | Value |
|---|---|
| **agent_id** | `competitor_analyst` |
| **role_name** | Competitor Analyst |
| **purpose** | Map competitive landscape: direct competitors, indirect competitors, feature matrices, positioning gaps. |
| **required_inputs** | `business_brief`, `market_research_report` |
| **produced_artifacts** | `competitor_map`, `competitive_positioning`, `feature_gap_analysis` |
| **reviewers** | Market Researcher, Product Manager, Business Strategist |
| **fail_conditions** | No competitors identified (unrealistic); feature comparison lacks evidence; differentiation unclear |
| **activation_trigger** | Any product with market competition |
| **parallel** | Yes — can run after market research starts, in parallel with user researcher |
| **dependencies** | `market_research_report` |

### AGENT: user_researcher

| Field | Value |
|---|---|
| **agent_id** | `user_researcher` |
| **role_name** | User Researcher |
| **purpose** | Define target personas, user needs, pain points, jobs-to-be-done, user journey mapping. |
| **required_inputs** | `business_brief`, `market_research_report` |
| **produced_artifacts** | `target_personas`, `user_needs_analysis`, `jobs_to_be_done`, `user_journey_maps` |
| **reviewers** | Product Manager, UX Designer, Market Researcher |
| **fail_conditions** | Personas lack specificity; no evidence for user needs; JTBD framework misapplied |
| **activation_trigger** | Any user-facing product |
| **parallel** | Yes — runs after market research |
| **dependencies** | `market_research_report` |

### AGENT: pricing_analyst

| Field | Value |
|---|---|
| **agent_id** | `pricing_analyst` |
| **role_name** | Pricing Analyst |
| **purpose** | Analyze competitor pricing, willingness-to-pay studies, pricing models, discount strategies, and revenue optimization. |
| **required_inputs** | `competitor_map`, `target_personas`, `business_brief` |
| **produced_artifacts** | `pricing_analysis`, `price_sensitivity_model` |
| **reviewers** | Business Strategist, Monetization Strategist |
| **fail_conditions** | No competitor price data; pricing not anchored to value; margin analysis missing |
| **activation_trigger** | Revenue-generating products |
| **parallel** | Yes — runs alongside Monetization Strategist |
| **dependencies** | `competitor_map`, `target_personas` |

---

## Layer 4 — Product Management

### AGENT: product_manager

| Field | Value |
|---|---|
| **agent_id** | `product_manager` |
| **role_name** | Product Manager |
| **purpose** | Own the product requirements, roadmap, and backlog. Translate vision + research into actionable specs. |
| **required_inputs** | `business_brief`, `market_research_report`, `competitor_map`, `target_personas`, `user_needs_analysis` |
| **produced_artifacts** | `product_requirements_doc`, `user_stories`, `acceptance_criteria`, `product_roadmap`, `feature_prioritization` |
| **reviewers** | Chief Vision Officer, Business Strategist, UX Designer, Software Architect |
| **fail_conditions** | Requirements contradict research; missing acceptance criteria; unprioritized backlog; stakeholder conflicts not resolved |
| **activation_trigger** | Always — core product agent |
| **parallel** | No — runs after research, before design/engineering |
| **dependencies** | All Layer 3 (Market Research) outputs |

### AGENT: technical_product_manager

| Field | Value |
|---|---|
| **agent_id** | `technical_product_manager` |
| **role_name** | Technical Product Manager |
| **purpose** | Bridge product requirements and technical feasibility. Validate technical constraints, API capabilities, platform limitations. |
| **required_inputs** | `product_requirements_doc`, `architecture_spec` |
| **produced_artifacts** | `technical_feasibility_assessment`, `technical_user_stories` |
| **reviewers** | Software Architect, Product Manager |
| **fail_conditions** | Product requirements impossible given technical constraints; no mitigation proposed |
| **activation_trigger** | Technically complex products |
| **parallel** | Yes — runs after architecture spec draft, alongside engineering planning |
| **dependencies** | `product_requirements_doc`, `architecture_spec` |

### AGENT: scope_manager

| Field | Value |
|---|---|
| **agent_id** | `scope_manager` |
| **role_name** | Scope Manager |
| **purpose** | Guard against scope creep. Evaluate change requests against original vision, timeline, and resources. |
| **required_inputs** | `business_brief`, `product_requirements_doc`, change proposals |
| **produced_artifacts** | `scope_change_decision`, `updated_roadmap` |
| **reviewers** | Product Manager, Chief Vision Officer |
| **fail_conditions** | Uncontrolled scope growth; no trade-off analysis for additions; removal of core features without justification |
| **activation_trigger** | Whenever a scope change is proposed |
| **parallel** | Yes — runs on-demand at change events |
| **dependencies** | Baseline PRD and vision |

---

## Layer 5 — Brand / Content / Marketing

### AGENT: brand_strategist

| Field | Value |
|---|---|
| **agent_id** | `brand_strategist` |
| **role_name** | Brand Strategist |
| **purpose** | Define brand identity: name, positioning, voice, tone, values, visual direction, brand story. |
| **required_inputs** | `business_brief`, `target_personas`, `competitor_map` |
| **produced_artifacts** | `brand_strategy`, `brand_book` |
| **reviewers** | Chief Vision Officer, UX Designer, Content Strategist |
| **fail_conditions** | Brand indistinguishable from competitors; voice inconsistent with target personas; values not substantiated |
| **activation_trigger** | Consumer-facing products, or products needing market differentiation |
| **parallel** | Yes — runs after personas are defined |
| **dependencies** | `target_personas`, `competitor_map` |

### AGENT: content_strategist

| Field | Value |
|---|---|
| **agent_id** | `content_strategist` |
| **role_name** | Content Strategist |
| **purpose** | Plan content architecture: information hierarchy, messaging framework, content types, editorial calendar, localization. |
| **required_inputs** | `brand_strategy`, `target_personas`, `UX_flow_map` |
| **produced_artifacts** | `content_strategy`, `messaging_framework`, `content_model` |
| **reviewers** | Brand Strategist, UX Designer, Product Manager |
| **fail_conditions** | Content not mapped to user journey; missing key messaging; no localization plan for global products |
| **activation_trigger** | Content-heavy products, marketing sites, documentation surfaces |
| **parallel** | Yes — runs after brand strategy |
| **dependencies** | `brand_strategy`, `UX_flow_map` |

### AGENT: marketing_lead

| Field | Value |
|---|---|
| **agent_id** | `marketing_lead` |
| **role_name** | Marketing Lead |
| **purpose** | Plan go-to-market marketing: channels, campaigns, launch strategy, positioning, press/PR. |
| **required_inputs** | `brand_strategy`, `business_brief`, `gtm_plan`, `target_personas` |
| **produced_artifacts** | `marketing_plan`, `launch_strategy`, `campaign_briefs` |
| **reviewers** | Business Strategist, Brand Strategist, Growth Analyst |
| **fail_conditions** | No channel strategy; target audience not reachable; launch timing conflicts |
| **activation_trigger** | Products requiring market launch |
| **parallel** | Yes — runs after brand and business strategy |
| **dependencies** | `brand_strategy`, `gtm_plan` |

### AGENT: seo_specialist

| Field | Value |
|---|---|
| **agent_id** | `seo_specialist` |
| **role_name** | SEO Specialist |
| **purpose** | Define SEO strategy: keyword research, technical SEO requirements, content optimization, backlink strategy. |
| **required_inputs** | `content_strategy`, `marketing_plan`, `information_architecture` |
| **produced_artifacts** | `seo_strategy`, `keyword_map`, `technical_seo_requirements` |
| **reviewers** | Content Strategist, Frontend Developer, Marketing Lead |
| **fail_conditions** | No keyword research; technical SEO conflicts with architecture; content not SEO-optimized |
| **activation_trigger** | Public-facing web products |
| **parallel** | Yes — runs after content strategy |
| **dependencies** | `content_strategy`, `information_architecture` |

---

## Layer 6 — UX / UI / Product Design

### AGENT: ux_designer

| Field | Value |
|---|---|
| **agent_id** | `ux_designer` |
| **role_name** | UX Designer |
| **purpose** | Design user experience: flows, information architecture, interaction patterns, accessibility, usability heuristics. |
| **required_inputs** | `target_personas`, `user_journey_maps`, `product_requirements_doc`, `brand_strategy` |
| **produced_artifacts** | `UX_flow_map`, `information_architecture`, `interaction_patterns`, `accessibility_requirements` |
| **reviewers** | User Researcher, Product Manager, UI Designer, QA Engineer |
| **fail_conditions** | Flows not mapped to personas; accessibility (WCAG) not addressed; IA contradicts user expectations |
| **activation_trigger** | Any product with a user interface |
| **parallel** | Yes — runs after personas/journeys, in parallel with UI design |
| **dependencies** | `target_personas`, `user_journey_maps`, `product_requirements_doc`, `brand_strategy` |

### AGENT: ui_designer

| Field | Value |
|---|---|
| **agent_id** | `ui_designer` |
| **role_name** | UI Designer |
| **purpose** | Design visual interface: screen layouts, component states, responsive breakpoints, micro-interactions, visual hierarchy. |
| **required_inputs** | `UX_flow_map`, `information_architecture`, `design_system`, `brand_book` |
| **produced_artifacts** | `UI_spec`, `wireframes`, `visual_designs`, `component_specs` |
| **reviewers** | UX Designer, Brand Strategist, Frontend Developer |
| **fail_conditions** | Designs don't match IA; responsive breakpoints missing; component states undefined; brand inconsistency |
| **activation_trigger** | Any product with a visual interface |
| **parallel** | Yes — runs after UX flows are defined |
| **dependencies** | `UX_flow_map`, `information_architecture`, `design_system`, `brand_book` |

### AGENT: design_system_architect

| Field | Value |
|---|---|
| **agent_id** | `design_system_architect` |
| **role_name** | Design System Architect |
| **purpose** | Build the design system: tokens, components, patterns, spacing, typography, color, elevation, motion. |
| **required_inputs** | `brand_book`, `UX_flow_map`, `accessibility_requirements` |
| **produced_artifacts** | `design_system`, `component_library_spec`, `design_tokens` |
| **reviewers** | UI Designer, Frontend Developer, Brand Strategist |
| **fail_conditions** | Tokens not normalized; components not accessible; no dark mode support; inconsistent spacing grid |
| **activation_trigger** | Products with multiple screens or components |
| **parallel** | Yes — runs after brand book, in parallel with UI design |
| **dependencies** | `brand_book`, `accessibility_requirements` |

### AGENT: interaction_designer

| Field | Value |
|---|---|
| **agent_id** | `interaction_designer` |
| **role_name** | Interaction Designer |
| **purpose** | Design micro-interactions, animations, transitions, loading states, empty states, error states, gestures. |
| **required_inputs** | `UI_spec`, `UX_flow_map`, `design_system` |
| **produced_artifacts** | `interaction_spec`, `animation_spec`, `state_machine_diagrams` |
| **reviewers** | UI Designer, Frontend Developer, UX Designer |
| **fail_conditions** | Loading/error/empty states not designed; animations not respecting reduced-motion; gesture conflicts |
| **activation_trigger** | Interactive products (web apps, mobile apps) |
| **parallel** | Yes — runs after UI spec is drafted |
| **dependencies** | `UI_spec`, `design_system` |

### AGENT: accessibility_auditor

| Field | Value |
|---|---|
| **agent_id** | `accessibility_auditor` |
| **role_name** | Accessibility Auditor |
| **purpose** | Audit all designs and implementations against WCAG 2.2 AA, screen reader compatibility, keyboard navigation, color contrast. |
| **required_inputs** | `UI_spec`, `design_system`, `accessibility_requirements`, `frontend_implementation_plan` |
| **produced_artifacts** | `accessibility_audit_report`, `a11y_remediation_tickets` |
| **reviewers** | UX Designer, UI Designer, Frontend Developer, QA Engineer |
| **fail_conditions** | WCAG AA failures; keyboard traps; screen reader incompatibility; color contrast failures |
| **activation_trigger** | Any user-facing UI |
| **parallel** | Yes — runs alongside QA testing |
| **dependencies** | `UI_spec`, `frontend_implementation_plan` |

---

## Layer 7 — Software Architecture

### AGENT: software_architect

| Field | Value |
|---|---|
| **agent_id** | `software_architect` |
| **role_name** | Software Architect |
| **purpose** | Define system architecture: tech stack, service boundaries, data flow, API design principles, non-functional requirements. |
| **required_inputs** | `product_requirements_doc`, `technical_feasibility_assessment`, `security_requirements` |
| **produced_artifacts** | `architecture_spec`, `tech_stack_decision`, `system_boundaries`, `data_flow_diagrams` |
| **reviewers** | Technical Product Manager, Senior Backend Developer, Senior Frontend Developer, Security Engineer |
| **fail_conditions** | Architecture doesn't support requirements; tech stack choices unjustified; no scalability plan; tight coupling |
| **activation_trigger** | Always — core technical agent |
| **parallel** | No — must run before engineering layers |
| **dependencies** | `product_requirements_doc`, `security_requirements` |

### AGENT: api_architect

| Field | Value |
|---|---|
| **agent_id** | `api_architect` |
| **role_name** | API Architect |
| **purpose** | Design API surface: REST/GraphQL/gRPC endpoints, authentication, versioning, rate limiting, error handling, documentation standards. |
| **required_inputs** | `architecture_spec`, `product_requirements_doc`, `data_flow_diagrams` |
| **produced_artifacts** | `API_contract`, `api_documentation_spec`, `error_handling_standard` |
| **reviewers** | Software Architect, Senior Backend Developer, Senior Frontend Developer, Security Engineer |
| **fail_conditions** | Endpoints don't cover all use cases; auth model not specified; no versioning strategy; error format inconsistent |
| **activation_trigger** | Products with APIs (client-server, microservices, public APIs) |
| **parallel** | Yes — runs after architecture spec, in parallel with database schema |
| **dependencies** | `architecture_spec`, `data_flow_diagrams` |

### AGENT: data_architect

| Field | Value |
|---|---|
| **agent_id** | `data_architect` |
| **role_name** | Data Architect |
| **purpose** | Design data architecture: storage strategy, data models, caching layers, event sourcing, data pipelines, analytics schema. |
| **required_inputs** | `architecture_spec`, `product_requirements_doc` |
| **produced_artifacts** | `data_architecture_spec`, `storage_strategy`, `caching_strategy`, `event_schema` |
| **reviewers** | Software Architect, Database Developer, Backend Developer |
| **fail_conditions** | Data model doesn't support product requirements; no caching strategy; inconsistent event schema |
| **activation_trigger** | Data-intensive products |
| **parallel** | Yes — runs after architecture spec, in parallel with API design |
| **dependencies** | `architecture_spec` |

---

## Layer 8 — Frontend Engineering

### AGENT: senior_frontend_developer

| Field | Value |
|---|---|
| **agent_id** | `senior_frontend_developer` |
| **role_name** | Senior Frontend Developer |
| **purpose** | Plan and guide frontend implementation: component architecture, state management, routing, performance, bundle optimization. |
| **required_inputs** | `UI_spec`, `design_system`, `API_contract`, `architecture_spec`, `accessibility_requirements` |
| **produced_artifacts** | `frontend_implementation_plan`, `component_tree`, `state_management_spec`, `routing_spec` |
| **reviewers** | Software Architect, UI Designer, QA Engineer |
| **fail_conditions** | Plan doesn't cover all UI states; performance budget not defined; accessibility not addressed; bundle size unmanaged |
| **activation_trigger** | Products with a frontend |
| **parallel** | No — depends on multiple upstream layers |
| **dependencies** | `UI_spec`, `design_system`, `API_contract`, `architecture_spec`, `accessibility_requirements` |

### AGENT: frontend_performance_engineer

| Field | Value |
|---|---|
| **agent_id** | `frontend_performance_engineer` |
| **role_name** | Frontend Performance Engineer |
| **purpose** | Optimize frontend performance: Core Web Vitals, bundle analysis, lazy loading, code splitting, image optimization, caching headers. |
| **required_inputs** | `frontend_implementation_plan`, `UI_spec` |
| **produced_artifacts** | `frontend_performance_plan`, `bundle_budget`, `loading_strategy` |
| **reviewers** | Senior Frontend Developer, QA Engineer |
| **fail_conditions** | LCP > 2.5s; CLS > 0.1; INP > 200ms; no bundle budget; images unoptimized |
| **activation_trigger** | Web applications |
| **parallel** | Yes — runs after frontend plan, alongside implementation |
| **dependencies** | `frontend_implementation_plan` |

### AGENT: mobile_developer

| Field | Value |
|---|---|
| **agent_id** | `mobile_developer` |
| **role_name** | Mobile Developer |
| **purpose** | Plan mobile-specific implementation: React Native/Flutter/native, platform capabilities, offline support, push notifications, app store requirements. |
| **required_inputs** | `UI_spec`, `design_system`, `API_contract`, `architecture_spec` |
| **produced_artifacts** | `mobile_implementation_plan`, `platform_capability_map`, `offline_strategy` |
| **reviewers** | Senior Frontend Developer, Software Architect, QA Engineer |
| **fail_conditions** | Platform guidelines violated; offline support missing; app store rejection risks unaddressed |
| **activation_trigger** | Mobile apps |
| **parallel** | Yes — runs in parallel with frontend implementation |
| **dependencies** | `UI_spec`, `API_contract`, `architecture_spec` |

---

## Layer 9 — Backend Engineering

### AGENT: senior_backend_developer

| Field | Value |
|---|---|
| **agent_id** | `senior_backend_developer` |
| **role_name** | Senior Backend Developer |
| **purpose** | Plan and guide backend implementation: service design, business logic, API implementation, middleware, background jobs, error handling. |
| **required_inputs** | `API_contract`, `architecture_spec`, `database_schema_spec`, `security_requirements`, `product_requirements_doc` |
| **produced_artifacts** | `backend_implementation_plan`, `service_design`, `middleware_spec`, `background_job_spec` |
| **reviewers** | Software Architect, API Architect, Database Developer, Security Engineer |
| **fail_conditions** | API contract not fully implemented; error handling incomplete; auth/authz not designed; no retry/backoff strategy |
| **activation_trigger** | Products with a backend |
| **parallel** | No — depends on API, DB schema, architecture |
| **dependencies** | `API_contract`, `architecture_spec`, `database_schema_spec`, `security_requirements` |

### AGENT: api_developer

| Field | Value |
|---|---|
| **agent_id** | `api_developer` |
| **role_name** | API Developer |
| **purpose** | Implement API endpoints: request validation, response formatting, rate limiting, pagination, filtering, sorting, webhooks. |
| **required_inputs** | `API_contract`, `backend_implementation_plan`, `database_schema_spec` |
| **produced_artifacts** | `api_implementation`, `webhook_spec` |
| **reviewers** | Senior Backend Developer, API Architect, QA Engineer |
| **fail_conditions** | Contract not satisfied; validation missing; pagination broken; webhook delivery not guaranteed |
| **activation_trigger** | Products with APIs |
| **parallel** | Yes — runs after backend plan, in parallel with other backend work |
| **dependencies** | `API_contract`, `backend_implementation_plan` |

### AGENT: integration_engineer

| Field | Value |
|---|---|
| **agent_id** | `integration_engineer` |
| **role_name** | Integration Engineer |
| **purpose** | Design and implement third-party integrations: payment gateways, email services, SMS, social login, analytics, CRM, ERP. |
| **required_inputs** | `backend_implementation_plan`, `product_requirements_doc`, `API_contract` |
| **produced_artifacts** | `integration_spec`, `third_party_service_map`, `fallback_strategies` |
| **reviewers** | Senior Backend Developer, Security Engineer, QA Engineer |
| **fail_conditions** | No fallback for third-party failure; credential management insecure; rate limits not respected |
| **activation_trigger** | Products integrating third-party services |
| **parallel** | Yes — runs alongside API development |
| **dependencies** | `backend_implementation_plan` |

---

## Layer 10 — Database / Data Engineering

### AGENT: database_developer

| Field | Value |
|---|---|
| **agent_id** | `database_developer` |
| **role_name** | Database Developer |
| **purpose** | Design and implement database schema: tables, indexes, constraints, migrations, query optimization, data integrity. |
| **required_inputs** | `data_architecture_spec`, `product_requirements_doc`, `API_contract`, `security_requirements` |
| **produced_artifacts** | `database_schema_spec`, `migration_plan`, `indexing_strategy`, `query_patterns` |
| **reviewers** | Data Architect, Senior Backend Developer, Security Engineer |
| **fail_conditions** | Schema doesn't support product requirements; no migration strategy; missing indexes; no data retention policy |
| **activation_trigger** | Products with persistent data |
| **parallel** | No — depends on data architecture |
| **dependencies** | `data_architecture_spec`, `API_contract`, `security_requirements` |

### AGENT: data_engineer

| Field | Value |
|---|---|
| **agent_id** | `data_engineer` |
| **role_name** | Data Engineer |
| **purpose** | Build data pipelines: ETL/ELT, data warehousing, stream processing, data quality monitoring, data catalog. |
| **required_inputs** | `data_architecture_spec`, `database_schema_spec`, `analytics_strategy` |
| **produced_artifacts** | `data_pipeline_spec`, `etl_plan`, `data_quality_monitoring`, `data_catalog` |
| **reviewers** | Data Architect, Database Developer, Growth Analyst |
| **fail_conditions** | Pipeline doesn't handle late data; no data quality checks; schema evolution not planned |
| **activation_trigger** | Data-intensive or analytics-heavy products |
| **parallel** | Yes — runs after DB schema, alongside analytics setup |
| **dependencies** | `data_architecture_spec`, `database_schema_spec` |

### AGENT: ml_engineer

| Field | Value |
|---|---|
| **agent_id** | `ml_engineer` |
| **role_name** | ML Engineer |
| **purpose** | Design ML features: model selection, training pipeline, feature engineering, model serving, evaluation, monitoring, A/B testing. |
| **required_inputs** | `product_requirements_doc`, `data_architecture_spec`, `architecture_spec` |
| **produced_artifacts** | `ml_system_design`, `feature_spec`, `model_evaluation_plan`, `serving_architecture` |
| **reviewers** | Data Engineer, Software Architect, Product Ethics Officer |
| **fail_conditions** | No evaluation metrics; training-serving skew unaddressed; feature leakage; model bias not tested |
| **activation_trigger** | Products with ML/AI features |
| **parallel** | Yes — runs after data architecture |
| **dependencies** | `data_architecture_spec`, `architecture_spec` |

---

## Layer 11 — QA / Testing / Verification

### AGENT: qa_engineer

| Field | Value |
|---|---|
| **agent_id** | `qa_engineer` |
| **role_name** | QA Engineer |
| **purpose** | Design and execute test strategy: test plan, test cases, test automation, regression suites, edge case discovery. |
| **required_inputs** | `product_requirements_doc`, `acceptance_criteria`, `UI_spec`, `API_contract`, `frontend_implementation_plan`, `backend_implementation_plan` |
| **produced_artifacts** | `test_plan`, `test_cases`, `QA_report`, `bug_reports`, `regression_suite` |
| **reviewers** | Product Manager, Senior Frontend Developer, Senior Backend Developer |
| **fail_conditions** | Critical paths untested; edge cases not covered; regression suite missing; test data not representative |
| **activation_trigger** | Always — quality gate for all products |
| **parallel** | Yes — runs after implementation plans, alongside development |
| **dependencies** | `product_requirements_doc`, `acceptance_criteria`, `UI_spec`, `API_contract` |

### AGENT: test_automation_engineer

| Field | Value |
|---|---|
| **agent_id** | `test_automation_engineer` |
| **role_name** | Test Automation Engineer |
| **purpose** | Build test automation framework: unit, integration, E2E, API tests, visual regression, performance tests, CI integration. |
| **required_inputs** | `test_plan`, `API_contract`, `UI_spec`, `frontend_implementation_plan`, `backend_implementation_plan` |
| **produced_artifacts** | `automation_framework_spec`, `ci_test_pipeline`, `test_coverage_report` |
| **reviewers** | QA Engineer, DevOps Engineer |
| **fail_conditions** | No CI integration; flaky tests not addressed; coverage below threshold; E2E tests too slow |
| **activation_trigger** | Any product with automated testing |
| **parallel** | Yes — runs after test plan |
| **dependencies** | `test_plan` |

### AGENT: performance_tester

| Field | Value |
|---|---|
| **agent_id** | `performance_tester` |
| **role_name** | Performance Tester |
| **purpose** | Load testing, stress testing, endurance testing, scalability validation, bottleneck identification. |
| **required_inputs** | `architecture_spec`, `backend_implementation_plan`, `frontend_implementation_plan` |
| **produced_artifacts** | `performance_report`, `load_test_results`, `bottleneck_analysis`, `scalability_recommendations` |
| **reviewers** | Software Architect, Senior Backend Developer, DevOps Engineer |
| **fail_conditions** | System fails under expected load; no baseline established; bottlenecks not identified |
| **activation_trigger** | Products expecting significant traffic |
| **parallel** | Yes — runs after implementation is testable |
| **dependencies** | `architecture_spec`, implementation plans |

### AGENT: visual_qa_engineer

| Field | Value |
|---|---|
| **agent_id** | `visual_qa_engineer` |
| **role_name** | Visual QA Engineer |
| **purpose** | Verify visual implementation matches design: pixel-perfect comparison, responsive breakpoints, cross-browser, dark mode, animations. |
| **required_inputs** | `UI_spec`, `design_system`, `interaction_spec`, `frontend_implementation_plan` |
| **produced_artifacts** | `visual_QA_report`, `design_fidelity_audit`, `cross_browser_report` |
| **reviewers** | UI Designer, Senior Frontend Developer |
| **fail_conditions** | Visual regressions from design; responsive breakpoints broken; dark mode inconsistent; animations not matching spec |
| **activation_trigger** | Products with UI |
| **parallel** | Yes — runs after frontend implementation |
| **dependencies** | `UI_spec`, `design_system`, `frontend_implementation_plan` |

---

## Layer 12 — Security / Compliance

### AGENT: security_engineer

| Field | Value |
|---|---|
| **agent_id** | `security_engineer` |
| **role_name** | Security Engineer |
| **purpose** | Define security requirements: threat modeling, authentication, authorization, data protection, secrets management, dependency scanning. |
| **required_inputs** | `architecture_spec`, `API_contract`, `data_architecture_spec`, `compliance_requirements` |
| **produced_artifacts** | `security_requirements`, `threat_model`, `auth_spec`, `security_review` |
| **reviewers** | Software Architect, Senior Backend Developer, DevOps Engineer, Legal Compliance Officer |
| **fail_conditions** | No threat model; auth/authz not specified; secrets in code; known vulnerabilities not addressed |
| **activation_trigger** | Always — security is mandatory |
| **parallel** | Yes — runs after architecture spec, in parallel with implementation planning |
| **dependencies** | `architecture_spec`, `API_contract`, `data_architecture_spec` |

### AGENT: penetration_tester

| Field | Value |
|---|---|
| **agent_id** | `penetration_tester` |
| **role_name** | Penetration Tester |
| **purpose** | Simulate attacks: OWASP Top 10, injection, XSS, CSRF, auth bypass, privilege escalation, API abuse, data exfiltration. |
| **required_inputs** | `security_requirements`, `API_contract`, `backend_implementation_plan`, `threat_model` |
| **produced_artifacts** | `pentest_report`, `vulnerability_list`, `remediation_plan` |
| **reviewers** | Security Engineer, Senior Backend Developer |
| **fail_conditions** | Critical vulnerabilities found; OWASP Top 10 not tested; remediation not proposed |
| **activation_trigger** | Security-sensitive products |
| **parallel** | Yes — runs after implementation is testable |
| **dependencies** | `security_requirements`, implementation artifacts |

### AGENT: dependency_auditor

| Field | Value |
|---|---|
| **agent_id** | `dependency_auditor` |
| **role_name** | Dependency Auditor |
| **purpose** | Audit all third-party dependencies: known vulnerabilities, license compliance, maintenance status, supply chain risk. |
| **required_inputs** | `frontend_implementation_plan`, `backend_implementation_plan` |
| **produced_artifacts** | `dependency_audit_report`, `license_compliance_report`, `supply_chain_risk_assessment` |
| **reviewers** | Security Engineer, Legal Compliance Officer |
| **fail_conditions** | Critical CVEs in dependencies; license violations; unmaintained dependencies; supply chain attack vectors |
| **activation_trigger** | Products with third-party dependencies |
| **parallel** | Yes — runs alongside security testing |
| **dependencies** | Implementation plans (dependency lists) |

---

## Layer 13 — DevOps / Infrastructure

### AGENT: devops_engineer

| Field | Value |
|---|---|
| **agent_id** | `devops_engineer` |
| **role_name** | DevOps Engineer |
| **purpose** | Design CI/CD pipeline, infrastructure as code, containerization, orchestration, environment strategy, secrets management. |
| **required_inputs** | `architecture_spec`, `backend_implementation_plan`, `frontend_implementation_plan`, `security_requirements` |
| **produced_artifacts** | `deployment_plan`, `ci_cd_pipeline_spec`, `infrastructure_spec`, `environment_strategy` |
| **reviewers** | Software Architect, Security Engineer, Observability Engineer |
| **fail_conditions** | No CI/CD pipeline; manual deployment steps; secrets in config; no environment parity; no rollback strategy |
| **activation_trigger** | Products requiring deployment |
| **parallel** | Yes — runs after implementation plans |
| **dependencies** | `architecture_spec`, implementation plans |

### AGENT: infrastructure_engineer

| Field | Value |
|---|---|
| **agent_id** | `infrastructure_engineer` |
| **role_name** | Infrastructure Engineer |
| **purpose** | Provision and configure infrastructure: compute, networking, storage, CDN, DNS, load balancing, auto-scaling. |
| **required_inputs** | `deployment_plan`, `architecture_spec` |
| **produced_artifacts** | `infrastructure_provisioning_plan`, `network_topology`, `scaling_policy`, `cost_estimate` |
| **reviewers** | DevOps Engineer, Software Architect, Business Strategist |
| **fail_conditions** | Single points of failure; no auto-scaling; cost not estimated; network security groups misconfigured |
| **activation_trigger** | Cloud-deployed products |
| **parallel** | Yes — runs after deployment plan |
| **dependencies** | `deployment_plan`, `architecture_spec` |

### AGENT: release_manager

| Field | Value |
|---|---|
| **agent_id** | `release_manager` |
| **role_name** | Release Manager |
| **purpose** | Manage release process: versioning, changelogs, release notes, staged rollouts, canary deployments, rollback procedures. |
| **required_inputs** | `deployment_plan`, `QA_report`, `security_review`, `performance_report` |
| **produced_artifacts** | `release_readiness_report`, `release_notes`, `rollback_procedure`, `go_no_go_decision` |
| **reviewers** | DevOps Engineer, Product Manager, QA Engineer |
| **fail_conditions** | Release not versioned; no changelog; no rollback plan; failing tests not addressed; security issues open |
| **activation_trigger** | Every release |
| **parallel** | No — runs after all quality gates pass |
| **dependencies** | `QA_report`, `security_review`, `performance_report`, `deployment_plan` |

---

## Layer 14 — Observability / Reliability

### AGENT: observability_engineer

| Field | Value |
|---|---|
| **agent_id** | `observability_engineer` |
| **role_name** | Observability Engineer |
| **purpose** | Design observability stack: logging, metrics, tracing, alerting, dashboards, error tracking, SLO definition. |
| **required_inputs** | `architecture_spec`, `deployment_plan`, `backend_implementation_plan` |
| **produced_artifacts** | `observability_spec`, `slo_definitions`, `alerting_rules`, `dashboard_specs` |
| **reviewers** | DevOps Engineer, Senior Backend Developer, SRE Engineer |
| **fail_conditions** | No structured logging; metrics not defined; no tracing; alerting missing; no SLOs |
| **activation_trigger** | Production-deployed products |
| **parallel** | Yes — runs alongside deployment setup |
| **dependencies** | `architecture_spec`, `deployment_plan` |

### AGENT: sre_engineer

| Field | Value |
|---|---|
| **agent_id** | `sre_engineer` |
| **role_name** | SRE Engineer |
| **purpose** | Define reliability strategy: error budgets, incident response, runbooks, disaster recovery, capacity planning, chaos engineering. |
| **required_inputs** | `observability_spec`, `deployment_plan`, `architecture_spec` |
| **produced_artifacts** | `reliability_spec`, `incident_response_plan`, `disaster_recovery_plan`, `runbooks` |
| **reviewers** | Observability Engineer, DevOps Engineer, Software Architect |
| **fail_conditions** | No DR plan; no incident response; error budgets not defined; no capacity planning |
| **activation_trigger** | Production-critical products |
| **parallel** | Yes — runs after observability spec |
| **dependencies** | `observability_spec`, `deployment_plan` |

---

## Layer 15 — Growth / Analytics

### AGENT: growth_analyst

| Field | Value |
|---|---|
| **agent_id** | `growth_analyst` |
| **role_name** | Growth Analyst |
| **purpose** | Define growth strategy: acquisition channels, activation funnel, retention metrics, referral mechanics, monetization optimization. |
| **required_inputs** | `business_brief`, `target_personas`, `marketing_plan`, `monetization_spec` |
| **produced_artifacts** | `growth_strategy`, `funnel_definition`, `acquisition_plan`, `retention_model` |
| **reviewers** | Product Manager, Marketing Lead, Business Strategist |
| **fail_conditions** | No funnel defined; metrics not measurable; acquisition channels not validated; retention not addressed |
| **activation_trigger** | Products targeting user growth |
| **parallel** | Yes — runs after marketing and monetization |
| **dependencies** | `business_brief`, `marketing_plan`, `monetization_spec` |

### AGENT: analytics_engineer

| Field | Value |
|---|---|
| **agent_id** | `analytics_engineer` |
| **role_name** | Analytics Engineer |
| **purpose** | Implement analytics: event tracking, conversion tracking, user behavior analysis, cohort analysis, dashboards, experimentation framework. |
| **required_inputs** | `growth_strategy`, `data_architecture_spec`, `frontend_implementation_plan` |
| **produced_artifacts** | `analytics_spec`, `event_taxonomy`, `tracking_plan`, `experimentation_framework` |
| **reviewers** | Growth Analyst, Data Engineer, Frontend Developer |
| **fail_conditions** | Key events not tracked; no experimentation framework; data not flowing to warehouse; privacy violations |
| **activation_trigger** | Products requiring user analytics |
| **parallel** | Yes — runs after data architecture |
| **dependencies** | `growth_strategy`, `data_architecture_spec` |

### AGENT: conversion_optimizer

| Field | Value |
|---|---|
| **agent_id** | `conversion_optimizer` |
| **role_name** | Conversion Optimizer |
| **purpose** | Optimize conversion funnels: A/B test design, landing page optimization, checkout flow, onboarding optimization, churn reduction. |
| **required_inputs** | `analytics_spec`, `UI_spec`, `growth_strategy`, `UX_flow_map` |
| **produced_artifacts** | `cro_strategy`, `ab_test_plan`, `funnel_optimization_recommendations` |
| **reviewers** | Growth Analyst, UX Designer, Product Manager |
| **fail_conditions** | No baseline conversion rates; A/B tests not statistically valid; recommendations contradict UX best practices |
| **activation_trigger** | Revenue or conversion-focused products |
| **parallel** | Yes — runs after analytics and UI are available |
| **dependencies** | `analytics_spec`, `UI_spec` |

---

## Layer 16 — Support / Operations

### AGENT: customer_success_manager

| Field | Value |
|---|---|
| **agent_id** | `customer_success_manager` |
| **role_name** | Customer Success Manager |
| **purpose** | Design customer success workflows: onboarding, training materials, feedback loops, NPS surveys, churn intervention, escalation paths. |
| **required_inputs** | `product_requirements_doc`, `target_personas`, `user_journey_maps` |
| **produced_artifacts** | `customer_success_plan`, `onboarding_flow`, `feedback_system_spec`, `support_escalation_paths` |
| **reviewers** | Product Manager, UX Designer |
| **fail_conditions** | No onboarding flow; no feedback mechanism; no churn intervention; support not scoped |
| **activation_trigger** | Products with end users |
| **parallel** | Yes — runs after personas and journeys |
| **dependencies** | `product_requirements_doc`, `target_personas`, `user_journey_maps` |

### AGENT: documentation_specialist

| Field | Value |
|---|---|
| **agent_id** | `documentation_specialist` |
| **role_name** | Documentation Specialist |
| **purpose** | Create product documentation: user guides, API docs, developer docs, FAQ, changelog, knowledge base structure. |
| **required_inputs** | `product_requirements_doc`, `UI_spec`, `API_contract`, `architecture_spec` |
| **produced_artifacts** | `documentation_plan`, `user_guide_outline`, `api_documentation`, `knowledge_base_structure` |
| **reviewers** | Product Manager, API Architect, Customer Success Manager |
| **fail_conditions** | API endpoints undocumented; user guides incomplete; no searchable knowledge base; docs not versioned |
| **activation_trigger** | Products requiring user or developer documentation |
| **parallel** | Yes — runs after specs are stable |
| **dependencies** | `UI_spec`, `API_contract`, `architecture_spec` |

---

## Layer 17 — Orchestration / Arbitration / Project Memory

### AGENT: orchestrator

| Field | Value |
|---|---|
| **agent_id** | `orchestrator` |
| **role_name** | Orchestrator |
| **purpose** | Select and activate the right agents for a project, define execution order, manage parallel/concurrent execution, track dependencies. |
| **required_inputs** | `business_brief` |
| **produced_artifacts** | `council_activation_plan`, `agent_dependency_graph`, `execution_schedule` |
| **reviewers** | Chief Vision Officer, Final Arbiter |
| **fail_conditions** | Required agents not activated; deadlocks in dependency graph; sequential execution when parallel is possible |
| **activation_trigger** | Always — entry point for Agent Council |
| **parallel** | No — runs first, then activates other agents |
| **dependencies** | `business_brief` |

### AGENT: project_memory_keeper

| Field | Value |
|---|---|
| **agent_id** | `project_memory_keeper` |
| **role_name** | Project Memory Keeper |
| **purpose** | Maintain project memory: decisions log, rationale, trade-offs, lessons learned, context handoff between phases. |
| **required_inputs** | All agent outputs, all review reports, all decisions |
| **produced_artifacts** | `project_memory`, `decisions_log`, `trade_off_journal`, `context_handoff`, `lessons_learned` |
| **reviewers** | Final Arbiter, Orchestrator |
| **fail_conditions** | Decisions not recorded; rationale lost; context handoff incomplete; conflicts not documented |
| **activation_trigger** | Always — runs continuously |
| **parallel** | Yes — runs in background across all phases |
| **dependencies** | All agent outputs (streaming) |

### AGENT: final_arbiter

| Field | Value |
|---|---|
| **agent_id** | `final_arbiter` |
| **role_name** | Final Arbiter |
| **purpose** | Evaluate evidence from all agents, resolve conflicts, decide go/no-go, approve release, ensure quality and alignment. |
| **required_inputs** | `QA_report`, `security_review`, `performance_report`, `alignment_audit_report`, `visual_QA_report`, `accessibility_audit_report`, `release_readiness_report`, `dependency_audit_report`, `pentest_report`, `ethics_audit_report`, `project_memory` |
| **produced_artifacts** | `final_arbiter_decision`, `release_approval`, `conflict_resolution` |
| **reviewers** | Chief Vision Officer (advisory only — arbiter decision is final) |
| **fail_conditions** | Evidence incomplete; critical issues unresolved; conflicting reports not reconciled; quality gates bypassed |
| **activation_trigger** | End of each project phase, and before release |
| **parallel** | No — runs after all other agents complete |
| **dependencies** | All review/audit reports |

### AGENT: conflict_resolver

| Field | Value |
|---|---|
| **agent_id** | `conflict_resolver` |
| **role_name** | Conflict Resolver |
| **purpose** | Detect and resolve inter-agent conflicts: contradictory requirements, incompatible designs, resource disputes, priority clashes. |
| **required_inputs** | Conflicting agent outputs |
| **produced_artifacts** | `conflict_resolution`, `resolution_rationale` |
| **reviewers** | Final Arbiter, relevant domain agents |
| **fail_conditions** | Conflict not resolved; resolution creates new conflict; affected agents not consulted |
| **activation_trigger** | When two or more agent outputs contradict |
| **parallel** | Yes — runs on-demand at conflict events |
| **dependencies** | Conflicting outputs |

### AGENT: quality_gate_keeper

| Field | Value |
|---|---|
| **agent_id** | `quality_gate_keeper` |
| **role_name** | Quality Gate Keeper |
| **purpose** | Enforce quality gates: verify all required artifacts exist, all tests pass, all reviews complete, all approvals obtained. |
| **required_inputs** | All artifacts, all reports, all test results |
| **produced_artifacts** | `gate_status_report`, `missing_artifacts_list`, `gate_decision` (PASS/BLOCK/CONDITIONAL) |
| **reviewers** | Final Arbiter, Orchestrator |
| **fail_conditions** | Required artifact missing; gate bypassed without approval; conditional pass not tracked |
| **activation_trigger** | Every quality gate checkpoint |
| **parallel** | Yes — runs at defined checkpoints |
| **dependencies** | All phase artifacts |

---

## Agent Count Summary

| Layer | Agents | Examples |
|---|---|---|
| 1. Executive / Vision | 3 | Chief Vision Officer, Product Ethics Officer, Strategic Alignment Auditor |
| 2. Business Strategy | 3 | Business Strategist, Monetization Strategist, Legal Compliance Officer |
| 3. Market Research | 4 | Market Researcher, Competitor Analyst, User Researcher, Pricing Analyst |
| 4. Product Management | 3 | Product Manager, Technical PM, Scope Manager |
| 5. Brand / Content / Marketing | 4 | Brand Strategist, Content Strategist, Marketing Lead, SEO Specialist |
| 6. UX / UI / Product Design | 5 | UX Designer, UI Designer, Design System Architect, Interaction Designer, Accessibility Auditor |
| 7. Software Architecture | 3 | Software Architect, API Architect, Data Architect |
| 8. Frontend Engineering | 3 | Senior Frontend Developer, Frontend Perf Engineer, Mobile Developer |
| 9. Backend Engineering | 3 | Senior Backend Developer, API Developer, Integration Engineer |
| 10. Database / Data Engineering | 3 | Database Developer, Data Engineer, ML Engineer |
| 11. QA / Testing / Verification | 4 | QA Engineer, Test Automation Engineer, Performance Tester, Visual QA Engineer |
| 12. Security / Compliance | 3 | Security Engineer, Penetration Tester, Dependency Auditor |
| 13. DevOps / Infrastructure | 3 | DevOps Engineer, Infrastructure Engineer, Release Manager |
| 14. Observability / Reliability | 2 | Observability Engineer, SRE Engineer |
| 15. Growth / Analytics | 3 | Growth Analyst, Analytics Engineer, Conversion Optimizer |
| 16. Support / Operations | 2 | Customer Success Manager, Documentation Specialist |
| 17. Orchestration / Arbitration | 5 | Orchestrator, Project Memory Keeper, Final Arbiter, Conflict Resolver, Quality Gate Keeper |
| **Total** | **56** | |

### Selection Logic

Not all 56 agents activate for every project. The Orchestrator analyses the `business_brief` and selects only relevant agents. Typical activation:

| Project Type | Approximate Agent Count |
|---|---|
| Full SaaS product (web app, API, DB, payments, analytics) | 40–50 |
| Mobile app | 30–40 |
| CLI tool / library | 15–20 |
| Marketing website | 20–25 |
| Internal tool | 15–20 |
| API-only service | 20–25 |

Agents can be further subdivided (e.g., Junior/Senior variants, platform-specific specialists) to reach 100+ granular agents. The taxonomy supports this via role inheritance but the base 56 covers all essential domains.

---

## Dependency Graph (Simplified)

```
business_brief
    │
    ├─ Orchestrator ──────────────────────────┐
    │                                          │
    ├─ Chief Vision Officer                    │
    │   └─ Strategic Alignment Auditor         │
    │                                          │
    ├─ Market Researcher ─────────────────┐    │
    │   ├─ Competitor Analyst             │    │
    │   ├─ User Researcher                │    │
    │   └─ Pricing Analyst                │    │
    │                                      │    │
    ├─ Business Strategist ◄──────────────┘    │
    │   ├─ Monetization Strategist             │
    │   └─ Legal Compliance Officer            │
    │                                          │
    ├─ Brand Strategist                        │
    │   ├─ Content Strategist                  │
    │   └─ Marketing Lead                      │
    │       └─ SEO Specialist                  │
    │                                          │
    ├─ Product Manager ◄───────────────────┐   │
    │   ├─ Technical PM                    │   │
    │   └─ Scope Manager                   │   │
    │                                      │   │
    ├─ UX Designer ◄───────────────────────┤   │
    │   ├─ UI Designer                     │   │
    │   ├─ Design System Architect         │   │
    │   ├─ Interaction Designer            │   │
    │   └─ Accessibility Auditor           │   │
    │                                      │   │
    ├─ Software Architect ◄───────────────┘   │
    │   ├─ API Architect                      │
    │   └─ Data Architect                     │
    │                                          │
    ├─ Security Engineer                       │
    │   ├─ Penetration Tester                  │
    │   └─ Dependency Auditor                  │
    │                                          │
    ├─ Database Developer                      │
    │   ├─ Data Engineer                       │
    │   └─ ML Engineer                         │
    │                                          │
    ├─ Senior Frontend Developer ◄─────────┐   │
    │   ├─ Frontend Perf Engineer          │   │
    │   └─ Mobile Developer                │   │
    │                                      │   │
    ├─ Senior Backend Developer ◄──────────┤   │
    │   ├─ API Developer                   │   │
    │   └─ Integration Engineer            │   │
    │                                      │   │
    ├─ QA Engineer ◄───────────────────────┘   │
    │   ├─ Test Automation Engineer            │
    │   ├─ Performance Tester                  │
    │   └─ Visual QA Engineer                  │
    │                                          │
    ├─ DevOps Engineer                         │
    │   ├─ Infrastructure Engineer             │
    │   └─ Release Manager                     │
    │                                          │
    ├─ Observability Engineer                  │
    │   └─ SRE Engineer                        │
    │                                          │
    ├─ Growth Analyst                          │
    │   ├─ Analytics Engineer                  │
    │   └─ Conversion Optimizer                │
    │                                          │
    ├─ Customer Success Manager                │
    │   └─ Documentation Specialist            │
    │                                          │
    └─ Final Arbiter ◄────────────────────────┘
        ├─ Quality Gate Keeper
        └─ Conflict Resolver

    Project Memory Keeper (runs continuously across all)
```

### Parallel Execution Opportunities

Agents in different branches of the dependency graph run concurrently. Example from a SaaS product:

1. **Phase A (parallel):** Market Researcher, Competitor Analyst, User Researcher, Pricing Analyst
2. **Phase B (parallel):** Business Strategist, Brand Strategist, Legal Compliance Officer
3. **Phase C (parallel):** Product Manager, UX Designer, Security Engineer, Software Architect
4. **Phase D (parallel):** UI Designer, Design System Architect, API Architect, Data Architect, Database Developer
5. **Phase E (parallel):** Senior Frontend Developer, Senior Backend Developer, Mobile Developer
6. **Phase F (parallel):** All sub-engineers (API Dev, Integration Eng, Frontend Perf, Data Eng, ML Eng)
7. **Phase G (parallel):** QA Engineer, Test Automation, Performance Tester, Visual QA, Penetration Tester, Dependency Auditor, Accessibility Auditor
8. **Phase H (parallel):** DevOps Engineer, Infrastructure Engineer, Observability Engineer, SRE Engineer, Growth Analyst, Analytics Engineer, Documentation Specialist, Customer Success Manager
9. **Phase I:** Release Manager, Quality Gate Keeper
10. **Phase J:** Final Arbiter

Agents within each phase run concurrently where they don't depend on each other's outputs. This maximizes throughput while respecting dependency chains.
