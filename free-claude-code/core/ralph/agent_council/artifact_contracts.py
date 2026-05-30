"""Agent Council V2 — Artifact Contracts.

Built-in artifact contracts based on AGENT_COUNCIL_V2_ARTIFACT_CONTRACTS.md.
Each contract defines a shared artifact that agents pass between each other.

Validation ensures required fields exist, owner agent exists, consumers exist,
validation method is defined, and pass/fail criteria are present.
"""

from __future__ import annotations

from .models import ArtifactContract
from .registry import AgentRegistry

# ---------------------------------------------------------------------------
# Validation errors
# ---------------------------------------------------------------------------


class ArtifactValidationError(ValueError):
    """Raised when an artifact contract fails validation."""


# ---------------------------------------------------------------------------
# Built-in artifact contracts (33 core artifacts)
# ---------------------------------------------------------------------------


def _build_default_contracts() -> tuple[ArtifactContract, ...]:
    """Return the 33 core artifact contracts from the taxonomy."""
    return (
        # ---- Vision & Strategy ----
        ArtifactContract(
            artifact_id="business_brief",
            name="Business Brief",
            owner_agent="chief_vision_officer",
            description="Defines product vision, mission, value proposition, and business model.",
            required_fields=(
                "vision_statement", "mission_statement", "value_proposition",
                "target_market_summary", "business_model", "revenue_model",
                "strategic_goals", "success_metrics", "key_assumptions",
                "risks", "timeline_estimate",
            ),
            consumers=(
                "business_strategist", "market_researcher", "product_manager",
                "brand_strategist", "software_architect", "security_engineer",
                "growth_analyst", "final_arbiter", "orchestrator",
                "legal_compliance_officer", "strategic_alignment_auditor",
                "chief_product_ethics_officer",
            ),
            validation_method="All fields present, non-empty, internally consistent",
            pass_criteria=(
                "All required fields present",
                "Vision and business model do not contradict",
                "Success metrics are measurable",
            ),
            fail_criteria=(
                "Missing required fields",
                "Vision contradicts business model",
                "Success metrics not quantifiable",
            ),
        ),
        ArtifactContract(
            artifact_id="strategic_direction",
            name="Strategic Direction",
            owner_agent="chief_vision_officer",
            description="High-level strategic goals, principles, and decision framework.",
            required_fields=(
                "strategic_goals", "guiding_principles", "decision_framework",
                "priority_areas", "success_criteria",
            ),
            consumers=("product_manager", "software_architect", "final_arbiter"),
            validation_method="Strategic goals are specific; decision framework is actionable",
            pass_criteria=("Goals are measurable", "Principles are concrete", "Framework is usable"),
            fail_criteria=("Vague goals", "Principles are platitudes", "No decision framework"),
        ),

        # ---- Market Research ----
        ArtifactContract(
            artifact_id="market_research_report",
            name="Market Research Report",
            owner_agent="market_researcher",
            description="Comprehensive market analysis with sizing, trends, and opportunity assessment.",
            required_fields=(
                "market_size_tam", "market_size_sam", "market_size_som",
                "market_trends", "segment_analysis", "opportunity_assessment",
                "threat_assessment", "data_sources", "methodology_notes",
            ),
            consumers=("business_strategist", "product_manager", "competitor_analyst", "user_researcher"),
            validation_method="Data sources verified; claims checked against cited sources; TAM/SAM/SOM consistency",
            pass_criteria=(
                "All fields present",
                "Sources cited",
                "Market sizing has methodology",
                "Trends have evidence",
            ),
            fail_criteria=(
                "No sources cited",
                "TAM > SAM or SAM > SOM",
                "Claims contradict available data",
            ),
        ),
        ArtifactContract(
            artifact_id="competitor_map",
            name="Competitor Map",
            owner_agent="competitor_analyst",
            description="Competitive landscape mapping with feature comparison and positioning.",
            required_fields=(
                "direct_competitors", "indirect_competitors",
                "feature_comparison_matrix", "pricing_comparison",
                "positioning_map", "competitive_advantages",
                "competitive_disadvantages", "market_gaps",
                "data_collection_date",
            ),
            consumers=(
                "product_manager", "business_strategist", "brand_strategist",
                "pricing_analyst", "monetization_strategist",
            ),
            validation_method="Minimum 3 direct competitors; feature matrix has evidence; pricing sourced",
            pass_criteria=(
                "At least 3 competitors mapped",
                "Feature comparison is specific",
                "Pricing data included",
                "Gaps identified",
            ),
            fail_criteria=(
                "No direct competitors (unrealistic)",
                "Feature matrix empty",
                "No pricing data",
                "No gaps found",
            ),
        ),
        ArtifactContract(
            artifact_id="target_personas",
            name="Target Personas",
            owner_agent="user_researcher",
            description="Detailed user personas with goals, pain points, and jobs-to-be-done.",
            required_fields=("personas",),
            consumers=(
                "product_manager", "ux_designer", "brand_strategist",
                "content_strategist", "growth_analyst",
                "customer_success_manager",
            ),
            validation_method="Minimum 2 personas; each has all fields; JTBD are specific",
            pass_criteria=(
                "2+ distinct personas",
                "Pain points are evidence-backed",
                "JTBD are actionable",
                "Personas are differentiated",
            ),
            fail_criteria=(
                "Single persona only",
                "Personas are identical",
                "Pain points are generic",
                "JTBD too vague to act on",
            ),
        ),
        ArtifactContract(
            artifact_id="user_journey_maps",
            name="User Journey Maps",
            owner_agent="user_researcher",
            description="End-to-end user journey maps for each persona.",
            required_fields=("journeys",),
            consumers=("ux_designer", "product_manager", "customer_success_manager"),
            validation_method="Each journey has entry/exit; all stages covered; emotions mapped",
            pass_criteria=("Complete journeys for all personas", "Emotional states mapped", "Pain points identified"),
            fail_criteria=("Missing stages", "Personas not mapped", "No emotional mapping"),
        ),
        ArtifactContract(
            artifact_id="user_needs_analysis",
            name="User Needs Analysis",
            owner_agent="user_researcher",
            description="Analysis of user needs, pain points, and current solutions.",
            required_fields=("needs", "pain_points", "current_solutions", "opportunity_areas"),
            consumers=("product_manager", "ux_designer"),
            validation_method="Needs are specific; evidence provided; opportunities actionable",
            pass_criteria=("Needs evidence-backed", "Pain points specific", "Opportunities actionable"),
            fail_criteria=("Generic needs", "No evidence", "Opportunities vague"),
        ),

        # ---- Product Management ----
        ArtifactContract(
            artifact_id="product_requirements_doc",
            name="Product Requirements Document",
            owner_agent="product_manager",
            description="Complete product requirements with features, stories, and acceptance criteria.",
            required_fields=(
                "product_overview", "problem_statement", "solution_description",
                "feature_list", "scope_boundaries", "out_of_scope",
                "assumptions", "constraints", "dependencies",
                "mvp_definition", "post_mvp_features",
            ),
            consumers=(
                "software_architect", "ux_designer", "security_engineer",
                "qa_engineer", "senior_frontend_developer",
                "senior_backend_developer", "database_developer",
                "devops_engineer", "chief_product_ethics_officer",
                "legal_compliance_officer",
            ),
            validation_method="Feature completeness; acceptance criteria are testable; MVP defined; scope bounded",
            pass_criteria=(
                "All features have acceptance criteria",
                "MVP is clearly scoped",
                "Out-of-scope is explicit",
                "Stories follow INVEST",
            ),
            fail_criteria=(
                "Missing acceptance criteria",
                "Scope unbounded",
                "MVP undefined",
                "Features lack priority",
            ),
        ),
        ArtifactContract(
            artifact_id="user_stories",
            name="User Stories",
            owner_agent="product_manager",
            description="User stories with acceptance criteria in GIVEN/WHEN/THEN format.",
            required_fields=("epics", "stories"),
            consumers=("software_architect", "senior_frontend_developer", "senior_backend_developer", "qa_engineer"),
            validation_method="Each story linked to a persona; acceptance criteria specific and testable; priorities assigned",
            pass_criteria=("All stories have persona refs", "Acceptance criteria in GIVEN/WHEN/THEN format", "Dependencies explicit"),
            fail_criteria=("Stories without personas", "Acceptance criteria untestable", "Circular dependencies"),
        ),
        ArtifactContract(
            artifact_id="acceptance_criteria",
            name="Acceptance Criteria",
            owner_agent="product_manager",
            description="Per-feature acceptance criteria with edge cases and NFRs.",
            required_fields=("criteria",),
            consumers=("qa_engineer", "senior_frontend_developer", "senior_backend_developer", "final_arbiter"),
            validation_method="GIVEN/WHEN/THEN format check; edge cases identified; NFRs specified",
            pass_criteria=("All criteria in structured format", "Edge cases covered", "NFRs measurable"),
            fail_criteria=("Criteria in prose only", "No edge cases", "NFRs missing"),
        ),
        ArtifactContract(
            artifact_id="product_roadmap",
            name="Product Roadmap",
            owner_agent="product_manager",
            description="Prioritized product roadmap with timeline and milestones.",
            required_fields=("milestones", "timeline", "priorities", "dependencies"),
            consumers=("chief_vision_officer", "software_architect", "devops_engineer"),
            validation_method="Milestones measurable; timeline realistic; priorities reflect strategy",
            pass_criteria=("Clear milestones", "Realistic timeline", "Strategy-aligned priorities"),
            fail_criteria=("Vague milestones", "Unrealistic timeline", "Misaligned priorities"),
        ),

        # ---- Brand & Design ----
        ArtifactContract(
            artifact_id="brand_strategy",
            name="Brand Strategy",
            owner_agent="brand_strategist",
            description="Brand positioning, promise, values, personality, and voice.",
            required_fields=(
                "brand_positioning", "brand_promise", "brand_values",
                "brand_personality", "brand_voice_attributes",
                "target_audience_alignment", "competitive_differentiation",
                "brand_story",
            ),
            consumers=("ux_designer", "chief_vision_officer", "design_system_architect"),
            validation_method="Positioning statement specific; values actionable; voice attributes concrete",
            pass_criteria=("Positioning differentiated from competitors", "Values non-generic", "Voice usable by content team"),
            fail_criteria=("Positioning same as competitor", "Values are clichés", "Voice too vague to implement"),
        ),
        ArtifactContract(
            artifact_id="brand_book",
            name="Brand Book",
            owner_agent="brand_strategist",
            description="Complete brand guidelines: logo, color, typography, imagery, voice.",
            required_fields=(
                "brand_name", "logo_guidelines", "color_palette",
                "typography", "imagery_style", "iconography",
                "voice_and_tone", "brand_application_examples",
                "accessibility_notes",
            ),
            consumers=("ui_designer", "senior_frontend_developer", "design_system_architect"),
            validation_method="Color palette has accessible contrast ratios; typography web-safe; voice examples provided",
            pass_criteria=("Complete color system", "Typography with fallbacks", "Voice examples for 3+ contexts", "Accessibility considered"),
            fail_criteria=("Colors not meeting WCAG AA contrast", "No fallback fonts", "Voice examples missing"),
        ),
        ArtifactContract(
            artifact_id="content_strategy",
            name="Content Strategy",
            owner_agent="content_strategist",
            description="Content architecture, messaging framework, and editorial plan.",
            required_fields=(
                "content_pillars", "messaging_framework", "content_types",
                "editorial_calendar", "content_model",
                "information_hierarchy", "localization_strategy",
            ),
            consumers=("marketing_lead", "seo_specialist", "ux_designer", "documentation_specialist"),
            validation_method="Content pillars mapped to personas; messaging framework complete; content model structured",
            pass_criteria=("All pillars have sample content", "Messaging framework covers all personas", "Content model is structured"),
            fail_criteria=("Pillars not linked to personas", "Messaging inconsistent across channels", "No localization plan"),
        ),

        # ---- UX / UI ----
        ArtifactContract(
            artifact_id="UX_flow_map",
            name="UX Flow Map",
            owner_agent="ux_designer",
            description="Complete user flows with entry/exit points, decision points, and error states.",
            required_fields=("user_flows",),
            consumers=("product_manager", "qa_engineer", "senior_frontend_developer", "content_strategist", "ui_designer", "interaction_designer"),
            validation_method="Every flow has entry/exit; all states covered; each flow mapped to a persona",
            pass_criteria=("Complete flows for all core journeys", "Error states designed", "Decision logic explicit"),
            fail_criteria=("Missing error states", "Flows don't match personas", "Decision points ambiguous"),
        ),
        ArtifactContract(
            artifact_id="design_system",
            name="Design System",
            owner_agent="design_system_architect",
            description="Complete design system: tokens, components, patterns, spacing, typography, color.",
            required_fields=("design_tokens", "component_library"),
            consumers=("senior_frontend_developer", "qa_engineer", "visual_qa_engineer", "ui_designer"),
            validation_method="All tokens defined; components have all states; accessibility annotations; code references present",
            pass_criteria=("Complete token system", "15+ core components", "Each component has all states", "A11y annotations"),
            fail_criteria=("Missing token categories", "Components without states", "No accessibility annotations"),
        ),
        ArtifactContract(
            artifact_id="UI_spec",
            name="UI Specification",
            owner_agent="ui_designer",
            description="Complete visual designs for all screens with responsive layouts.",
            required_fields=(
                "visual_designs", "component_states", "responsive_layouts",
                "spacing_spec", "typography_application", "color_application",
                "interaction_notes", "design_system_compliance",
            ),
            consumers=("senior_frontend_developer", "qa_engineer", "visual_qa_engineer", "accessibility_auditor", "interaction_designer"),
            validation_method="All screens have visual designs; design system components used; responsive layouts present",
            pass_criteria=("Complete visual designs for all screens", "Design system compliance", "Responsive breakpoints"),
            fail_criteria=("Screens using non-design-system components", "Missing responsive layouts", "Color contrast failures"),
        ),
        ArtifactContract(
            artifact_id="accessibility_requirements",
            name="Accessibility Requirements",
            owner_agent="ux_designer",
            description="Accessibility requirements covering WCAG 2.2 AA standards.",
            required_fields=("wcag_level", "keyboard_navigation", "screen_reader_compatibility", "color_contrast_requirements"),
            consumers=("senior_frontend_developer", "accessibility_auditor", "design_system_architect"),
            validation_method="WCAG level specified; keyboard nav requirements detailed; screen reader requirements enumerated",
            pass_criteria=("WCAG 2.2 AA target", "All interaction patterns covered", "Contrast ratio requirements specified"),
            fail_criteria=("WCAG level not specified", "Keyboard nav ignored", "Screen reader not considered"),
        ),

        # ---- Architecture ----
        ArtifactContract(
            artifact_id="architecture_spec",
            name="Architecture Specification",
            owner_agent="software_architect",
            description="Complete system architecture with tech stack, service boundaries, and data flow.",
            required_fields=(
                "tech_stack", "system_diagram", "service_boundaries",
                "data_flow", "deployment_topology", "non_functional_requirements",
                "technology_decisions", "constraints", "trade_offs",
            ),
            consumers=(
                "senior_frontend_developer", "senior_backend_developer",
                "database_developer", "security_engineer",
                "devops_engineer", "observability_engineer",
                "api_architect", "data_architect",
            ),
            validation_method="Tech stack justified; service boundaries clear; NFRs specified; trade-offs documented",
            pass_criteria=("Complete tech stack with rationale", "Clear service boundaries", "NFRs measurable", "Trade-offs explicit"),
            fail_criteria=("Tech choices without rationale", "Monolith not justified", "NFRs missing", "No trade-off analysis"),
        ),
        ArtifactContract(
            artifact_id="API_contract",
            name="API Contract",
            owner_agent="api_architect",
            description="Complete API specification with endpoints, schemas, auth, and versioning.",
            required_fields=("endpoints", "versioning_strategy", "auth_scheme", "error_format", "rate_limiting"),
            consumers=(
                "senior_frontend_developer", "senior_backend_developer",
                "qa_engineer", "security_engineer", "api_developer",
                "documentation_specialist",
            ),
            validation_method="OpenAPI 3.x format; all endpoints have request/response/error schemas; auth specified",
            pass_criteria=("Complete API spec", "All endpoints have schemas", "Error format standardized", "Versioning defined"),
            fail_criteria=("Missing endpoints for product features", "Schemas incomplete", "No error standardization"),
        ),
        ArtifactContract(
            artifact_id="database_schema_spec",
            name="Database Schema Specification",
            owner_agent="database_developer",
            description="Complete database schema with tables, indexes, constraints, and migration strategy.",
            required_fields=("tables", "migration_strategy", "seed_data", "backup_strategy", "retention_policy"),
            consumers=("senior_backend_developer", "security_engineer", "data_engineer", "api_developer"),
            validation_method="Schema supports all product features; indexes on query paths; constraints enforced; migration path clear",
            pass_criteria=("Normalized schema (at least 3NF)", "Indexes on foreign keys", "Migration strategy defined"),
            fail_criteria=("Denormalized without justification", "Missing indexes", "No migration plan", "No retention policy"),
        ),
        ArtifactContract(
            artifact_id="data_architecture_spec",
            name="Data Architecture Specification",
            owner_agent="data_architect",
            description="Data architecture with storage strategy, caching, event sourcing, and pipelines.",
            required_fields=("storage_strategy", "caching_strategy", "data_models", "event_schema", "pipeline_architecture"),
            consumers=("database_developer", "data_engineer", "ml_engineer", "analytics_engineer"),
            validation_method="Storage strategy appropriate for data types; caching layers defined; event schema consistent",
            pass_criteria=("Complete storage strategy", "Caching layers defined", "Event schema documented", "Pipeline architecture clear"),
            fail_criteria=("No caching strategy", "Inconsistent event schema", "Storage strategy missing"),
        ),

        # ---- Security ----
        ArtifactContract(
            artifact_id="security_requirements",
            name="Security Requirements",
            owner_agent="security_engineer",
            description="Complete security requirements with threat model, auth, encryption, and scanning.",
            required_fields=(
                "threat_model", "auth_scheme", "authz_model",
                "data_protection_requirements", "encryption_standards",
                "secret_management", "vulnerability_scanning",
                "security_headers", "cors_policy", "csp_policy",
                "dependency_scanning", "audit_logging",
            ),
            consumers=(
                "software_architect", "senior_backend_developer",
                "senior_frontend_developer", "database_developer",
                "devops_engineer", "legal_compliance_officer",
                "penetration_tester",
            ),
            validation_method="Threat model covers OWASP Top 10; auth/authz specified; encryption standards named; audit logging designed",
            pass_criteria=("Complete threat model", "Auth scheme defined", "Encryption at rest and in transit", "CSP/CORS configured"),
            fail_criteria=("No threat model", "Auth not specified", "Plaintext secrets", "Missing security headers"),
        ),

        # ---- Engineering Plans ----
        ArtifactContract(
            artifact_id="frontend_implementation_plan",
            name="Frontend Implementation Plan",
            owner_agent="senior_frontend_developer",
            description="Frontend implementation plan with component tree, state management, routing, and performance.",
            required_fields=(
                "component_tree", "state_management_approach", "routing_spec",
                "api_integration_plan", "performance_budget", "bundle_optimization",
                "testing_strategy", "accessibility_implementation",
                "build_configuration", "deployment_instructions",
            ),
            consumers=("frontend_performance_engineer", "qa_engineer", "devops_engineer", "accessibility_auditor"),
            validation_method="All UI screens mapped to components; state management justified; performance budget set; a11y plan present",
            pass_criteria=("Complete component tree", "State management approach documented", "Bundle budget defined", "A11y plan actionable"),
            fail_criteria=("Components not mapped to UI screens", "No performance budget", "A11y not addressed", "Build config missing"),
        ),
        ArtifactContract(
            artifact_id="backend_implementation_plan",
            name="Backend Implementation Plan",
            owner_agent="senior_backend_developer",
            description="Backend implementation plan with service design, middleware, and background jobs.",
            required_fields=(
                "service_design", "api_implementation_approach", "middleware_stack",
                "background_jobs", "error_handling_strategy", "logging_strategy",
                "testing_strategy", "performance_targets", "deployment_considerations",
            ),
            consumers=("api_developer", "integration_engineer", "database_developer", "qa_engineer", "devops_engineer"),
            validation_method="All API endpoints implemented; error handling standardized; middleware documented; background jobs defined",
            pass_criteria=("Service design complete", "Middleware stack justified", "Error handling consistent", "Logging structured"),
            fail_criteria=("Endpoints not covered", "Error handling ad-hoc", "No background job strategy", "Logging unstructured"),
        ),

        # ---- QA ----
        ArtifactContract(
            artifact_id="test_plan",
            name="Test Plan",
            owner_agent="qa_engineer",
            description="Complete test plan with levels, cases, data, environments, and exit criteria.",
            required_fields=(
                "test_levels", "test_cases", "test_data",
                "test_environments", "automation_scope",
                "regression_suite", "defect_management", "exit_criteria",
            ),
            consumers=("senior_frontend_developer", "senior_backend_developer", "final_arbiter", "test_automation_engineer"),
            validation_method="All acceptance criteria have test cases; test levels defined; exit criteria explicit",
            pass_criteria=("Test cases cover all acceptance criteria", "Automation scope defined", "Exit criteria measurable"),
            fail_criteria=("Acceptance criteria without tests", "No regression suite", "Exit criteria vague"),
        ),
        ArtifactContract(
            artifact_id="QA_report",
            name="QA Report",
            owner_agent="qa_engineer",
            description="Complete QA results with pass/fail counts, defects, coverage, and release recommendation.",
            required_fields=(
                "test_summary", "passed_count", "failed_count",
                "blocked_count", "skipped_count", "defects",
                "test_coverage", "regression_results",
                "automation_results", "recommendations",
                "release_readiness_assessment",
            ),
            consumers=("release_manager", "final_arbiter", "product_manager"),
            validation_method="All test results reported; defects have severity/priority; coverage meets threshold",
            pass_criteria=("All critical tests pass", "Coverage >= 80%", "All defects triaged", "Release recommendation clear"),
            fail_criteria=("Critical tests failing", "Coverage below threshold", "Untriaged defects"),
        ),
        ArtifactContract(
            artifact_id="visual_QA_report",
            name="Visual QA Report",
            owner_agent="visual_qa_engineer",
            description="Visual QA results with pixel comparison, responsive, cross-browser, and dark mode checks.",
            required_fields=(
                "visual_regression_results", "responsive_breakpoint_results",
                "cross_browser_results", "dark_mode_results",
                "animation_fidelity", "design_system_compliance",
                "pixel_comparison_summary", "defects",
            ),
            consumers=("ui_designer", "senior_frontend_developer", "qa_engineer", "final_arbiter"),
            validation_method="All screens checked across breakpoints; dark mode verified; animations match spec",
            pass_criteria=("No visual regressions", "Responsive layouts match designs", "Dark mode consistent", ">= 95% design fidelity"),
            fail_criteria=("Visual regressions detected", "Breakpoint layout failures", "Dark mode broken", "Major design deviations"),
        ),
        ArtifactContract(
            artifact_id="performance_report",
            name="Performance Report",
            owner_agent="performance_tester",
            description="Load, stress, endurance, and scalability test results.",
            required_fields=(
                "load_test_results", "stress_test_results", "endurance_test_results",
                "scalability_analysis", "bottleneck_analysis",
                "response_time_percentiles", "throughput", "error_rate",
                "resource_utilization", "recommendations",
            ),
            consumers=("software_architect", "senior_backend_developer", "devops_engineer", "final_arbiter"),
            validation_method="Tests run at expected load; bottlenecks identified; recommendations specific",
            pass_criteria=("Response times within targets", "Error rate < 0.1%", "Bottlenecks documented", "Scalability headroom confirmed"),
            fail_criteria=("Response times exceed targets", "Error rate unacceptable", "Bottlenecks unidentified", "No scalability analysis"),
        ),

        # ---- Security Reports ----
        ArtifactContract(
            artifact_id="pentest_report",
            name="Penetration Test Report",
            owner_agent="penetration_tester",
            description="Penetration test results covering OWASP Top 10, injection, XSS, CSRF, and auth bypass.",
            required_fields=("tested_vectors", "findings", "severity_ratings", "remediation_recommendations"),
            consumers=("security_engineer", "senior_backend_developer", "final_arbiter"),
            validation_method="OWASP Top 10 covered; findings have severity; remediation is actionable",
            pass_criteria=("All vectors tested", "No critical findings", "Remediation plan complete"),
            fail_criteria=("Critical vulnerability found", "OWASP Top 10 not fully tested", "No remediation proposed"),
        ),
        ArtifactContract(
            artifact_id="dependency_audit_report",
            name="Dependency Audit Report",
            owner_agent="dependency_auditor",
            description="Third-party dependency audit: CVEs, licenses, maintenance status, supply chain risk.",
            required_fields=("dependencies_scanned", "cves_found", "license_issues", "supply_chain_risks", "recommendations"),
            consumers=("security_engineer", "legal_compliance_officer", "final_arbiter"),
            validation_method="All dependencies scanned; CVEs assessed; licenses verified; supply chain evaluated",
            pass_criteria=("No critical CVEs", "Licenses compliant", "All deps maintained", "Supply chain risk assessed"),
            fail_criteria=("Critical CVEs present", "License violations", "Unmaintained dependencies", "Supply chain not assessed"),
        ),

        # ---- Deployment & Release ----
        ArtifactContract(
            artifact_id="deployment_plan",
            name="Deployment Plan",
            owner_agent="devops_engineer",
            description="Complete deployment plan with CI/CD pipeline, environments, and rollback strategy.",
            required_fields=(
                "ci_cd_pipeline", "environment_strategy", "infrastructure_spec",
                "containerization", "orchestration", "secrets_management",
                "rollback_strategy", "health_checks", "monitoring_integration",
            ),
            consumers=("observability_engineer", "final_arbiter", "release_manager", "infrastructure_engineer"),
            validation_method="Pipeline covers build/test/deploy; environments defined; secrets managed; rollback tested",
            pass_criteria=("Complete CI/CD pipeline", "Environment parity", "Secrets not in config", "Rollback procedure documented"),
            fail_criteria=("Manual deployment steps", "No staging environment", "Secrets in config", "No rollback plan"),
        ),
        ArtifactContract(
            artifact_id="release_readiness_report",
            name="Release Readiness Report",
            owner_agent="release_manager",
            description="Final release assessment with all gate statuses, changelog, and go/no-go recommendation.",
            required_fields=(
                "release_version", "changelog", "all_gates_status",
                "QA_report_summary", "security_review_summary",
                "open_issues", "rollback_procedure",
                "go_no_go_recommendation", "stakeholder_signoffs",
            ),
            consumers=("final_arbiter", "product_manager", "devops_engineer"),
            validation_method="All gates checked; open issues triaged; rollback procedure current; changelog complete",
            pass_criteria=("All gates passing or waived with justification", "Open issues non-blocking", "Changelog complete"),
            fail_criteria=("Critical gate failing", "Blocking issues open", "Rollback not tested", "Changelog incomplete"),
        ),

        # ---- Growth & Analytics ----
        ArtifactContract(
            artifact_id="growth_strategy",
            name="Growth Strategy",
            owner_agent="growth_analyst",
            description="Growth strategy with acquisition channels, funnel, retention, and experimentation.",
            required_fields=("acquisition_channels", "activation_funnel", "retention_model", "referral_mechanics", "monetization_optimization", "kpis", "experimentation_roadmap"),
            consumers=("marketing_lead", "product_manager", "analytics_engineer", "conversion_optimizer"),
            validation_method="Funnel stages defined; KPIs measurable; experiments planned",
            pass_criteria=("Complete funnel with metrics", "Acquisition channels prioritized", "KPIs measurable", "Experiment roadmap"),
            fail_criteria=("Funnel not measurable", "No retention model", "KPIs vague", "No experiment plan"),
        ),
        ArtifactContract(
            artifact_id="analytics_spec",
            name="Analytics Specification",
            owner_agent="analytics_engineer",
            description="Analytics implementation with event tracking, taxonomy, and experimentation framework.",
            required_fields=("event_taxonomy", "tracking_plan", "experimentation_framework", "dashboard_specs"),
            consumers=("growth_analyst", "conversion_optimizer", "senior_frontend_developer"),
            validation_method="Key events tracked; experimentation framework defined; dashboards cover KPIs",
            pass_criteria=("Complete event taxonomy", "Tracking plan covers all KPIs", "Experimentation framework ready"),
            fail_criteria=("Key events missing", "No experimentation framework", "Privacy violations"),
        ),

        # ---- Observability ----
        ArtifactContract(
            artifact_id="observability_spec",
            name="Observability Specification",
            owner_agent="observability_engineer",
            description="Observability stack with logging, metrics, tracing, alerting, and SLOs.",
            required_fields=("logging_schema", "metrics", "traces", "dashboards", "alerts", "error_tracking", "slo_definitions", "on_call_rotation"),
            consumers=("sre_engineer", "devops_engineer", "senior_backend_developer"),
            validation_method="SLOs defined; alerts have runbooks; dashboards cover key metrics",
            pass_criteria=("Complete logging schema", "Metrics for all services", "SLOs for critical paths", "Alert runbooks"),
            fail_criteria=("No structured logging", "Critical metrics missing", "SLOs undefined", "No runbooks"),
        ),

        # ---- Ethics & Compliance ----
        ArtifactContract(
            artifact_id="ethics_audit_report",
            name="Ethics Audit Report",
            owner_agent="chief_product_ethics_officer",
            description="Ethics audit covering privacy, bias, accessibility, dark patterns, and sustainability.",
            required_fields=("privacy_assessment", "bias_audit", "accessibility_audit", "dark_pattern_audit", "sustainability_assessment", "findings", "remediation_required", "compliance_status"),
            consumers=("product_manager", "final_arbiter", "legal_compliance_officer"),
            validation_method="All audit dimensions covered; findings specific; remediation actionable",
            pass_criteria=("No critical ethics violations", "Privacy respected", "Bias assessed", "Accessibility addressed"),
            fail_criteria=("Critical ethics violations unaddressed", "Bias confirmed but not remediated", "Dark patterns detected"),
        ),
        ArtifactContract(
            artifact_id="compliance_requirements",
            name="Compliance Requirements",
            owner_agent="legal_compliance_officer",
            description="Legal compliance requirements for GDPR, CCPA, HIPAA, SOC2, PCI-DSS, etc.",
            required_fields=("applicable_regulations", "data_protection_requirements", "consent_requirements", "data_retention_policy", "data_deletion_policy", "breach_notification_procedure", "jurisdiction_notes", "required_documents"),
            consumers=("security_engineer", "database_developer", "devops_engineer", "product_manager"),
            validation_method="Regulations mapped to product features; required documents listed; procedures defined",
            pass_criteria=("All applicable regulations identified", "Procedures defined", "Documents specified"),
            fail_criteria=("Missing regulatory analysis", "No breach procedure", "No data retention/deletion policy"),
        ),

        # ---- Final Arbiter ----
        ArtifactContract(
            artifact_id="final_arbiter_decision",
            name="Final Arbiter Decision",
            owner_agent="final_arbiter",
            description="Final decision with evidence summary, conflict resolution, and next steps.",
            required_fields=(
                "decision", "evidence_summary", "conflicts_resolved",
                "conditions", "risk_acknowledgement", "rationale",
                "affected_artifacts", "next_steps",
            ),
            consumers=("chief_vision_officer", "product_manager", "devops_engineer", "orchestrator"),
            validation_method="All evidence cited; conflicts documented; rationale explicit; conditions specific",
            pass_criteria=("Decision supported by evidence", "All conflicts addressed", "Conditions actionable", "Rationale clear"),
            fail_criteria=("Decision without evidence", "Unresolved conflicts", "Vague conditions", "No rationale"),
        ),
    )


