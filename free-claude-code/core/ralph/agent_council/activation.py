"""Agent Council V2 — Activation Planner.

Deterministic planner that decides which agents should activate for a given
project type. No LLM calls. No execution. Just plan generation.

Supported project types:
- landing_page
- static_site
- frontend_app
- full_stack_app
- saas_product
- ai_tool
- internal_tool
- research_project
"""

from __future__ import annotations

from .dependency_graph import topological_sort
from .models import AgentActivationDecision, AgentCouncilPlan, AgentProfile
from .registry import AgentRegistry

# ---------------------------------------------------------------------------
# Project-type -> agent activation maps
# ---------------------------------------------------------------------------


_PROJECT_TYPE_AGENTS: dict[str, frozenset[str]] = {
    "landing_page": frozenset(
        {
            # Strategy
            "chief_vision_officer",
            # Market research
            "market_researcher",
            "user_researcher",
            # Product
            "product_manager",
            # Brand
            "brand_strategist",
            # UX/UI
            "ux_designer",
            "ui_designer",
            "design_system_architect",
            # Frontend
            "senior_frontend_developer",
            # SEO + conversion
            "seo_specialist",
            "conversion_optimizer",
            # Visual QA
            "visual_qa_engineer",
            # Deployment
            "devops_engineer",
            # Final gate
            "final_arbiter",
            # Memory
            "project_memory_keeper",
            # Orchestrator
            "orchestrator",
        }
    ),
    "static_site": frozenset(
        {
            "chief_vision_officer",
            "market_researcher",
            "competitor_analyst",
            "user_researcher",
            "product_manager",
            "brand_strategist",
            "content_strategist",
            "ux_designer",
            "ui_designer",
            "design_system_architect",
            "software_architect",
            "senior_frontend_developer",
            "frontend_performance_engineer",
            "qa_engineer",
            "visual_qa_engineer",
            "security_engineer",
            "devops_engineer",
            "seo_specialist",
            "accessibility_auditor",
            "final_arbiter",
            "project_memory_keeper",
            "orchestrator",
        }
    ),
    "frontend_app": frozenset(
        {
            "chief_vision_officer",
            "market_researcher",
            "competitor_analyst",
            "user_researcher",
            "product_manager",
            "brand_strategist",
            "ux_designer",
            "ui_designer",
            "design_system_architect",
            "interaction_designer",
            "software_architect",
            "api_architect",
            "senior_frontend_developer",
            "frontend_performance_engineer",
            "qa_engineer",
            "test_automation_engineer",
            "visual_qa_engineer",
            "security_engineer",
            "devops_engineer",
            "growth_analyst",
            "analytics_engineer",
            "accessibility_auditor",
            "final_arbiter",
            "project_memory_keeper",
            "orchestrator",
        }
    ),
    "full_stack_app": frozenset(
        {
            # Layer 1-4: Strategy + Research + Product
            "chief_vision_officer",
            "chief_product_ethics_officer",
            "business_strategist",
            "market_researcher",
            "competitor_analyst",
            "user_researcher",
            "product_manager",
            "technical_product_manager",
            # Layer 5: Brand
            "brand_strategist",
            # Layer 6: UX/UI
            "ux_designer",
            "ui_designer",
            "design_system_architect",
            "interaction_designer",
            # Layer 7: Architecture
            "software_architect",
            "api_architect",
            "data_architect",
            # Layer 8-9-10: Engineering
            "senior_frontend_developer",
            "frontend_performance_engineer",
            "senior_backend_developer",
            "api_developer",
            "database_developer",
            # Layer 11: QA
            "qa_engineer",
            "test_automation_engineer",
            "performance_tester",
            "visual_qa_engineer",
            # Layer 12: Security
            "security_engineer",
            "penetration_tester",
            "dependency_auditor",
            # Layer 13-14: DevOps + Observability
            "devops_engineer",
            "infrastructure_engineer",
            "release_manager",
            "observability_engineer",
            # Layer 15: Growth
            "growth_analyst",
            "analytics_engineer",
            # Layer 6: A11y
            "accessibility_auditor",
            # Layer 17
            "orchestrator",
            "project_memory_keeper",
            "final_arbiter",
            "quality_gate_keeper",
        }
    ),
    "saas_product": frozenset(
        {
            # All strategy
            "chief_vision_officer",
            "chief_product_ethics_officer",
            "strategic_alignment_auditor",
            "business_strategist",
            "monetization_strategist",
            "legal_compliance_officer",
            "market_researcher",
            "competitor_analyst",
            "user_researcher",
            "pricing_analyst",
            "product_manager",
            "technical_product_manager",
            "scope_manager",
            # Brand + Content + Marketing
            "brand_strategist",
            "content_strategist",
            "marketing_lead",
            "seo_specialist",
            # UX/UI all
            "ux_designer",
            "ui_designer",
            "design_system_architect",
            "interaction_designer",
            "accessibility_auditor",
            # Architecture all
            "software_architect",
            "api_architect",
            "data_architect",
            # All engineering
            "senior_frontend_developer",
            "frontend_performance_engineer",
            "senior_backend_developer",
            "api_developer",
            "integration_engineer",
            "database_developer",
            "data_engineer",
            # All QA
            "qa_engineer",
            "test_automation_engineer",
            "performance_tester",
            "visual_qa_engineer",
            # All security
            "security_engineer",
            "penetration_tester",
            "dependency_auditor",
            # All DevOps
            "devops_engineer",
            "infrastructure_engineer",
            "release_manager",
            "observability_engineer",
            "sre_engineer",
            # All Growth
            "growth_analyst",
            "analytics_engineer",
            "conversion_optimizer",
            # Support
            "customer_success_manager",
            "documentation_specialist",
            # All orchestration
            "orchestrator",
            "project_memory_keeper",
            "final_arbiter",
            "conflict_resolver",
            "quality_gate_keeper",
        }
    ),
    "ai_tool": frozenset(
        {
            "chief_vision_officer",
            "chief_product_ethics_officer",
            "market_researcher",
            "user_researcher",
            "product_manager",
            "technical_product_manager",
            "ux_designer",
            "ui_designer",
            "design_system_architect",
            "software_architect",
            "api_architect",
            "data_architect",
            "senior_frontend_developer",
            "senior_backend_developer",
            "api_developer",
            "database_developer",
            "data_engineer",
            "ml_engineer",
            "qa_engineer",
            "test_automation_engineer",
            "performance_tester",
            "security_engineer",
            "dependency_auditor",
            "devops_engineer",
            "observability_engineer",
            "analytics_engineer",
            "final_arbiter",
            "project_memory_keeper",
            "orchestrator",
        }
    ),
    "internal_tool": frozenset(
        {
            "chief_vision_officer",
            "product_manager",
            "ux_designer",
            "ui_designer",
            "design_system_architect",
            "software_architect",
            "api_architect",
            "senior_frontend_developer",
            "senior_backend_developer",
            "api_developer",
            "database_developer",
            "qa_engineer",
            "test_automation_engineer",
            "security_engineer",
            "devops_engineer",
            "final_arbiter",
            "project_memory_keeper",
            "orchestrator",
        }
    ),
    "research_project": frozenset(
        {
            "chief_vision_officer",
            "market_researcher",
            "competitor_analyst",
            "product_manager",
            "chief_product_ethics_officer",
            "final_arbiter",
            "project_memory_keeper",
            "orchestrator",
        }
    ),
}

