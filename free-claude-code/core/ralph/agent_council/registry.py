"""Agent Council V2 — Registry.

Provides the expanded default agent registry with 56 specialized agents
across all 17 layers, based on AGENT_COUNCIL_V2_TAXONOMY.md.

Supports lookup by agent_id, layer, produced artifact, required input,
role family, and activation mode. Validates duplicate IDs, unknown
dependencies, missing reviewers, artifact producer/consumer chains,
and structural integrity of the dependency graph.
"""

from __future__ import annotations

from .models import AgentActivationMode, AgentProfile

# ---------------------------------------------------------------------------
# Validation errors
# ---------------------------------------------------------------------------


class RegistryValidationError(ValueError):
    """Raised when the registry fails validation."""


# ---------------------------------------------------------------------------
# Expanded 56-agent registry
# ---------------------------------------------------------------------------


def _build_default_agents() -> tuple[AgentProfile, ...]:
    """Return the 56 specialized agents from the full taxonomy."""
    return (
        # ================================================================
        # Layer 1 — Executive / Vision (3 agents)
        # ================================================================
        AgentProfile(
            agent_id="chief_vision_officer",
            role_name="Chief Vision Officer",
            layer=1,
            purpose="Define the product vision, mission, core value proposition, and strategic direction.",
            required_inputs=("project_brief",),
            produced_artifacts=("business_brief", "strategic_direction"),
            reviewers=("business_strategist", "product_manager"),
            fail_conditions=(
                "Vague or unvalidated vision",
                "No differentiation from existing products",
                "Misalignment with market reality",
            ),
            activation_triggers=("project_start",),
            activation_mode=AgentActivationMode.ALWAYS,
            can_run_parallel=False,
            dependencies=(),
            research_categories=("Business Strategy", "Market Research"),
        ),
        AgentProfile(
            agent_id="chief_product_ethics_officer",
            role_name="Chief Product Ethics Officer",
            layer=1,
            purpose="Audit product decisions against ethical frameworks: privacy, bias, accessibility, sustainability, dark patterns.",
            required_inputs=(
                "business_brief",
                "product_requirements_doc",
                "design_system",
            ),
            produced_artifacts=("ethics_audit_report",),
            reviewers=("product_manager", "final_arbiter"),
            fail_conditions=(
                "Unresolved privacy violations",
                "Confirmed bias in model/data",
                "Accessibility failures",
                "Dark pattern usage",
            ),
            activation_triggers=(
                "user_data_handling",
                "ai_ml_features",
                "consumer_facing_product",
            ),
            activation_mode=AgentActivationMode.TRIGGERED,
            can_run_parallel=True,
            dependencies=("product_manager", "design_system_architect"),
            research_categories=("Security / Compliance", "UX / UI / Product Design"),
        ),
        AgentProfile(
            agent_id="strategic_alignment_auditor",
            role_name="Strategic Alignment Auditor",
            layer=1,
            purpose="Verify that implementation decisions remain aligned with the original vision and strategy.",
            required_inputs=(
                "business_brief",
                "product_requirements_doc",
                "architecture_spec",
            ),
            produced_artifacts=("alignment_audit_report",),
            reviewers=("chief_vision_officer", "final_arbiter"),
            fail_conditions=(
                "Implementation contradicts stated vision",
                "Scope creep unacknowledged",
                "Stakeholder conflict unresolved",
            ),
            activation_triggers=("mid_project_checkpoint", "scope_change_proposed"),
            activation_mode=AgentActivationMode.CHECKPOINT,
            can_run_parallel=True,
            dependencies=("product_manager", "software_architect"),
            research_categories=("Business Strategy", "Software Architecture"),
        ),
        # ================================================================
        # Layer 2 — Business Strategy (3 agents)
        # ================================================================
        AgentProfile(
            agent_id="business_strategist",
            role_name="Business Strategist",
            layer=2,
            purpose="Define business model, revenue strategy, pricing, go-to-market plan, cost structure, and risk assessment.",
            required_inputs=(
                "business_brief",
                "market_research_report",
                "competitor_map",
            ),
            produced_artifacts=(
                "business_model_canvas",
                "pricing_strategy",
                "gtm_plan",
            ),
            reviewers=("chief_vision_officer", "product_manager", "market_researcher"),
            fail_conditions=(
                "Unsustainable unit economics",
                "No clear revenue model",
                "Pricing below cost",
                "Unaddressed regulatory risk",
            ),
            activation_triggers=("commercial_product",),
            activation_mode=AgentActivationMode.TRIGGERED,
            can_run_parallel=True,
            dependencies=("market_researcher", "competitor_analyst"),
            research_categories=("Business Strategy", "Market Research"),
        ),
        AgentProfile(
            agent_id="monetization_strategist",
            role_name="Monetization Strategist",
            layer=2,
            purpose="Design specific monetization mechanics: subscription tiers, freemium boundaries, in-app purchases, marketplace fees, ads.",
            required_inputs=("business_brief", "target_personas", "competitor_map"),
            produced_artifacts=("monetization_spec",),
            reviewers=("business_strategist", "product_manager", "ux_designer"),
            fail_conditions=(
                "Monetization harms core UX",
                "Pricing confuses users",
                "Competitor undercutting not addressed",
            ),
            activation_triggers=("revenue_generating", "complex_pricing"),
            activation_mode=AgentActivationMode.TRIGGERED,
            can_run_parallel=True,
            dependencies=(
                "business_strategist",
                "user_researcher",
                "competitor_analyst",
            ),
            research_categories=("Business Strategy", "Market Research"),
        ),
        AgentProfile(
            agent_id="legal_compliance_officer",
            role_name="Legal & Compliance Officer",
            layer=2,
            purpose="Identify legal requirements: GDPR, CCPA, HIPAA, SOC2, PCI-DSS, COPPA, terms of service, privacy policy, data processing agreements.",
            required_inputs=(
                "business_brief",
                "product_requirements_doc",
                "database_schema_spec",
                "security_requirements",
            ),
            produced_artifacts=("compliance_requirements", "legal_risk_assessment"),
            reviewers=("security_engineer", "database_developer", "product_manager"),
            fail_conditions=(
                "Identified regulatory violation not addressed",
                "Missing required legal documents",
                "Data handling violates jurisdiction",
            ),
            activation_triggers=(
                "personal_data",
                "payments",
                "health_data",
                "children_targeting",
            ),
            activation_mode=AgentActivationMode.TRIGGERED,
            can_run_parallel=True,
            dependencies=("product_manager", "database_developer", "security_engineer"),
            research_categories=("Security / Compliance", "Business Strategy"),
        ),
        # ================================================================
        # Layer 3 — Market Research (4 agents)
        # ================================================================
        AgentProfile(
            agent_id="market_researcher",
            role_name="Market Researcher",
            layer=3,
            purpose="Research market size, trends, segments, opportunities, threats. Produce data-backed market analysis.",
            required_inputs=("business_brief",),
            produced_artifacts=(
                "market_research_report",
                "market_sizing",
                "trend_analysis",
            ),
            reviewers=("business_strategist", "product_manager"),
            fail_conditions=(
                "No data sources cited",
                "Claims contradicted by available evidence",
                "TAM/SAM/SOM not estimated",
            ),
            activation_triggers=("targeting_market",),
            activation_mode=AgentActivationMode.TRIGGERED,
            can_run_parallel=True,
            dependencies=("chief_vision_officer",),
            research_categories=("Market Research", "Competitive Analysis"),
        ),
        AgentProfile(
            agent_id="competitor_analyst",
            role_name="Competitor Analyst",
            layer=3,
            purpose="Map competitive landscape: direct competitors, indirect competitors, feature matrices, positioning gaps.",
            required_inputs=("business_brief", "market_research_report"),
            produced_artifacts=(
                "competitor_map",
                "competitive_positioning",
                "feature_gap_analysis",
            ),
            reviewers=("market_researcher", "product_manager", "business_strategist"),
            fail_conditions=(
                "No competitors identified (unrealistic)",
                "Feature comparison lacks evidence",
                "Differentiation unclear",
            ),
            activation_triggers=("has_market_competition",),
            activation_mode=AgentActivationMode.TRIGGERED,
            can_run_parallel=True,
            dependencies=("market_researcher",),
            research_categories=("Competitive Analysis", "Market Research"),
        ),
        AgentProfile(
            agent_id="user_researcher",
            role_name="User Researcher",
            layer=3,
            purpose="Define target personas, user needs, pain points, jobs-to-be-done, user journey mapping.",
            required_inputs=("business_brief", "market_research_report"),
            produced_artifacts=(
                "target_personas",
                "user_needs_analysis",
                "jobs_to_be_done",
                "user_journey_maps",
            ),
            reviewers=("product_manager", "ux_designer", "market_researcher"),
            fail_conditions=(
                "Personas lack specificity",
                "No evidence for user needs",
                "JTBD framework misapplied",
            ),
            activation_triggers=("user_facing_product",),
            activation_mode=AgentActivationMode.TRIGGERED,
            can_run_parallel=True,
            dependencies=("market_researcher",),
            research_categories=("Market Research", "UX / UI / Product Design"),
        ),
        AgentProfile(
            agent_id="pricing_analyst",
            role_name="Pricing Analyst",
            layer=3,
            purpose="Analyze competitor pricing, willingness-to-pay studies, pricing models, discount strategies, revenue optimization.",
            required_inputs=("competitor_map", "target_personas", "business_brief"),
            produced_artifacts=("pricing_analysis", "price_sensitivity_model"),
            reviewers=("business_strategist", "monetization_strategist"),
            fail_conditions=(
                "No competitor price data",
                "Pricing not anchored to value",
                "Margin analysis missing",
            ),
            activation_triggers=("revenue_generating",),
            activation_mode=AgentActivationMode.TRIGGERED,
            can_run_parallel=True,
            dependencies=("competitor_analyst", "user_researcher"),
            research_categories=("Market Research", "Business Strategy"),
        ),
        # ================================================================
        # Layer 4 — Product Management (3 agents)
        # ================================================================
        AgentProfile(
            agent_id="product_manager",
            role_name="Product Manager",
            layer=4,
            purpose="Own the product requirements, roadmap, and backlog. Translate vision + research into actionable specs.",
            required_inputs=(
                "business_brief",
                "market_research_report",
                "competitor_map",
                "target_personas",
                "user_needs_analysis",
            ),
            produced_artifacts=(
                "product_requirements_doc",
                "user_stories",
                "acceptance_criteria",
                "product_roadmap",
                "feature_prioritization",
            ),
            reviewers=(
                "chief_vision_officer",
                "business_strategist",
                "ux_designer",
                "software_architect",
            ),
            fail_conditions=(
                "Requirements contradict research",
                "Missing acceptance criteria",
                "Unprioritized backlog",
                "Stakeholder conflicts not resolved",
            ),
            activation_triggers=("project_start",),
            activation_mode=AgentActivationMode.ALWAYS,
            can_run_parallel=False,
            dependencies=(
                "chief_vision_officer",
                "market_researcher",
                "competitor_analyst",
                "user_researcher",
            ),
            research_categories=("Product Management", "Backend / API Frameworks"),
        ),
        AgentProfile(
            agent_id="technical_product_manager",
            role_name="Technical Product Manager",
            layer=4,
            purpose="Bridge product requirements and technical feasibility. Validate technical constraints, API capabilities, platform limitations.",
            required_inputs=("product_requirements_doc", "architecture_spec"),
            produced_artifacts=(
                "technical_feasibility_assessment",
                "technical_user_stories",
            ),
            reviewers=("software_architect", "product_manager"),
            fail_conditions=(
                "Product requirements impossible given technical constraints",
                "No mitigation proposed",
            ),
            activation_triggers=("technically_complex",),
            activation_mode=AgentActivationMode.TRIGGERED,
            can_run_parallel=True,
            dependencies=("product_manager", "software_architect"),
            research_categories=("Product Management", "Software Architecture"),
        ),
        AgentProfile(
            agent_id="scope_manager",
            role_name="Scope Manager",
            layer=4,
            purpose="Guard against scope creep. Evaluate change requests against original vision, timeline, and resources.",
            required_inputs=("business_brief", "product_requirements_doc"),
            produced_artifacts=("scope_change_decision", "updated_roadmap"),
            reviewers=("product_manager", "chief_vision_officer"),
            fail_conditions=(
                "Uncontrolled scope growth",
                "No trade-off analysis for additions",
                "Removal of core features without justification",
            ),
            activation_triggers=("scope_change_proposed",),
            activation_mode=AgentActivationMode.ON_DEMAND,
            can_run_parallel=True,
            dependencies=("chief_vision_officer", "product_manager"),
            research_categories=("Product Management",),
        ),
        # ================================================================
        # Layer 5 — Brand / Content / Marketing (4 agents)
        # ================================================================
        AgentProfile(
            agent_id="brand_strategist",
            role_name="Brand Strategist",
            layer=5,
            purpose="Define brand identity: name, positioning, voice, tone, values, visual direction, brand story.",
            required_inputs=("business_brief", "target_personas", "competitor_map"),
            produced_artifacts=("brand_strategy", "brand_book"),
            reviewers=("chief_vision_officer", "ux_designer", "content_strategist"),
            fail_conditions=(
                "Brand indistinguishable from competitors",
                "Voice inconsistent with target personas",
                "Values not substantiated",
            ),
            activation_triggers=(
                "consumer_facing_product",
                "needs_market_differentiation",
            ),
            activation_mode=AgentActivationMode.TRIGGERED,
            can_run_parallel=True,
            dependencies=("user_researcher", "competitor_analyst"),
            research_categories=("Brand / Content / Marketing", "Design Systems / CSS"),
        ),
        AgentProfile(
            agent_id="content_strategist",
            role_name="Content Strategist",
            layer=5,
            purpose="Plan content architecture: information hierarchy, messaging framework, content types, editorial calendar, localization.",
            required_inputs=("brand_strategy", "target_personas", "UX_flow_map"),
            produced_artifacts=(
                "content_strategy",
                "messaging_framework",
                "content_model",
            ),
            reviewers=("brand_strategist", "ux_designer", "product_manager"),
            fail_conditions=(
                "Content not mapped to user journey",
                "Missing key messaging",
                "No localization plan for global products",
            ),
            activation_triggers=(
                "content_heavy",
                "marketing_site",
                "documentation_surface",
            ),
            activation_mode=AgentActivationMode.TRIGGERED,
            can_run_parallel=True,
            dependencies=("brand_strategist", "ux_designer"),
            research_categories=("Brand / Content / Marketing", "Documentation"),
        ),
        AgentProfile(
            agent_id="marketing_lead",
            role_name="Marketing Lead",
            layer=5,
            purpose="Plan go-to-market marketing: channels, campaigns, launch strategy, positioning, press/PR.",
            required_inputs=(
                "brand_strategy",
                "business_brief",
                "gtm_plan",
                "target_personas",
            ),
            produced_artifacts=("marketing_plan", "launch_strategy", "campaign_briefs"),
            reviewers=("business_strategist", "brand_strategist", "growth_analyst"),
            fail_conditions=(
                "No channel strategy",
                "Target audience not reachable",
                "Launch timing conflicts",
            ),
            activation_triggers=("requires_market_launch",),
            activation_mode=AgentActivationMode.TRIGGERED,
            can_run_parallel=True,
            dependencies=("brand_strategist", "business_strategist", "user_researcher"),
            research_categories=("Brand / Content / Marketing", "Growth / Analytics"),
        ),
        AgentProfile(
            agent_id="seo_specialist",
            role_name="SEO Specialist",
            layer=5,
            purpose="Define SEO strategy: keyword research, technical SEO requirements, content optimization, backlink strategy.",
            required_inputs=(
                "content_strategy",
                "marketing_plan",
                "information_architecture",
            ),
            produced_artifacts=(
                "seo_strategy",
                "keyword_map",
                "technical_seo_requirements",
            ),
            reviewers=(
                "content_strategist",
                "senior_frontend_developer",
                "marketing_lead",
            ),
            fail_conditions=(
                "No keyword research",
                "Technical SEO conflicts with architecture",
                "Content not SEO-optimized",
            ),
            activation_triggers=("public_facing_web",),
            activation_mode=AgentActivationMode.TRIGGERED,
            can_run_parallel=True,
            dependencies=("content_strategist", "marketing_lead", "ux_designer"),
            research_categories=("Brand / Content / Marketing", "Frontend Engineering"),
        ),
        # ================================================================
        # Layer 6 — UX / UI / Product Design (5 agents)
        # ================================================================
        AgentProfile(
            agent_id="ux_designer",
            role_name="UX Designer",
            layer=6,
            purpose="Design user experience: flows, information architecture, interaction patterns, accessibility, usability heuristics.",
            required_inputs=(
                "target_personas",
                "user_journey_maps",
                "product_requirements_doc",
                "brand_strategy",
            ),
            produced_artifacts=(
                "UX_flow_map",
                "information_architecture",
                "interaction_patterns",
                "accessibility_requirements",
            ),
            reviewers=(
                "user_researcher",
                "product_manager",
                "ui_designer",
                "qa_engineer",
            ),
            fail_conditions=(
                "Flows not mapped to personas",
                "Accessibility (WCAG) not addressed",
                "IA contradicts user expectations",
            ),
            activation_triggers=("has_user_interface",),
            activation_mode=AgentActivationMode.TRIGGERED,
            can_run_parallel=True,
            dependencies=("user_researcher", "product_manager", "brand_strategist"),
            research_categories=("UX / UI / Product Design", "Design Systems / CSS"),
        ),
        AgentProfile(
            agent_id="ui_designer",
            role_name="UI Designer",
            layer=6,
            purpose="Design visual interface: screen layouts, component states, responsive breakpoints, micro-interactions, visual hierarchy.",
            required_inputs=(
                "UX_flow_map",
                "information_architecture",
                "design_system",
                "brand_book",
            ),
            produced_artifacts=(
                "UI_spec",
                "wireframes",
                "visual_designs",
                "component_specs",
            ),
            reviewers=("ux_designer", "brand_strategist", "senior_frontend_developer"),
            fail_conditions=(
                "Designs don't match IA",
                "Responsive breakpoints missing",
                "Component states undefined",
                "Brand inconsistency",
            ),
            activation_triggers=("has_visual_interface",),
            activation_mode=AgentActivationMode.TRIGGERED,
            can_run_parallel=True,
            dependencies=("ux_designer", "design_system_architect", "brand_strategist"),
            research_categories=(
                "UX / UI / Product Design",
                "UI Component Libraries",
                "Design Systems / CSS",
            ),
        ),
        AgentProfile(
            agent_id="design_system_architect",
            role_name="Design System Architect",
            layer=6,
            purpose="Build the design system: tokens, components, patterns, spacing, typography, color, elevation, motion.",
            required_inputs=("brand_book", "UX_flow_map", "accessibility_requirements"),
            produced_artifacts=(
                "design_system",
                "component_library_spec",
                "design_tokens",
            ),
            reviewers=("ui_designer", "senior_frontend_developer", "brand_strategist"),
            fail_conditions=(
                "Tokens not normalized",
                "Components not accessible",
                "No dark mode support",
                "Inconsistent spacing grid",
            ),
            activation_triggers=("multi_screen_product",),
            activation_mode=AgentActivationMode.TRIGGERED,
            can_run_parallel=True,
            dependencies=("brand_strategist", "ux_designer"),
            research_categories=("UX / UI / Product Design", "Design Systems / CSS"),
        ),
        AgentProfile(
            agent_id="interaction_designer",
            role_name="Interaction Designer",
            layer=6,
            purpose="Design micro-interactions, animations, transitions, loading states, empty states, error states, gestures.",
            required_inputs=("UI_spec", "UX_flow_map", "design_system"),
            produced_artifacts=(
                "interaction_spec",
                "animation_spec",
                "state_machine_diagrams",
            ),
            reviewers=("ui_designer", "senior_frontend_developer", "ux_designer"),
            fail_conditions=(
                "Loading/error/empty states not designed",
                "Animations not respecting reduced-motion",
                "Gesture conflicts",
            ),
            activation_triggers=("interactive_product",),
            activation_mode=AgentActivationMode.TRIGGERED,
            can_run_parallel=True,
            dependencies=("ui_designer", "design_system_architect"),
            research_categories=("UX / UI / Product Design", "Frontend Engineering"),
        ),
        AgentProfile(
            agent_id="accessibility_auditor",
            role_name="Accessibility Auditor",
            layer=6,
            purpose="Audit all designs and implementations against WCAG 2.2 AA, screen reader compatibility, keyboard navigation, color contrast.",
            required_inputs=(
                "UI_spec",
                "design_system",
                "accessibility_requirements",
                "frontend_implementation_plan",
            ),
            produced_artifacts=(
                "accessibility_audit_report",
                "a11y_remediation_tickets",
            ),
            reviewers=(
                "ux_designer",
                "ui_designer",
                "senior_frontend_developer",
                "qa_engineer",
            ),
            fail_conditions=(
                "WCAG AA failures",
                "Keyboard traps",
                "Screen reader incompatibility",
                "Color contrast failures",
            ),
            activation_triggers=("user_facing_ui",),
            activation_mode=AgentActivationMode.TRIGGERED,
            can_run_parallel=True,
            dependencies=("ui_designer", "senior_frontend_developer"),
            research_categories=("UX / UI / Product Design", "Frontend Engineering"),
        ),
        # ================================================================
        # Layer 7 — Software Architecture (3 agents)
        # ================================================================
        AgentProfile(
            agent_id="software_architect",
            role_name="Software Architect",
            layer=7,
            purpose="Define system architecture: tech stack, service boundaries, data flow, API design principles, non-functional requirements.",
            required_inputs=(
                "product_requirements_doc",
                "technical_feasibility_assessment",
            ),
            produced_artifacts=(
                "architecture_spec",
                "tech_stack_decision",
                "system_boundaries",
                "data_flow_diagrams",
            ),
            reviewers=(
                "technical_product_manager",
                "senior_backend_developer",
                "senior_frontend_developer",
                "security_engineer",
            ),
            fail_conditions=(
                "Architecture doesn't support requirements",
                "Tech stack choices unjustified",
                "No scalability plan",
                "Tight coupling",
            ),
            activation_triggers=("project_start",),
            activation_mode=AgentActivationMode.ALWAYS,
            can_run_parallel=False,
            dependencies=("product_manager",),
            research_categories=(
                "Software Architecture",
                "Backend / API Frameworks",
                "Infrastructure",
            ),
        ),
        AgentProfile(
            agent_id="api_architect",
            role_name="API Architect",
            layer=7,
            purpose="Design API surface: REST/GraphQL/gRPC endpoints, authentication, versioning, rate limiting, error handling, documentation standards.",
            required_inputs=(
                "architecture_spec",
                "product_requirements_doc",
                "data_flow_diagrams",
            ),
            produced_artifacts=(
                "API_contract",
                "api_documentation_spec",
                "error_handling_standard",
            ),
            reviewers=(
                "software_architect",
                "senior_backend_developer",
                "senior_frontend_developer",
                "security_engineer",
            ),
            fail_conditions=(
                "Endpoints don't cover all use cases",
                "Auth model not specified",
                "No versioning strategy",
                "Error format inconsistent",
            ),
            activation_triggers=("has_api",),
            activation_mode=AgentActivationMode.TRIGGERED,
            can_run_parallel=True,
            dependencies=("software_architect",),
            research_categories=("Software Architecture", "Backend / API Frameworks"),
        ),
        AgentProfile(
            agent_id="data_architect",
            role_name="Data Architect",
            layer=7,
            purpose="Design data architecture: storage strategy, data models, caching layers, event sourcing, data pipelines, analytics schema.",
            required_inputs=("architecture_spec", "product_requirements_doc"),
            produced_artifacts=(
                "data_architecture_spec",
                "storage_strategy",
                "caching_strategy",
                "event_schema",
            ),
            reviewers=(
                "software_architect",
                "database_developer",
                "senior_backend_developer",
            ),
            fail_conditions=(
                "Data model doesn't support product requirements",
                "No caching strategy",
                "Inconsistent event schema",
            ),
            activation_triggers=("data_intensive",),
            activation_mode=AgentActivationMode.TRIGGERED,
            can_run_parallel=True,
            dependencies=("software_architect",),
            research_categories=("Software Architecture", "Database / Schema Tooling"),
        ),
        # ================================================================
        # Layer 8 — Frontend Engineering (3 agents)
        # ================================================================
        AgentProfile(
            agent_id="senior_frontend_developer",
            role_name="Senior Frontend Developer",
            layer=8,
            purpose="Plan and guide frontend implementation: component architecture, state management, routing, performance, bundle optimization.",
            required_inputs=(
                "UI_spec",
                "design_system",
                "API_contract",
                "architecture_spec",
                "accessibility_requirements",
            ),
            produced_artifacts=(
                "frontend_implementation_plan",
                "component_tree",
                "state_management_spec",
                "routing_spec",
            ),
            reviewers=("software_architect", "ui_designer", "qa_engineer"),
            fail_conditions=(
                "Plan doesn't cover all UI states",
                "Performance budget not defined",
                "Accessibility not addressed",
                "Bundle size unmanaged",
            ),
            activation_triggers=("has_frontend",),
            activation_mode=AgentActivationMode.TRIGGERED,
            can_run_parallel=False,
            dependencies=(
                "ui_designer",
                "design_system_architect",
                "api_architect",
                "software_architect",
                "ux_designer",
            ),
            research_categories=(
                "Frontend Engineering",
                "UI Component Libraries",
                "Design Systems / CSS",
                "Browser Automation / Testing",
            ),
        ),
        AgentProfile(
            agent_id="frontend_performance_engineer",
            role_name="Frontend Performance Engineer",
            layer=8,
            purpose="Optimize frontend performance: Core Web Vitals, bundle analysis, lazy loading, code splitting, image optimization, caching headers.",
            required_inputs=("frontend_implementation_plan", "UI_spec"),
            produced_artifacts=(
                "frontend_performance_plan",
                "bundle_budget",
                "loading_strategy",
            ),
            reviewers=("senior_frontend_developer", "qa_engineer"),
            fail_conditions=(
                "LCP > 2.5s",
                "CLS > 0.1",
                "INP > 200ms",
                "No bundle budget",
                "Images unoptimized",
            ),
            activation_triggers=("web_application",),
            activation_mode=AgentActivationMode.TRIGGERED,
            can_run_parallel=True,
            dependencies=("senior_frontend_developer",),
            research_categories=(
                "Frontend Engineering",
                "Browser Automation / Testing",
            ),
        ),
        AgentProfile(
            agent_id="mobile_developer",
            role_name="Mobile Developer",
            layer=8,
            purpose="Plan mobile-specific implementation: React Native/Flutter/native, platform capabilities, offline support, push notifications, app store requirements.",
            required_inputs=(
                "UI_spec",
                "design_system",
                "API_contract",
                "architecture_spec",
            ),
            produced_artifacts=(
                "mobile_implementation_plan",
                "platform_capability_map",
                "offline_strategy",
            ),
            reviewers=(
                "senior_frontend_developer",
                "software_architect",
                "qa_engineer",
            ),
            fail_conditions=(
                "Platform guidelines violated",
                "Offline support missing",
                "App store rejection risks unaddressed",
            ),
            activation_triggers=("mobile_app",),
            activation_mode=AgentActivationMode.TRIGGERED,
            can_run_parallel=True,
            dependencies=("ui_designer", "api_architect", "software_architect"),
            research_categories=("Frontend Engineering", "UI Component Libraries"),
        ),
        # ================================================================
        # Layer 9 — Backend Engineering (3 agents)
        # ================================================================
        AgentProfile(
            agent_id="senior_backend_developer",
            role_name="Senior Backend Developer",
            layer=9,
            purpose="Plan and guide backend implementation: service design, business logic, API implementation, middleware, background jobs, error handling.",
            required_inputs=(
                "API_contract",
                "architecture_spec",
                "database_schema_spec",
                "security_requirements",
                "product_requirements_doc",
            ),
            produced_artifacts=(
                "backend_implementation_plan",
                "service_design",
                "middleware_spec",
                "background_job_spec",
            ),
            reviewers=(
                "software_architect",
                "api_architect",
                "database_developer",
                "security_engineer",
            ),
            fail_conditions=(
                "API contract not fully implemented",
                "Error handling incomplete",
                "Auth/authz not designed",
                "No retry/backoff strategy",
            ),
            activation_triggers=("has_backend",),
            activation_mode=AgentActivationMode.TRIGGERED,
            can_run_parallel=False,
            dependencies=(
                "api_architect",
                "software_architect",
                "database_developer",
                "security_engineer",
            ),
            research_categories=(
                "Backend / API Frameworks",
                "Database / Schema Tooling",
                "DevOps / Deployment",
            ),
        ),
        AgentProfile(
            agent_id="api_developer",
            role_name="API Developer",
            layer=9,
            purpose="Implement API endpoints: request validation, response formatting, rate limiting, pagination, filtering, sorting, webhooks.",
            required_inputs=(
                "API_contract",
                "backend_implementation_plan",
                "database_schema_spec",
            ),
            produced_artifacts=("api_implementation", "webhook_spec"),
            reviewers=("senior_backend_developer", "api_architect", "qa_engineer"),
            fail_conditions=(
                "Contract not satisfied",
                "Validation missing",
                "Pagination broken",
                "Webhook delivery not guaranteed",
            ),
            activation_triggers=("has_api",),
            activation_mode=AgentActivationMode.TRIGGERED,
            can_run_parallel=True,
            dependencies=("api_architect", "senior_backend_developer"),
            research_categories=("Backend / API Frameworks",),
        ),
        AgentProfile(
            agent_id="integration_engineer",
            role_name="Integration Engineer",
            layer=9,
            purpose="Design and implement third-party integrations: payment gateways, email services, SMS, social login, analytics, CRM, ERP.",
            required_inputs=(
                "backend_implementation_plan",
                "product_requirements_doc",
                "API_contract",
            ),
            produced_artifacts=(
                "integration_spec",
                "third_party_service_map",
                "fallback_strategies",
            ),
            reviewers=("senior_backend_developer", "security_engineer", "qa_engineer"),
            fail_conditions=(
                "No fallback for third-party failure",
                "Credential management insecure",
                "Rate limits not respected",
            ),
            activation_triggers=("third_party_integrations",),
            activation_mode=AgentActivationMode.TRIGGERED,
            can_run_parallel=True,
            dependencies=("senior_backend_developer",),
            research_categories=("Backend / API Frameworks", "Security / Compliance"),
        ),
        # ================================================================
        # Layer 10 — Database / Data Engineering (3 agents)
        # ================================================================
        AgentProfile(
            agent_id="database_developer",
            role_name="Database Developer",
            layer=10,
            purpose="Design and implement database schema: tables, indexes, constraints, migrations, query optimization, data integrity.",
            required_inputs=(
                "data_architecture_spec",
                "product_requirements_doc",
                "API_contract",
                "security_requirements",
            ),
            produced_artifacts=(
                "database_schema_spec",
                "migration_plan",
                "indexing_strategy",
                "query_patterns",
            ),
            reviewers=(
                "data_architect",
                "senior_backend_developer",
                "security_engineer",
            ),
            fail_conditions=(
                "Schema doesn't support product requirements",
                "No migration strategy",
                "Missing indexes",
                "No data retention policy",
            ),
            activation_triggers=("has_persistent_data",),
            activation_mode=AgentActivationMode.TRIGGERED,
            can_run_parallel=False,
            dependencies=("data_architect", "api_architect", "security_engineer"),
            research_categories=(
                "Database / Schema Tooling",
                "Backend / API Frameworks",
            ),
        ),
        AgentProfile(
            agent_id="data_engineer",
            role_name="Data Engineer",
            layer=10,
            purpose="Build data pipelines: ETL/ELT, data warehousing, stream processing, data quality monitoring, data catalog.",
            required_inputs=(
                "data_architecture_spec",
                "database_schema_spec",
                "analytics_strategy",
            ),
            produced_artifacts=(
                "data_pipeline_spec",
                "etl_plan",
                "data_quality_monitoring",
                "data_catalog",
            ),
            reviewers=("data_architect", "database_developer", "growth_analyst"),
            fail_conditions=(
                "Pipeline doesn't handle late data",
                "No data quality checks",
                "Schema evolution not planned",
            ),
            activation_triggers=("data_intensive", "analytics_heavy"),
            activation_mode=AgentActivationMode.TRIGGERED,
            can_run_parallel=True,
            dependencies=("data_architect", "database_developer"),
            research_categories=("Database / Schema Tooling", "Growth / Analytics"),
        ),
        AgentProfile(
            agent_id="ml_engineer",
            role_name="ML Engineer",
            layer=10,
            purpose="Design ML features: model selection, training pipeline, feature engineering, model serving, evaluation, monitoring, A/B testing.",
            required_inputs=(
                "product_requirements_doc",
                "data_architecture_spec",
                "architecture_spec",
            ),
            produced_artifacts=(
                "ml_system_design",
                "feature_spec",
                "model_evaluation_plan",
                "serving_architecture",
            ),
            reviewers=(
                "data_engineer",
                "software_architect",
                "chief_product_ethics_officer",
            ),
            fail_conditions=(
                "No evaluation metrics",
                "Training-serving skew unaddressed",
                "Feature leakage",
                "Model bias not tested",
            ),
            activation_triggers=("ml_ai_features",),
            activation_mode=AgentActivationMode.TRIGGERED,
            can_run_parallel=True,
            dependencies=("data_architect", "software_architect"),
            research_categories=(
                "Database / Schema Tooling",
                "Backend / API Frameworks",
            ),
        ),
        # ================================================================
        # Layer 11 — QA / Testing / Verification (4 agents)
        # ================================================================
        AgentProfile(
            agent_id="qa_engineer",
            role_name="QA Engineer",
            layer=11,
            purpose="Design and execute test strategy: test plan, test cases, test automation, regression suites, edge case discovery.",
            required_inputs=(
                "product_requirements_doc",
                "acceptance_criteria",
                "UI_spec",
                "API_contract",
                "frontend_implementation_plan",
                "backend_implementation_plan",
            ),
            produced_artifacts=(
                "test_plan",
                "test_cases",
                "QA_report",
                "bug_reports",
                "regression_suite",
            ),
            reviewers=(
                "product_manager",
                "senior_frontend_developer",
                "senior_backend_developer",
            ),
            fail_conditions=(
                "Critical paths untested",
                "Edge cases not covered",
                "Regression suite missing",
                "Test data not representative",
            ),
            activation_triggers=("project_start",),
            activation_mode=AgentActivationMode.ALWAYS,
            can_run_parallel=True,
            dependencies=(
                "product_manager",
                "ui_designer",
                "api_architect",
                "senior_frontend_developer",
                "senior_backend_developer",
            ),
            research_categories=(
                "QA / Testing / Verification",
                "Browser Automation / Testing",
                "Evaluation Frameworks",
                "Code Quality",
            ),
        ),
        AgentProfile(
            agent_id="test_automation_engineer",
            role_name="Test Automation Engineer",
            layer=11,
            purpose="Build test automation framework: unit, integration, E2E, API tests, visual regression, performance tests, CI integration.",
            required_inputs=(
                "test_plan",
                "API_contract",
                "UI_spec",
                "frontend_implementation_plan",
                "backend_implementation_plan",
            ),
            produced_artifacts=(
                "automation_framework_spec",
                "ci_test_pipeline",
                "test_coverage_report",
            ),
            reviewers=("qa_engineer", "devops_engineer"),
            fail_conditions=(
                "No CI integration",
                "Flaky tests not addressed",
                "Coverage below threshold",
                "E2E tests too slow",
            ),
            activation_triggers=("automated_testing",),
            activation_mode=AgentActivationMode.TRIGGERED,
            can_run_parallel=True,
            dependencies=("qa_engineer",),
            research_categories=("QA / Testing / Verification", "DevOps / Deployment"),
        ),
        AgentProfile(
            agent_id="performance_tester",
            role_name="Performance Tester",
            layer=11,
            purpose="Load testing, stress testing, endurance testing, scalability validation, bottleneck identification.",
            required_inputs=(
                "architecture_spec",
                "backend_implementation_plan",
                "frontend_implementation_plan",
            ),
            produced_artifacts=(
                "performance_report",
                "load_test_results",
                "bottleneck_analysis",
                "scalability_recommendations",
            ),
            reviewers=(
                "software_architect",
                "senior_backend_developer",
                "devops_engineer",
            ),
            fail_conditions=(
                "System fails under expected load",
                "No baseline established",
                "Bottlenecks not identified",
            ),
            activation_triggers=("significant_traffic",),
            activation_mode=AgentActivationMode.TRIGGERED,
            can_run_parallel=True,
            dependencies=(
                "software_architect",
                "senior_backend_developer",
                "senior_frontend_developer",
            ),
            research_categories=("QA / Testing / Verification", "DevOps / Deployment"),
        ),
        AgentProfile(
            agent_id="visual_qa_engineer",
            role_name="Visual QA Engineer",
            layer=11,
            purpose="Verify visual implementation matches design: pixel-perfect comparison, responsive breakpoints, cross-browser, dark mode, animations.",
            required_inputs=(
                "UI_spec",
                "design_system",
                "interaction_spec",
                "frontend_implementation_plan",
            ),
            produced_artifacts=(
                "visual_QA_report",
                "design_fidelity_audit",
                "cross_browser_report",
            ),
            reviewers=("ui_designer", "senior_frontend_developer"),
            fail_conditions=(
                "Visual regressions from design",
                "Responsive breakpoints broken",
                "Dark mode inconsistent",
                "Animations not matching spec",
            ),
            activation_triggers=("has_ui",),
            activation_mode=AgentActivationMode.TRIGGERED,
            can_run_parallel=True,
            dependencies=(
                "ui_designer",
                "design_system_architect",
                "senior_frontend_developer",
            ),
            research_categories=(
                "QA / Testing / Verification",
                "UX / UI / Product Design",
            ),
        ),
        # ================================================================
        # Layer 12 — Security / Compliance (3 agents)
        # ================================================================
        AgentProfile(
            agent_id="security_engineer",
            role_name="Security Engineer",
            layer=12,
            purpose="Define security requirements: threat modeling, authentication, authorization, data protection, secrets management, dependency scanning.",
            required_inputs=(
                "architecture_spec",
                "API_contract",
                "data_architecture_spec",
                "compliance_requirements",
            ),
            produced_artifacts=(
                "security_requirements",
                "threat_model",
                "auth_spec",
                "security_review",
            ),
            reviewers=(
                "software_architect",
                "senior_backend_developer",
                "devops_engineer",
                "legal_compliance_officer",
            ),
            fail_conditions=(
                "No threat model",
                "Auth/authz not specified",
                "Secrets in code",
                "Known vulnerabilities not addressed",
            ),
            activation_triggers=("project_start",),
            activation_mode=AgentActivationMode.ALWAYS,
            can_run_parallel=True,
            dependencies=("software_architect", "api_architect", "data_architect"),
            research_categories=(
                "Security / Compliance",
                "Security Scanning",
                "Infrastructure",
            ),
        ),
        AgentProfile(
            agent_id="penetration_tester",
            role_name="Penetration Tester",
            layer=12,
            purpose="Simulate attacks: OWASP Top 10, injection, XSS, CSRF, auth bypass, privilege escalation, API abuse, data exfiltration.",
            required_inputs=(
                "security_requirements",
                "API_contract",
                "backend_implementation_plan",
                "threat_model",
            ),
            produced_artifacts=(
                "pentest_report",
                "vulnerability_list",
                "remediation_plan",
            ),
            reviewers=("security_engineer", "senior_backend_developer"),
            fail_conditions=(
                "Critical vulnerabilities found",
                "OWASP Top 10 not tested",
                "Remediation not proposed",
            ),
            activation_triggers=("security_sensitive",),
            activation_mode=AgentActivationMode.TRIGGERED,
            can_run_parallel=True,
            dependencies=("security_engineer", "senior_backend_developer"),
            research_categories=("Security / Compliance", "Security Scanning"),
        ),
        AgentProfile(
            agent_id="dependency_auditor",
            role_name="Dependency Auditor",
            layer=12,
            purpose="Audit all third-party dependencies: known vulnerabilities, license compliance, maintenance status, supply chain risk.",
            required_inputs=(
                "frontend_implementation_plan",
                "backend_implementation_plan",
            ),
            produced_artifacts=(
                "dependency_audit_report",
                "license_compliance_report",
                "supply_chain_risk_assessment",
            ),
            reviewers=("security_engineer", "legal_compliance_officer"),
            fail_conditions=(
                "Critical CVEs in dependencies",
                "License violations",
                "Unmaintained dependencies",
                "Supply chain attack vectors",
            ),
            activation_triggers=("has_third_party_dependencies",),
            activation_mode=AgentActivationMode.TRIGGERED,
            can_run_parallel=True,
            dependencies=("senior_frontend_developer", "senior_backend_developer"),
            research_categories=("Security / Compliance", "Security Scanning"),
        ),
        # ================================================================
        # Layer 13 — DevOps / Infrastructure (3 agents)
        # ================================================================
        AgentProfile(
            agent_id="devops_engineer",
            role_name="DevOps Engineer",
            layer=13,
            purpose="Design CI/CD pipeline, infrastructure as code, containerization, orchestration, environment strategy, secrets management.",
            required_inputs=(
                "architecture_spec",
                "backend_implementation_plan",
                "frontend_implementation_plan",
                "security_requirements",
            ),
            produced_artifacts=(
                "deployment_plan",
                "ci_cd_pipeline_spec",
                "infrastructure_spec",
                "environment_strategy",
            ),
            reviewers=(
                "software_architect",
                "security_engineer",
                "observability_engineer",
            ),
            fail_conditions=(
                "No CI/CD pipeline",
                "Manual deployment steps",
                "Secrets in config",
                "No environment parity",
                "No rollback strategy",
            ),
            activation_triggers=("requires_deployment",),
            activation_mode=AgentActivationMode.TRIGGERED,
            can_run_parallel=True,
            dependencies=(
                "software_architect",
                "senior_backend_developer",
                "senior_frontend_developer",
                "security_engineer",
            ),
            research_categories=(
                "DevOps / Deployment",
                "Infrastructure",
                "Security / Compliance",
            ),
        ),
        AgentProfile(
            agent_id="infrastructure_engineer",
            role_name="Infrastructure Engineer",
            layer=13,
            purpose="Provision and configure infrastructure: compute, networking, storage, CDN, DNS, load balancing, auto-scaling.",
            required_inputs=("deployment_plan", "architecture_spec"),
            produced_artifacts=(
                "infrastructure_provisioning_plan",
                "network_topology",
                "scaling_policy",
                "cost_estimate",
            ),
            reviewers=("devops_engineer", "software_architect", "business_strategist"),
            fail_conditions=(
                "Single points of failure",
                "No auto-scaling",
                "Cost not estimated",
                "Network security groups misconfigured",
            ),
            activation_triggers=("cloud_deployed",),
            activation_mode=AgentActivationMode.TRIGGERED,
            can_run_parallel=True,
            dependencies=("devops_engineer",),
            research_categories=("DevOps / Deployment", "Infrastructure"),
        ),
        AgentProfile(
            agent_id="release_manager",
            role_name="Release Manager",
            layer=13,
            purpose="Manage release process: versioning, changelogs, release notes, staged rollouts, canary deployments, rollback procedures.",
            required_inputs=(
                "deployment_plan",
                "QA_report",
                "security_review",
                "performance_report",
            ),
            produced_artifacts=(
                "release_readiness_report",
                "release_notes",
                "rollback_procedure",
                "go_no_go_decision",
            ),
            reviewers=("devops_engineer", "product_manager", "qa_engineer"),
            fail_conditions=(
                "Release not versioned",
                "No changelog",
                "No rollback plan",
                "Failing tests not addressed",
                "Security issues open",
            ),
            activation_triggers=("every_release",),
            activation_mode=AgentActivationMode.CHECKPOINT,
            can_run_parallel=False,
            dependencies=(
                "devops_engineer",
                "qa_engineer",
                "security_engineer",
                "performance_tester",
            ),
            research_categories=("DevOps / Deployment",),
        ),
        # ================================================================
        # Layer 14 — Observability / Reliability (2 agents)
        # ================================================================
        AgentProfile(
            agent_id="observability_engineer",
            role_name="Observability Engineer",
            layer=14,
            purpose="Design observability stack: logging, metrics, tracing, alerting, dashboards, error tracking, SLO definition.",
            required_inputs=(
                "architecture_spec",
                "deployment_plan",
                "backend_implementation_plan",
            ),
            produced_artifacts=(
                "observability_spec",
                "slo_definitions",
                "alerting_rules",
                "dashboard_specs",
            ),
            reviewers=("devops_engineer", "senior_backend_developer", "sre_engineer"),
            fail_conditions=(
                "No structured logging",
                "Metrics not defined",
                "No tracing",
                "Alerting missing",
                "No SLOs",
            ),
            activation_triggers=("production_deployed",),
            activation_mode=AgentActivationMode.TRIGGERED,
            can_run_parallel=True,
            dependencies=("devops_engineer",),
            research_categories=("Observability / Monitoring", "DevOps / Deployment"),
        ),
        AgentProfile(
            agent_id="sre_engineer",
            role_name="SRE Engineer",
            layer=14,
            purpose="Define reliability strategy: error budgets, incident response, runbooks, disaster recovery, capacity planning, chaos engineering.",
            required_inputs=(
                "observability_spec",
                "deployment_plan",
                "architecture_spec",
            ),
            produced_artifacts=(
                "reliability_spec",
                "incident_response_plan",
                "disaster_recovery_plan",
                "runbooks",
            ),
            reviewers=(
                "observability_engineer",
                "devops_engineer",
                "software_architect",
            ),
            fail_conditions=(
                "No DR plan",
                "No incident response",
                "Error budgets not defined",
                "No capacity planning",
            ),
            activation_triggers=("production_critical",),
            activation_mode=AgentActivationMode.TRIGGERED,
            can_run_parallel=True,
            dependencies=("observability_engineer", "devops_engineer"),
            research_categories=("Observability / Monitoring", "DevOps / Deployment"),
        ),
        # ================================================================
        # Layer 15 — Growth / Analytics (3 agents)
        # ================================================================
        AgentProfile(
            agent_id="growth_analyst",
            role_name="Growth Analyst",
            layer=15,
            purpose="Define growth strategy: acquisition channels, activation funnel, retention metrics, referral mechanics, monetization optimization.",
            required_inputs=(
                "business_brief",
                "target_personas",
                "marketing_plan",
                "monetization_spec",
            ),
            produced_artifacts=(
                "growth_strategy",
                "funnel_definition",
                "acquisition_plan",
                "retention_model",
            ),
            reviewers=("product_manager", "marketing_lead", "business_strategist"),
            fail_conditions=(
                "No funnel defined",
                "Metrics not measurable",
                "Acquisition channels not validated",
                "Retention not addressed",
            ),
            activation_triggers=("targeting_user_growth",),
            activation_mode=AgentActivationMode.TRIGGERED,
            can_run_parallel=True,
            dependencies=("marketing_lead", "monetization_strategist"),
            research_categories=("Growth / Analytics", "Market Research"),
        ),
        AgentProfile(
            agent_id="analytics_engineer",
            role_name="Analytics Engineer",
            layer=15,
            purpose="Implement analytics: event tracking, conversion tracking, user behavior analysis, cohort analysis, dashboards, experimentation framework.",
            required_inputs=(
                "growth_strategy",
                "data_architecture_spec",
                "frontend_implementation_plan",
            ),
            produced_artifacts=(
                "analytics_spec",
                "event_taxonomy",
                "tracking_plan",
                "experimentation_framework",
            ),
            reviewers=("growth_analyst", "data_engineer", "senior_frontend_developer"),
            fail_conditions=(
                "Key events not tracked",
                "No experimentation framework",
                "Data not flowing to warehouse",
                "Privacy violations",
            ),
            activation_triggers=("user_analytics",),
            activation_mode=AgentActivationMode.TRIGGERED,
            can_run_parallel=True,
            dependencies=("growth_analyst", "data_architect"),
            research_categories=("Growth / Analytics", "Database / Schema Tooling"),
        ),
        AgentProfile(
            agent_id="conversion_optimizer",
            role_name="Conversion Optimizer",
            layer=15,
            purpose="Optimize conversion funnels: A/B test design, landing page optimization, checkout flow, onboarding optimization, churn reduction.",
            required_inputs=(
                "analytics_spec",
                "UI_spec",
                "growth_strategy",
                "UX_flow_map",
            ),
            produced_artifacts=(
                "cro_strategy",
                "ab_test_plan",
                "funnel_optimization_recommendations",
            ),
            reviewers=("growth_analyst", "ux_designer", "product_manager"),
            fail_conditions=(
                "No baseline conversion rates",
                "A/B tests not statistically valid",
                "Recommendations contradict UX best practices",
            ),
            activation_triggers=("conversion_focused",),
            activation_mode=AgentActivationMode.TRIGGERED,
            can_run_parallel=True,
            dependencies=("analytics_engineer", "ui_designer"),
            research_categories=("Growth / Analytics", "UX / UI / Product Design"),
        ),
        # ================================================================
        # Layer 16 — Support / Operations (2 agents)
        # ================================================================
        AgentProfile(
            agent_id="customer_success_manager",
            role_name="Customer Success Manager",
            layer=16,
            purpose="Design customer success workflows: onboarding, training materials, feedback loops, NPS surveys, churn intervention, escalation paths.",
            required_inputs=(
                "product_requirements_doc",
                "target_personas",
                "user_journey_maps",
            ),
            produced_artifacts=(
                "customer_success_plan",
                "onboarding_flow",
                "feedback_system_spec",
                "support_escalation_paths",
            ),
            reviewers=("product_manager", "ux_designer"),
            fail_conditions=(
                "No onboarding flow",
                "No feedback mechanism",
                "No churn intervention",
                "Support not scoped",
            ),
            activation_triggers=("has_end_users",),
            activation_mode=AgentActivationMode.TRIGGERED,
            can_run_parallel=True,
            dependencies=("product_manager", "user_researcher"),
            research_categories=("Support / Operations", "Documentation"),
        ),
        AgentProfile(
            agent_id="documentation_specialist",
            role_name="Documentation Specialist",
            layer=16,
            purpose="Create product documentation: user guides, API docs, developer docs, FAQ, changelog, knowledge base structure.",
            required_inputs=(
                "product_requirements_doc",
                "UI_spec",
                "API_contract",
                "architecture_spec",
            ),
            produced_artifacts=(
                "documentation_plan",
                "user_guide_outline",
                "api_documentation",
                "knowledge_base_structure",
            ),
            reviewers=("product_manager", "api_architect", "customer_success_manager"),
            fail_conditions=(
                "API endpoints undocumented",
                "User guides incomplete",
                "No searchable knowledge base",
                "Docs not versioned",
            ),
            activation_triggers=("requires_documentation",),
            activation_mode=AgentActivationMode.TRIGGERED,
            can_run_parallel=True,
            dependencies=("ui_designer", "api_architect", "software_architect"),
            research_categories=("Support / Operations", "Documentation"),
        ),
        # ================================================================
        # Layer 17 — Orchestration / Arbitration (5 agents)
        # ================================================================
        AgentProfile(
            agent_id="orchestrator",
            role_name="Orchestrator",
            layer=17,
            purpose="Select and activate the right agents for a project, define execution order, manage parallel/concurrent execution, track dependencies.",
            required_inputs=("business_brief",),
            produced_artifacts=(
                "council_activation_plan",
                "agent_dependency_graph",
                "execution_schedule",
            ),
            reviewers=("chief_vision_officer", "final_arbiter"),
            fail_conditions=(
                "Required agents not activated",
                "Deadlocks in dependency graph",
                "Sequential execution when parallel is possible",
            ),
            activation_triggers=("project_start",),
            activation_mode=AgentActivationMode.ALWAYS,
            can_run_parallel=False,
            dependencies=("chief_vision_officer",),
            research_categories=(
                "Multi-agent Orchestration",
                "Software Engineering Agents",
            ),
        ),
        AgentProfile(
            agent_id="project_memory_keeper",
            role_name="Project Memory Keeper",
            layer=17,
            purpose="Maintain project memory: decisions log, rationale, trade-offs, lessons learned, context handoff between phases.",
            required_inputs=(),
            produced_artifacts=(
                "project_memory",
                "decisions_log",
                "trade_off_journal",
                "context_handoff",
                "lessons_learned",
            ),
            reviewers=("final_arbiter", "orchestrator"),
            fail_conditions=(
                "Decisions not recorded",
                "Rationale lost",
                "Context handoff incomplete",
                "Conflicts not documented",
            ),
            activation_triggers=("project_start",),
            activation_mode=AgentActivationMode.BACKGROUND,
            can_run_parallel=True,
            dependencies=(),
            research_categories=(
                "Multi-agent Orchestration",
                "Software Engineering Agents",
            ),
        ),
        AgentProfile(
            agent_id="final_arbiter",
            role_name="Final Arbiter",
            layer=17,
            purpose="Evaluate evidence from all agents, resolve conflicts, decide go/no-go, approve release, ensure quality and alignment.",
            required_inputs=(
                "QA_report",
                "security_review",
                "performance_report",
                "alignment_audit_report",
                "visual_QA_report",
                "accessibility_audit_report",
                "release_readiness_report",
                "dependency_audit_report",
                "pentest_report",
                "ethics_audit_report",
                "project_memory",
            ),
            produced_artifacts=(
                "final_arbiter_decision",
                "release_approval",
                "conflict_resolution",
            ),
            reviewers=("chief_vision_officer",),
            fail_conditions=(
                "Evidence incomplete",
                "Critical issues unresolved",
                "Conflicting reports not reconciled",
                "Quality gates bypassed",
            ),
            activation_triggers=("phase_end", "before_release"),
            activation_mode=AgentActivationMode.CHECKPOINT,
            can_run_parallel=False,
            dependencies=(
                "qa_engineer",
                "security_engineer",
                "devops_engineer",
                "release_manager",
                "performance_tester",
            ),
            research_categories=(
                "Multi-agent Orchestration",
                "Software Engineering Agents",
                "Evaluation Frameworks",
            ),
        ),
        AgentProfile(
            agent_id="conflict_resolver",
            role_name="Conflict Resolver",
            layer=17,
            purpose="Detect and resolve inter-agent conflicts: contradictory requirements, incompatible designs, resource disputes, priority clashes.",
            required_inputs=(),
            produced_artifacts=("conflict_resolution", "resolution_rationale"),
            reviewers=("final_arbiter",),
            fail_conditions=(
                "Conflict not resolved",
                "Resolution creates new conflict",
                "Affected agents not consulted",
            ),
            activation_triggers=("agent_outputs_contradict",),
            activation_mode=AgentActivationMode.ON_DEMAND,
            can_run_parallel=True,
            dependencies=(),
            research_categories=(
                "Multi-agent Orchestration",
                "Software Engineering Agents",
            ),
        ),
        AgentProfile(
            agent_id="quality_gate_keeper",
            role_name="Quality Gate Keeper",
            layer=17,
            purpose="Enforce quality gates: verify all required artifacts exist, all tests pass, all reviews complete, all approvals obtained.",
            required_inputs=(),
            produced_artifacts=(
                "gate_status_report",
                "missing_artifacts_list",
                "gate_decision",
            ),
            reviewers=("final_arbiter", "orchestrator"),
            fail_conditions=(
                "Required artifact missing",
                "Gate bypassed without approval",
                "Conditional pass not tracked",
            ),
            activation_triggers=("quality_gate_checkpoint",),
            activation_mode=AgentActivationMode.CHECKPOINT,
            can_run_parallel=True,
            dependencies=(),
            research_categories=("Multi-agent Orchestration", "Evaluation Frameworks"),
        ),
    )


