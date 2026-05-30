"""Agent Council V2 — Registry.

Provides the default agent registry with 17 layer-level agents (one per layer).
Supports lookup by agent_id, layer, produced artifact, and required input.
Validates duplicate IDs, unknown dependencies, and missing reviewers.

Expandable: later phases can register the full 56-agent taxonomy.
"""

from __future__ import annotations

from .models import AgentActivationMode, AgentProfile

# ---------------------------------------------------------------------------
# Validation errors
# ---------------------------------------------------------------------------


class RegistryValidationError(ValueError):
    """Raised when the registry fails validation."""


# ---------------------------------------------------------------------------
# Default 17-agent registry
# ---------------------------------------------------------------------------


def _build_default_agents() -> tuple[AgentProfile, ...]:
    """Return the 17 layer-level agents — one representative per layer."""
    return (
        # ---- Layer 1 — Executive / Vision ----
        AgentProfile(
            agent_id="executive_vision_agent",
            role_name="Executive Vision Agent",
            layer=1,
            purpose="Define product vision, mission, core value proposition, and strategic direction.",
            required_inputs=("project_brief",),
            produced_artifacts=("business_brief", "strategic_direction"),
            reviewers=("business_strategy_agent", "product_manager_agent"),
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
        # ---- Layer 2 — Business Strategy ----
        AgentProfile(
            agent_id="business_strategy_agent",
            role_name="Business Strategy Agent",
            layer=2,
            purpose="Define business model, revenue strategy, pricing, go-to-market plan, cost structure, and risk assessment.",
            required_inputs=("business_brief", "market_research_report", "competitor_map"),
            produced_artifacts=("business_model_canvas", "pricing_strategy", "gtm_plan"),
            reviewers=("executive_vision_agent", "product_manager_agent"),
            fail_conditions=(
                "Unsustainable unit economics",
                "No clear revenue model",
                "Pricing below cost",
                "Unaddressed regulatory risk",
            ),
            activation_triggers=("commercial_product",),
            activation_mode=AgentActivationMode.TRIGGERED,
            can_run_parallel=True,
            dependencies=("market_research_agent",),
            research_categories=("Business Strategy", "Market Research"),
        ),
        # ---- Layer 3 — Market Research ----
        AgentProfile(
            agent_id="market_research_agent",
            role_name="Market Research Agent",
            layer=3,
            purpose="Research market size, trends, segments, opportunities, threats, competition, and user needs.",
            required_inputs=("business_brief",),
            produced_artifacts=(
                "market_research_report",
                "competitor_map",
                "target_personas",
                "user_journey_maps",
            ),
            reviewers=("business_strategy_agent", "product_manager_agent"),
            fail_conditions=(
                "No data sources cited",
                "Claims contradicted by available evidence",
                "TAM/SAM/SOM not estimated",
                "Personas lack specificity",
            ),
            activation_triggers=("product_targeting_market",),
            activation_mode=AgentActivationMode.TRIGGERED,
            can_run_parallel=True,
            dependencies=("executive_vision_agent",),
            research_categories=("Market Research", "Competitive Analysis"),
        ),
        # ---- Layer 4 — Product Management ----
        AgentProfile(
            agent_id="product_manager_agent",
            role_name="Product Manager Agent",
            layer=4,
            purpose="Own product requirements, roadmap, and backlog. Translate vision + research into actionable specs.",
            required_inputs=(
                "business_brief",
                "market_research_report",
                "competitor_map",
                "target_personas",
            ),
            produced_artifacts=(
                "product_requirements_doc",
                "user_stories",
                "acceptance_criteria",
                "product_roadmap",
            ),
            reviewers=(
                "executive_vision_agent",
                "business_strategy_agent",
                "ux_ui_product_design_agent",
                "software_architect_agent",
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
                "executive_vision_agent",
                "market_research_agent",
            ),
            research_categories=("Product Management", "Backend / API Frameworks"),
        ),
        # ---- Layer 5 — Brand / Content / Marketing ----
        AgentProfile(
            agent_id="brand_content_agent",
            role_name="Brand & Content Agent",
            layer=5,
            purpose="Define brand identity, content strategy, marketing plan, and SEO strategy.",
            required_inputs=("business_brief", "target_personas", "competitor_map"),
            produced_artifacts=("brand_strategy", "brand_book", "content_strategy", "marketing_plan"),
            reviewers=("executive_vision_agent", "ux_ui_product_design_agent"),
            fail_conditions=(
                "Brand indistinguishable from competitors",
                "Voice inconsistent with target personas",
                "Content not mapped to user journey",
                "No channel strategy",
            ),
            activation_triggers=("consumer_facing_product",),
            activation_mode=AgentActivationMode.TRIGGERED,
            can_run_parallel=True,
            dependencies=("market_research_agent",),
            research_categories=("Brand / Content / Marketing", "Design Systems / CSS"),
        ),
        # ---- Layer 6 — UX / UI / Product Design ----
        AgentProfile(
            agent_id="ux_ui_product_design_agent",
            role_name="UX/UI Product Design Agent",
            layer=6,
            purpose="Design user experience: flows, information architecture, visual interface, design system, interaction patterns.",
            required_inputs=(
                "target_personas",
                "user_journey_maps",
                "product_requirements_doc",
                "brand_strategy",
            ),
            produced_artifacts=(
                "UX_flow_map",
                "information_architecture",
                "wireframes",
                "design_system",
                "UI_spec",
            ),
            reviewers=("product_manager_agent", "senior_frontend_developer_agent", "qa_verification_agent"),
            fail_conditions=(
                "Flows not mapped to personas",
                "Accessibility (WCAG) not addressed",
                "Responsive breakpoints missing",
                "Component states undefined",
            ),
            activation_triggers=("has_user_interface",),
            activation_mode=AgentActivationMode.TRIGGERED,
            can_run_parallel=True,
            dependencies=("product_manager_agent",),
            research_categories=("UX / UI / Product Design", "UI Component Libraries", "Design Systems / CSS"),
        ),
        # ---- Layer 7 — Software Architecture ----
        AgentProfile(
            agent_id="software_architect_agent",
            role_name="Software Architect Agent",
            layer=7,
            purpose="Define system architecture: tech stack, service boundaries, data flow, API design principles, non-functional requirements.",
            required_inputs=("product_requirements_doc", "security_requirements"),
            produced_artifacts=(
                "architecture_spec",
                "tech_stack_decision",
                "system_boundaries",
                "data_flow_diagrams",
            ),
            reviewers=(
                "senior_backend_developer_agent",
                "senior_frontend_developer_agent",
                "security_compliance_agent",
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
            dependencies=("product_manager_agent",),
            research_categories=(
                "Software Architecture",
                "Backend / API Frameworks",
                "Infrastructure",
            ),
        ),
        # ---- Layer 8 — Frontend Engineering ----
        AgentProfile(
            agent_id="senior_frontend_developer_agent",
            role_name="Senior Frontend Developer Agent",
            layer=8,
            purpose="Plan and guide frontend implementation: component architecture, state management, routing, performance, bundle optimization.",
            required_inputs=(
                "UI_spec",
                "design_system",
                "API_contract",
                "architecture_spec",
            ),
            produced_artifacts=(
                "frontend_implementation_plan",
                "component_tree",
                "state_management_spec",
                "routing_spec",
            ),
            reviewers=("software_architect_agent", "ux_ui_product_design_agent", "qa_verification_agent"),
            fail_conditions=(
                "Plan doesn't cover all UI states",
                "Performance budget not defined",
                "Accessibility not addressed",
                "Bundle size unmanaged",
            ),
            activation_triggers=("has_frontend",),
            activation_mode=AgentActivationMode.TRIGGERED,
            can_run_parallel=True,
            dependencies=(
                "ux_ui_product_design_agent",
                "software_architect_agent",
            ),
            research_categories=(
                "Frontend Engineering",
                "UI Component Libraries",
                "Design Systems / CSS",
                "Browser Automation / Testing",
            ),
        ),
        # ---- Layer 9 — Backend Engineering ----
        AgentProfile(
            agent_id="senior_backend_developer_agent",
            role_name="Senior Backend Developer Agent",
            layer=9,
            purpose="Plan and guide backend implementation: service design, business logic, API implementation, middleware, background jobs.",
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
                "software_architect_agent",
                "database_developer_agent",
                "security_compliance_agent",
            ),
            fail_conditions=(
                "API contract not fully implemented",
                "Error handling incomplete",
                "Auth/authz not designed",
                "No retry/backoff strategy",
            ),
            activation_triggers=("has_backend",),
            activation_mode=AgentActivationMode.TRIGGERED,
            can_run_parallel=True,
            dependencies=(
                "software_architect_agent",
                "database_developer_agent",
            ),
            research_categories=(
                "Backend / API Frameworks",
                "Database / Schema Tooling",
                "DevOps / Deployment",
            ),
        ),
        # ---- Layer 10 — Database / Data Engineering ----
        AgentProfile(
            agent_id="database_developer_agent",
            role_name="Database Developer Agent",
            layer=10,
            purpose="Design and implement database schema: tables, indexes, constraints, migrations, query optimization, data integrity.",
            required_inputs=(
                "architecture_spec",
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
            reviewers=("software_architect_agent", "senior_backend_developer_agent", "security_compliance_agent"),
            fail_conditions=(
                "Schema doesn't support product requirements",
                "No migration strategy",
                "Missing indexes",
                "No data retention policy",
            ),
            activation_triggers=("has_persistent_data",),
            activation_mode=AgentActivationMode.TRIGGERED,
            can_run_parallel=True,
            dependencies=("software_architect_agent",),
            research_categories=("Database / Schema Tooling", "Backend / API Frameworks"),
        ),
        # ---- Layer 11 — QA / Testing / Verification ----
        AgentProfile(
            agent_id="qa_verification_agent",
            role_name="QA Verification Agent",
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
                "regression_suite",
            ),
            reviewers=("product_manager_agent", "senior_frontend_developer_agent", "senior_backend_developer_agent"),
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
                "ux_ui_product_design_agent",
                "software_architect_agent",
            ),
            research_categories=(
                "QA / Testing / Verification",
                "Browser Automation / Testing",
                "Evaluation Frameworks",
                "Code Quality",
            ),
        ),
        # ---- Layer 12 — Security / Compliance ----
        AgentProfile(
            agent_id="security_compliance_agent",
            role_name="Security & Compliance Agent",
            layer=12,
            purpose="Define security requirements: threat modeling, authentication, authorization, data protection, secrets management, compliance, dependency scanning.",
            required_inputs=(
                "architecture_spec",
                "API_contract",
                "database_schema_spec",
                "product_requirements_doc",
            ),
            produced_artifacts=(
                "security_requirements",
                "threat_model",
                "auth_spec",
                "security_review",
                "compliance_requirements",
            ),
            reviewers=(
                "software_architect_agent",
                "senior_backend_developer_agent",
                "devops_infrastructure_agent",
            ),
            fail_conditions=(
                "No threat model",
                "Auth/authz not specified",
                "Secrets in code",
                "Known vulnerabilities not addressed",
                "Missing regulatory analysis",
            ),
            activation_triggers=("project_start",),
            activation_mode=AgentActivationMode.ALWAYS,
            can_run_parallel=True,
            dependencies=("software_architect_agent",),
            research_categories=(
                "Security / Compliance",
                "Security Scanning",
                "Infrastructure",
            ),
        ),
        # ---- Layer 13 — DevOps / Infrastructure ----
        AgentProfile(
            agent_id="devops_infrastructure_agent",
            role_name="DevOps & Infrastructure Agent",
            layer=13,
            purpose="Design CI/CD pipeline, infrastructure as code, containerization, orchestration, environment strategy, release management.",
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
                "release_readiness_report",
            ),
            reviewers=(
                "software_architect_agent",
                "security_compliance_agent",
                "observability_reliability_agent",
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
                "senior_frontend_developer_agent",
                "senior_backend_developer_agent",
            ),
            research_categories=(
                "DevOps / Deployment",
                "Infrastructure",
                "Security / Compliance",
            ),
        ),
        # ---- Layer 14 — Observability / Reliability ----
        AgentProfile(
            agent_id="observability_reliability_agent",
            role_name="Observability & Reliability Agent",
            layer=14,
            purpose="Design observability stack: logging, metrics, tracing, alerting, SLO definition, incident response, disaster recovery.",
            required_inputs=(
                "architecture_spec",
                "deployment_plan",
                "backend_implementation_plan",
            ),
            produced_artifacts=(
                "observability_spec",
                "slo_definitions",
                "alerting_rules",
                "reliability_spec",
                "incident_response_plan",
            ),
            reviewers=(
                "devops_infrastructure_agent",
                "senior_backend_developer_agent",
            ),
            fail_conditions=(
                "No structured logging",
                "Metrics not defined",
                "No tracing",
                "Alerting missing",
                "No SLOs",
                "No DR plan",
            ),
            activation_triggers=("production_deployed",),
            activation_mode=AgentActivationMode.TRIGGERED,
            can_run_parallel=True,
            dependencies=("devops_infrastructure_agent",),
            research_categories=(
                "Observability / Monitoring",
                "DevOps / Deployment",
            ),
        ),
        # ---- Layer 15 — Growth / Analytics ----
        AgentProfile(
            agent_id="growth_analytics_agent",
            role_name="Growth & Analytics Agent",
            layer=15,
            purpose="Define growth strategy: acquisition channels, activation funnel, retention metrics, analytics implementation, experimentation.",
            required_inputs=(
                "business_brief",
                "target_personas",
                "marketing_plan",
                "UI_spec",
            ),
            produced_artifacts=(
                "growth_strategy",
                "funnel_definition",
                "analytics_spec",
                "event_taxonomy",
            ),
            reviewers=("product_manager_agent", "business_strategy_agent"),
            fail_conditions=(
                "No funnel defined",
                "Metrics not measurable",
                "Key events not tracked",
                "No experimentation framework",
            ),
            activation_triggers=("targeting_user_growth",),
            activation_mode=AgentActivationMode.TRIGGERED,
            can_run_parallel=True,
            dependencies=("brand_content_agent",),
            research_categories=("Growth / Analytics", "Market Research"),
        ),
        # ---- Layer 16 — Support / Operations ----
        AgentProfile(
            agent_id="support_operations_agent",
            role_name="Support & Operations Agent",
            layer=16,
            purpose="Design customer success workflows, documentation, onboarding, feedback loops, support escalation paths.",
            required_inputs=(
                "product_requirements_doc",
                "target_personas",
                "user_journey_maps",
            ),
            produced_artifacts=(
                "customer_success_plan",
                "onboarding_flow",
                "documentation_plan",
                "knowledge_base_structure",
            ),
            reviewers=("product_manager_agent", "ux_ui_product_design_agent"),
            fail_conditions=(
                "No onboarding flow",
                "No feedback mechanism",
                "No churn intervention",
                "Support not scoped",
            ),
            activation_triggers=("has_end_users",),
            activation_mode=AgentActivationMode.TRIGGERED,
            can_run_parallel=True,
            dependencies=("product_manager_agent",),
            research_categories=("Support / Operations", "Documentation"),
        ),
        # ---- Layer 17 — Orchestration / Arbitration ----
        AgentProfile(
            agent_id="final_arbiter_agent",
            role_name="Final Arbiter Agent",
            layer=17,
            purpose="Evaluate evidence from all agents, resolve conflicts, decide go/no-go, approve release, ensure quality and alignment.",
            required_inputs=(
                "QA_report",
                "security_review",
                "performance_report",
                "release_readiness_report",
            ),
            produced_artifacts=(
                "final_arbiter_decision",
                "release_approval",
                "conflict_resolution",
            ),
            reviewers=("executive_vision_agent",),
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
                "qa_verification_agent",
                "security_compliance_agent",
                "devops_infrastructure_agent",
            ),
            research_categories=(
                "Multi-agent Orchestration",
                "Software Engineering Agents",
                "Evaluation Frameworks",
            ),
        ),
    )