# Artifact dependencies for each project type
_PROJECT_TYPE_ARTIFACTS: dict[str, frozenset[str]] = {
    "landing_page": frozenset(
        {
            "business_brief",
            "strategic_direction",
            "market_research_report",
            "target_personas",
            "product_requirements_doc",
            "user_stories",
            "acceptance_criteria",
            "brand_strategy",
            "brand_book",
            "UX_flow_map",
            "design_system",
            "UI_spec",
            "wireframes",
            "frontend_implementation_plan",
            "visual_QA_report",
            "deployment_plan",
            "final_arbiter_decision",
        }
    ),
    "static_site": frozenset(
        {
            "business_brief",
            "strategic_direction",
            "market_research_report",
            "competitor_map",
            "target_personas",
            "product_requirements_doc",
            "user_stories",
            "acceptance_criteria",
            "brand_strategy",
            "brand_book",
            "content_strategy",
            "UX_flow_map",
            "design_system",
            "UI_spec",
            "architecture_spec",
            "frontend_implementation_plan",
            "security_requirements",
            "test_plan",
            "QA_report",
            "visual_QA_report",
            "deployment_plan",
            "seo_strategy",
            "accessibility_audit_report",
            "final_arbiter_decision",
        }
    ),
    "frontend_app": frozenset(
        {
            "business_brief",
            "strategic_direction",
            "market_research_report",
            "competitor_map",
            "target_personas",
            "product_requirements_doc",
            "user_stories",
            "acceptance_criteria",
            "brand_strategy",
            "UX_flow_map",
            "design_system",
            "UI_spec",
            "architecture_spec",
            "API_contract",
            "frontend_implementation_plan",
            "security_requirements",
            "test_plan",
            "QA_report",
            "visual_QA_report",
            "deployment_plan",
            "growth_strategy",
            "analytics_spec",
            "accessibility_audit_report",
            "final_arbiter_decision",
        }
    ),
    "full_stack_app": frozenset(
        {
            "business_brief",
            "strategic_direction",
            "market_research_report",
            "competitor_map",
            "target_personas",
            "user_journey_maps",
            "product_requirements_doc",
            "user_stories",
            "acceptance_criteria",
            "brand_strategy",
            "brand_book",
            "UX_flow_map",
            "design_system",
            "UI_spec",
            "architecture_spec",
            "API_contract",
            "data_architecture_spec",
            "database_schema_spec",
            "frontend_implementation_plan",
            "backend_implementation_plan",
            "security_requirements",
            "threat_model",
            "test_plan",
            "QA_report",
            "performance_report",
            "visual_QA_report",
            "deployment_plan",
            "release_readiness_report",
            "observability_spec",
            "growth_strategy",
            "analytics_spec",
            "accessibility_audit_report",
            "pentest_report",
            "dependency_audit_report",
            "ethics_audit_report",
            "final_arbiter_decision",
            "gate_status_report",
        }
    ),
    "saas_product": frozenset(
        {
            "business_brief",
            "strategic_direction",
            "market_research_report",
            "competitor_map",
            "target_personas",
            "user_journey_maps",
            "user_needs_analysis",
            "product_requirements_doc",
            "user_stories",
            "acceptance_criteria",
            "product_roadmap",
            "business_model_canvas",
            "pricing_strategy",
            "gtm_plan",
            "monetization_spec",
            "pricing_analysis",
            "compliance_requirements",
            "legal_risk_assessment",
            "brand_strategy",
            "brand_book",
            "content_strategy",
            "messaging_framework",
            "marketing_plan",
            "seo_strategy",
            "UX_flow_map",
            "information_architecture",
            "design_system",
            "UI_spec",
            "wireframes",
            "interaction_spec",
            "architecture_spec",
            "API_contract",
            "data_architecture_spec",
            "database_schema_spec",
            "frontend_implementation_plan",
            "backend_implementation_plan",
            "security_requirements",
            "threat_model",
            "test_plan",
            "QA_report",
            "performance_report",
            "visual_QA_report",
            "deployment_plan",
            "release_readiness_report",
            "observability_spec",
            "reliability_spec",
            "growth_strategy",
            "analytics_spec",
            "cro_strategy",
            "customer_success_plan",
            "documentation_plan",
            "accessibility_audit_report",
            "pentest_report",
            "dependency_audit_report",
            "alignment_audit_report",
            "ethics_audit_report",
            "project_memory",
            "final_arbiter_decision",
            "gate_status_report",
        }
    ),
    "ai_tool": frozenset(
        {
            "business_brief",
            "strategic_direction",
            "market_research_report",
            "target_personas",
            "product_requirements_doc",
            "user_stories",
            "acceptance_criteria",
            "UX_flow_map",
            "design_system",
            "UI_spec",
            "architecture_spec",
            "API_contract",
            "data_architecture_spec",
            "database_schema_spec",
            "frontend_implementation_plan",
            "backend_implementation_plan",
            "ml_system_design",
            "security_requirements",
            "test_plan",
            "QA_report",
            "performance_report",
            "deployment_plan",
            "observability_spec",
            "analytics_spec",
            "dependency_audit_report",
            "ethics_audit_report",
            "final_arbiter_decision",
        }
    ),
    "internal_tool": frozenset(
        {
            "business_brief",
            "strategic_direction",
            "product_requirements_doc",
            "user_stories",
            "acceptance_criteria",
            "UX_flow_map",
            "design_system",
            "UI_spec",
            "architecture_spec",
            "API_contract",
            "database_schema_spec",
            "frontend_implementation_plan",
            "backend_implementation_plan",
            "security_requirements",
            "test_plan",
            "QA_report",
            "deployment_plan",
            "final_arbiter_decision",
        }
    ),
    "research_project": frozenset(
        {
            "business_brief",
            "strategic_direction",
            "market_research_report",
            "competitor_map",
            "product_requirements_doc",
            "ethics_audit_report",
            "final_arbiter_decision",
        }
    ),
}