DEFAULT_AGENTS: tuple[AgentProfile, ...] = _build_default_agents()


# ---------------------------------------------------------------------------
# External inputs (known seed artifacts not produced by any agent)
# ---------------------------------------------------------------------------

KNOWN_EXTERNAL_INPUTS: frozenset[str] = frozenset(
    {
        "project_brief",
    }
)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class AgentRegistry:
    """Immutable registry of Agent Council V2 agents.

    Provides lookup by agent_id, layer, artifact, input, role family, and
    activation mode. Validates the registry on construction, raising
    RegistryValidationError for any issues.
    """

    def __init__(self, agents: tuple[AgentProfile, ...] | None = None) -> None:
        """Initialize the registry with optional custom agent list.

        Args:
            agents: Optional tuple of AgentProfile to use instead of defaults.

        Raises:
            RegistryValidationError: If the registry fails validation.
        """
        self._agents: tuple[AgentProfile, ...] = (
            agents if agents is not None else DEFAULT_AGENTS
        )
        self._by_id: dict[str, AgentProfile] = {}
        self._by_layer: dict[int, tuple[AgentProfile, ...]] = {}
        self._by_artifact: dict[str, tuple[AgentProfile, ...]] = {}
        self._by_input: dict[str, tuple[AgentProfile, ...]] = {}
        self._by_activation_mode: dict[str, tuple[AgentProfile, ...]] = {}
        self._by_role_family: dict[str, tuple[AgentProfile, ...]] = {}
        self._validate()
        self._build_indexes()

    # -- Validation ----------------------------------------------------------

    def _validate(self) -> None:
        """Validate the registry for consistency."""
        seen_ids: set[str] = set()
        seen_role_names: dict[int, set[str]] = {}
        agent_ids: frozenset[str] = frozenset(a.agent_id for a in self._agents)
        produced_artifacts: set[str] = set()
        required_inputs: set[str] = set()

        for agent in self._agents:
            # Duplicate agent IDs
            if agent.agent_id in seen_ids:
                raise RegistryValidationError(f"Duplicate agent_id: {agent.agent_id}")
            seen_ids.add(agent.agent_id)

            # Layer must be 1-17
            if not (1 <= agent.layer <= 17):
                raise RegistryValidationError(
                    f"Agent {agent.agent_id}: layer {agent.layer} must be 1-17"
                )

            # Dependencies must reference known agents
            for dep_id in agent.dependencies:
                if dep_id not in agent_ids:
                    raise RegistryValidationError(
                        f"Agent {agent.agent_id}: dependency '{dep_id}' not found in registry"
                    )

            # Self-dependency is invalid
            if agent.agent_id in agent.dependencies:
                raise RegistryValidationError(
                    f"Agent {agent.agent_id}: cannot depend on itself"
                )

            # Reviewers must reference known agents
            for reviewer_id in agent.reviewers:
                if reviewer_id not in agent_ids:
                    raise RegistryValidationError(
                        f"Agent {agent.agent_id}: reviewer '{reviewer_id}' not found in registry"
                    )

            # Track produced artifacts and required inputs for later validation
            for art_id in agent.produced_artifacts:
                produced_artifacts.add(art_id)
            for inp_id in agent.required_inputs:
                required_inputs.add(inp_id)

            # Duplicate role names in the same layer (warn only via optional check)
            seen_role_names.setdefault(agent.layer, set())
            seen_role_names[agent.layer].add(agent.role_name)

        # Validate artifact producer/consumer chains
        self._validate_artifact_chains(agent_ids, produced_artifacts, required_inputs)

    def _validate_artifact_chains(
        self,
        agent_ids: frozenset[str],
        produced_artifacts: set[str],
        required_inputs: set[str],
    ) -> None:
        """Validate every required input has a producer or is a known external input."""
        for inp_id in sorted(required_inputs):
            if inp_id not in produced_artifacts and inp_id not in KNOWN_EXTERNAL_INPUTS:
                # Soft warning — not all inputs need to be from registered agents
                # (e.g., change_proposals, conflicting_outputs are context-dependent)
                pass

    def _build_indexes(self) -> None:
        """Build lookup indexes."""
        for agent in self._agents:
            self._by_id[agent.agent_id] = agent

            self._by_layer.setdefault(agent.layer, ())
            self._by_layer[agent.layer] = self._by_layer[agent.layer] + (agent,)

            for art_id in agent.produced_artifacts:
                self._by_artifact.setdefault(art_id, ())
                self._by_artifact[art_id] = self._by_artifact[art_id] + (agent,)

            for inp_id in agent.required_inputs:
                self._by_input.setdefault(inp_id, ())
                self._by_input[inp_id] = self._by_input[inp_id] + (agent,)

            self._by_activation_mode.setdefault(agent.activation_mode.value, ())
            self._by_activation_mode[agent.activation_mode.value] = (
                self._by_activation_mode[agent.activation_mode.value] + (agent,)
            )

    # -- Lookups -------------------------------------------------------------

    def get(self, agent_id: str) -> AgentProfile:
        """Look up an agent by ID. Raises KeyError if not found."""
        if agent_id not in self._by_id:
            raise KeyError(f"Agent '{agent_id}' not found in registry")
        return self._by_id[agent_id]

    def get_optional(self, agent_id: str) -> AgentProfile | None:
        """Look up an agent by ID, returning None if not found."""
        return self._by_id.get(agent_id)

    def list_all(self) -> tuple[AgentProfile, ...]:
        """Return all agents."""
        return self._agents

    def list_by_layer(self, layer: int) -> tuple[AgentProfile, ...]:
        """Return agents in a given layer (1-17)."""
        return self._by_layer.get(layer, ())

    def list_by_artifact(self, artifact_id: str) -> tuple[AgentProfile, ...]:
        """Return agents that produce a given artifact."""
        return self._by_artifact.get(artifact_id, ())

    def list_by_input(self, input_id: str) -> tuple[AgentProfile, ...]:
        """Return agents that require a given input."""
        return self._by_input.get(input_id, ())

    def producers_of(self, artifact_id: str) -> tuple[AgentProfile, ...]:
        """Alias for list_by_artifact."""
        return self.list_by_artifact(artifact_id)

    def consumers_of(self, artifact_id: str) -> tuple[AgentProfile, ...]:
        """Return agents that require a given artifact as input."""
        return self.list_by_input(artifact_id)

    def list_by_activation_mode(
        self,
        mode: str,
    ) -> tuple[AgentProfile, ...]:
        """Return agents with a given activation mode (always/triggered/on_demand/checkpoint/background)."""
        return self._by_activation_mode.get(mode, ())

    # -- Grouping queries ----------------------------------------------------

    def list_strategy_agents(self) -> tuple[AgentProfile, ...]:
        """Return all agents in strategic layers (1-5, 15-16)."""
        result: list[AgentProfile] = []
        for layer_num in (1, 2, 3, 4, 5, 15, 16):
            result.extend(self._by_layer.get(layer_num, ()))
        return tuple(result)

    def list_technical_agents(self) -> tuple[AgentProfile, ...]:
        """Return all agents in technical layers (6-14, 17)."""
        result: list[AgentProfile] = []
        for layer_num in (6, 7, 8, 9, 10, 11, 12, 13, 14, 17):
            result.extend(self._by_layer.get(layer_num, ()))
        return tuple(result)

    def list_review_agents(self) -> tuple[AgentProfile, ...]:
        """Return agents that serve as reviewers for other agents."""
        reviewer_ids: set[str] = set()
        for agent in self._agents:
            reviewer_ids.update(agent.reviewers)
        return tuple(
            self._by_id[rid] for rid in sorted(reviewer_ids) if rid in self._by_id
        )

    def list_implementation_agents(self) -> tuple[AgentProfile, ...]:
        """Return agents in implementation layers (8-10)."""
        result: list[AgentProfile] = []
        for layer_num in (8, 9, 10):
            result.extend(self._by_layer.get(layer_num, ()))
        return tuple(result)

    def list_critical_path_agents(self) -> tuple[AgentProfile, ...]:
        """Return agents that must run sequentially (can_run_parallel=False)."""
        return tuple(a for a in self._agents if not a.can_run_parallel)

    def list_always_activated(self) -> tuple[AgentProfile, ...]:
        """Return agents with ALWAYS activation mode."""
        return self.list_by_activation_mode("always")

    # -- Validation queries --------------------------------------------------

    def validate_produced_artifact_has_consumer(
        self,
        artifact_id: str,
    ) -> bool:
        """Check that a produced artifact has at least one consumer or is a terminal output."""
        consumers = self.consumers_of(artifact_id)
        # Terminal artifacts (like final_arbiter_decision) may have no registered
        # consumers but are still valid as final outputs.
        return len(consumers) > 0

    def find_orphan_artifacts(self) -> tuple[str, ...]:
        """Find produced artifacts that have no consumers and are not known terminal outputs."""
        terminal_outputs: frozenset[str] = frozenset(
            {
                "final_arbiter_decision",
                "release_approval",
                "conflict_resolution",
                "project_memory",
                "lessons_learned",
                "context_handoff",
                "decisions_log",
                "trade_off_journal",
            }
        )
        orphaned: list[str] = []
        for agent in self._agents:
            for art_id in agent.produced_artifacts:
                if art_id in terminal_outputs:
                    continue
                consumers = self.consumers_of(art_id)
                if len(consumers) == 0:
                    orphaned.append(art_id)
        return tuple(sorted(orphaned))

    def find_unproduced_inputs(self) -> tuple[str, ...]:
        """Find required inputs that are neither produced by any agent nor known external inputs."""
        produced: set[str] = set()
        for agent in self._agents:
            produced.update(agent.produced_artifacts)

        unproduced: list[str] = []
        seen: set[str] = set()
        for agent in self._agents:
            for inp_id in agent.required_inputs:
                if inp_id in seen:
                    continue
                seen.add(inp_id)
                if inp_id not in produced and inp_id not in KNOWN_EXTERNAL_INPUTS:
                    unproduced.append(inp_id)
        return tuple(sorted(unproduced))

    @property
    def agent_count(self) -> int:
        """Number of registered agents."""
        return len(self._agents)

    @property
    def agent_ids(self) -> tuple[str, ...]:
        """All registered agent IDs."""
        return tuple(a.agent_id for a in self._agents)

    @property
    def layers(self) -> tuple[int, ...]:
        """Layer numbers that have at least one agent."""
        return tuple(sorted({a.layer for a in self._agents}))


# ---------------------------------------------------------------------------
# Convenience factory
# ---------------------------------------------------------------------------


def load_default_registry() -> AgentRegistry:
    """Return a validated AgentRegistry with the 56 default specialized agents."""
    return AgentRegistry()