DEFAULT_AGENTS: tuple[AgentProfile, ...] = _build_default_agents()


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class AgentRegistry:
    """Immutable registry of Agent Council V2 agents.

    Provides lookup by agent_id, layer, artifact, and input. Validates the
    registry on construction, raising RegistryValidationError for any issues.
    """

    def __init__(self, agents: tuple[AgentProfile, ...] | None = None) -> None:
        """Initialize the registry with optional custom agent list.

        Args:
            agents: Optional tuple of AgentProfile to use instead of defaults.

        Raises:
            RegistryValidationError: If the registry fails validation.
        """
        self._agents: tuple[AgentProfile, ...] = agents if agents is not None else DEFAULT_AGENTS
        self._by_id: dict[str, AgentProfile] = {}
        self._by_layer: dict[int, tuple[AgentProfile, ...]] = {}
        self._by_artifact: dict[str, tuple[AgentProfile, ...]] = {}
        self._by_input: dict[str, tuple[AgentProfile, ...]] = {}
        self._validate()
        self._build_indexes()

    # -- Validation ----------------------------------------------------------

    def _validate(self) -> None:
        """Validate the registry for consistency."""
        seen_ids: set[str] = set()
        agent_ids: frozenset[str] = frozenset(a.agent_id for a in self._agents)

        for agent in self._agents:
            # Duplicate agent IDs
            if agent.agent_id in seen_ids:
                raise RegistryValidationError(
                    f"Duplicate agent_id: {agent.agent_id}"
                )
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

            # Reviewers must reference known agents (except for final arbiter
            # which may have advisory-only reviewers not in strict dependency chain)
            for reviewer_id in agent.reviewers:
                if reviewer_id not in agent_ids:
                    raise RegistryValidationError(
                        f"Agent {agent.agent_id}: reviewer '{reviewer_id}' not found in registry"
                    )

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

    # -- Lookups -------------------------------------------------------------

    def get(self, agent_id: str) -> AgentProfile:
        """Look up an agent by ID.

        Raises KeyError if not found.
        """
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
    """Return a validated AgentRegistry with the 17 default layer agents."""
    return AgentRegistry()