# Human-readable descriptions
_PROJECT_TYPE_DESCRIPTIONS: dict[str, str] = {
    "landing_page": "Single-page marketing landing page with brand, design, SEO, and deployment. No backend/database.",
    "static_site": "Multi-page static site (blog, portfolio, docs) with security, performance, and a11y.",
    "frontend_app": "Client-side SPA with API dependency, analytics, and full frontend stack.",
    "full_stack_app": "Full-stack web application with frontend, backend, database, security, QA, DevOps, and observability.",
    "saas_product": "Multi-tenant SaaS with auth, payments, analytics, growth, support, and full security/compliance.",
    "ai_tool": "AI-powered tool with ML features, API, UI, ethics review, and performance monitoring.",
    "internal_tool": "Internal dashboard or admin tool with authentication and database. No brand/market research.",
    "research_project": "Research-only project producing analysis, evidence, and recommendations.",
}

# Per-project-type rationale strings
_PROJECT_TYPE_RATIONALE: dict[str, str] = {
    "landing_page": (
        "Landing page needs brand, SEO, UX/UI, frontend, and deployment. "
        "Excludes backend/database as it is a static page."
    ),
    "static_site": (
        "Static site adds security, performance, content strategy, and accessibility "
        "to the landing page stack."
    ),
    "frontend_app": (
        "Frontend SPA needs API architecture, interaction design, analytics, "
        "and comprehensive frontend testing."
    ),
    "full_stack_app": (
        "Full-stack app activates frontend, backend, database, QA, security, "
        "DevOps, observability, and growth layers."
    ),
    "saas_product": (
        "SaaS product activates all 17 layers including monetization, legal compliance, "
        "growth, support, SRE, and full orchestration with quality gates."
    ),
    "ai_tool": (
        "AI tool activates product, architecture, frontend/backend, ML engineering, "
        "ethics review, performance testing, and security."
    ),
    "internal_tool": (
        "Internal tool skips brand, market research, and growth. "
        "Focuses on core engineering, QA, security, and deployment."
    ),
    "research_project": (
        "Research project focuses on vision, market analysis, product definition, "
        "ethics, and final arbitration. Minimal engineering."
    ),
}