DEFAULT_CONTRACTS: tuple[ArtifactContract, ...] = _build_default_contracts()


# ---------------------------------------------------------------------------
# Registry of contracts
# ---------------------------------------------------------------------------


class ContractRegistry:
    """Immutable registry of artifact contracts."""

    def __init__(
        self,
        contracts: tuple[ArtifactContract, ...] | None = None,
        agent_registry: AgentRegistry | None = None,
    ) -> None:
        """Initialize with optional custom contracts and agent registry.

        Args:
            contracts: Optional tuple of ArtifactContract to use.
            agent_registry: Optional AgentRegistry for validation.
        """
        self._contracts: tuple[ArtifactContract, ...] = (
            contracts if contracts is not None else DEFAULT_CONTRACTS
        )
        self._by_id: dict[str, ArtifactContract] = {}
        self._by_owner: dict[str, tuple[ArtifactContract, ...]] = {}
        self._agent_registry = agent_registry
        self._build_indexes()
        if agent_registry is not None:
            self._validate_against_registry(agent_registry)

    def _build_indexes(self) -> None:
        for contract in self._contracts:
            self._by_id[contract.artifact_id] = contract
            self._by_owner.setdefault(contract.owner_agent, ())
            self._by_owner[contract.owner_agent] = (
                self._by_owner[contract.owner_agent] + (contract,)
            )

    def _validate_against_registry(self, registry: AgentRegistry) -> None:
        """Validate that owner agents and consumer agents exist in the registry."""
        agent_ids = set(registry.agent_ids)
        for contract in self._contracts:
            if contract.owner_agent not in agent_ids:
                raise ArtifactValidationError(
                    f"Artifact '{contract.artifact_id}': owner agent "
                    f"'{contract.owner_agent}' not found in registry"
                )
            for consumer_id in contract.consumers:
                if consumer_id not in agent_ids:
                    raise ArtifactValidationError(
                        f"Artifact '{contract.artifact_id}': consumer agent "
                        f"'{consumer_id}' not found in registry"
                    )

    def validate_contract(self, contract: ArtifactContract) -> list[str]:
        """Validate a single artifact contract. Returns list of error messages."""
        errors: list[str] = []
        if not contract.artifact_id:
            errors.append("artifact_id is empty")
        if not contract.owner_agent:
            errors.append("owner_agent is empty")
        if not contract.required_fields:
            errors.append("required_fields is empty")
        if not contract.consumers:
            errors.append("consumers is empty — artifact has no consumers")
        if not contract.validation_method:
            errors.append("validation_method is empty")
        if not contract.pass_criteria:
            errors.append("pass_criteria is empty — no pass conditions defined")
        if not contract.fail_criteria:
            errors.append("fail_criteria is empty — no fail conditions defined")
        return errors

    def validate_all(self) -> dict[str, list[str]]:
        """Validate all contracts. Returns {artifact_id: [errors]} for any failing contracts."""
        results: dict[str, list[str]] = {}
        for contract in self._contracts:
            errs = self.validate_contract(contract)
            if errs:
                results[contract.artifact_id] = errs
        return results

    # -- Lookups -------------------------------------------------------------

    def get(self, artifact_id: str) -> ArtifactContract:
        """Look up a contract by artifact ID. Raises KeyError if not found."""
        if artifact_id not in self._by_id:
            raise KeyError(f"Artifact '{artifact_id}' not found")
        return self._by_id[artifact_id]

    def get_optional(self, artifact_id: str) -> ArtifactContract | None:
        """Look up a contract by artifact ID, returning None if not found."""
        return self._by_id.get(artifact_id)

    def list_all(self) -> tuple[ArtifactContract, ...]:
        """Return all artifact contracts."""
        return self._contracts

    def list_by_owner(self, owner_agent: str) -> tuple[ArtifactContract, ...]:
        """Return contracts owned by a given agent."""
        return self._by_owner.get(owner_agent, ())

    @property
    def contract_count(self) -> int:
        """Number of registered contracts."""
        return len(self._contracts)

    @property
    def artifact_ids(self) -> tuple[str, ...]:
        """All artifact IDs."""
        return tuple(c.artifact_id for c in self._contracts)


# ---------------------------------------------------------------------------
# Convenience factory
# ---------------------------------------------------------------------------


def load_default_contracts(
    agent_registry: AgentRegistry | None = None,
) -> ContractRegistry:
    """Return a ContractRegistry with the default artifact contracts."""
    return ContractRegistry(agent_registry=agent_registry)