# ---------------------------------------------------------------------------
# Planner
# ---------------------------------------------------------------------------


class ActivationPlanner:
    """Deterministic planner for Agent Council activation.

    Given a project type and registry, decides which agents activate,
    their execution order, parallel groups, and missing prerequisites.
    """

    def __init__(self, registry: AgentRegistry | None = None) -> None:
        self._registry = registry or AgentRegistry()

    @property
    def registry(self) -> AgentRegistry:
        return self._registry

    @property
    def supported_project_types(self) -> tuple[str, ...]:
        """Return all supported project types."""
        return tuple(_PROJECT_TYPE_AGENTS.keys())

    def plan(self, project_type: str) -> AgentCouncilPlan:
        """Create an activation plan for a project type.

        Args:
            project_type: One of the supported project types.

        Returns:
            AgentCouncilPlan with active agents, required artifacts,
            parallel groups, critical path, rationale, and missing prerequisites.

        Raises:
            ValueError: If project_type is unknown.
        """
        if project_type not in _PROJECT_TYPE_AGENTS:
            known = ", ".join(sorted(_PROJECT_TYPE_AGENTS.keys()))
            raise ValueError(
                f"Unknown project type '{project_type}'. Supported: {known}"
            )

        active_ids = _PROJECT_TYPE_AGENTS[project_type]
        required_artifacts = _PROJECT_TYPE_ARTIFACTS.get(project_type, frozenset())

        # Build a sub-registry view with only activated agents
        active_agents = tuple(
            a for a in self._registry.list_all() if a.agent_id in active_ids
        )

        # Compute parallel groups for activated agents
        parallel_groups = self._compute_parallel_groups(active_agents)

        # Critical path through activated agents
        try:
            topo = topological_sort(self._registry)
            cp = tuple(aid for aid in topo if aid in active_ids)
        except ValueError:
            cp = ()

        # Total phases = number of parallel groups
        total_phases = len(parallel_groups)

        return AgentCouncilPlan(
            project_type=project_type,
            active_agents=tuple(sorted(active_ids)),
            required_artifacts=tuple(sorted(required_artifacts)),
            parallel_groups=parallel_groups,
            critical_path=cp,
            missing_prerequisites=(),
            total_phases=total_phases,
        )

    def _compute_parallel_groups(
        self,
        activated_agents: tuple[AgentProfile, ...],
    ) -> tuple[tuple[str, ...], ...]:
        """Compute parallel execution groups for a subset of agents.

        Agents at the same depth (distance from root dependencies) can run
        in parallel, provided they don't depend on each other.
        """
        agent_ids = {a.agent_id for a in activated_agents}
        agent_map = {a.agent_id: a for a in activated_agents}

        # Compute depth for each agent
        depths: dict[str, int] = {}
        visiting: set[str] = set()

        def _depth(aid: str) -> int:
            if aid in depths:
                return depths[aid]
            if aid in visiting:
                # Cycle detected — break it by returning current max known depth
                return 0
            agent = agent_map.get(aid)
            if agent is None or not agent.dependencies:
                depths[aid] = 0
                return 0
            visiting.add(aid)
            try:
                max_dep = 0
                for dep_id in agent.dependencies:
                    if dep_id in agent_ids:
                        d = _depth(dep_id)
                        if d > max_dep:
                            max_dep = d
                depths[aid] = max_dep + 1
                return depths[aid]
            finally:
                visiting.discard(aid)

        for aid in sorted(agent_ids):
            _depth(aid)

        # Group by depth
        max_depth = max(depths.values()) if depths else 0
        groups: list[list[str]] = [[] for _ in range(max_depth + 1)]
        for aid, depth in depths.items():
            groups[depth].append(aid)

        return tuple(tuple(sorted(g)) for g in groups if g)

    def get_project_description(self, project_type: str) -> str:
        """Return a human-readable description of the project type."""
        return _PROJECT_TYPE_DESCRIPTIONS.get(
            project_type, f"Unknown project type: {project_type}"
        )

    def get_project_rationale(self, project_type: str) -> str:
        """Return the rationale for agent activation for a project type."""
        return _PROJECT_TYPE_RATIONALE.get(
            project_type, f"Standard activation for {project_type}"
        )

    def should_activate(
        self,
        agent_id: str,
        project_type: str,
    ) -> AgentActivationDecision:
        """Decide whether a single agent should activate for a project type.

        Args:
            agent_id: The agent to check.
            project_type: The project type.

        Returns:
            AgentActivationDecision with activation decision and reasoning.
        """
        if project_type not in _PROJECT_TYPE_AGENTS:
            return AgentActivationDecision(
                agent_id=agent_id,
                should_activate=False,
                reason=f"Unknown project type: {project_type}",
            )

        active_ids = _PROJECT_TYPE_AGENTS[project_type]
        agent = self._registry.get_optional(agent_id)

        if agent is None:
            return AgentActivationDecision(
                agent_id=agent_id,
                should_activate=False,
                reason="Agent not found in registry",
            )

        if agent_id not in active_ids:
            return AgentActivationDecision(
                agent_id=agent_id,
                should_activate=False,
                reason=f"Agent not required for project type '{project_type}'",
            )

        # Check which phase this agent runs in
        plan = self.plan(project_type)
        phase = -1
        for i, group in enumerate(plan.parallel_groups):
            if agent_id in group:
                phase = i
                break

        # Check blocked dependencies
        blocked = [dep_id for dep_id in agent.dependencies if dep_id not in active_ids]

        return AgentActivationDecision(
            agent_id=agent_id,
            should_activate=True,
            reason=f"Required for {project_type}: {self.get_project_rationale(project_type)}",
            required_artifacts_available=len(blocked) == 0,
            activation_phase=phase,
            blocked_by=tuple(blocked),
        )


# ---------------------------------------------------------------------------
# Convenience
# ---------------------------------------------------------------------------


_SUPPORTED_TYPES: tuple[str, ...] = tuple(_PROJECT_TYPE_AGENTS.keys())
