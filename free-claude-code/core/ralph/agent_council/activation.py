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
# Project-type → agent activation maps
# ---------------------------------------------------------------------------

# Each project type maps to a set of agent_ids that should be activated.
# Agents not in the set are skipped for that project type.

_PROJECT_TYPE_AGENTS: dict[str, frozenset[str]] = {
    "landing_page": frozenset({
        "executive_vision_agent",
        "market_research_agent",
        "product_manager_agent",
        "brand_content_agent",
        "ux_ui_product_design_agent",
        "software_architect_agent",
        "senior_frontend_developer_agent",
        "qa_verification_agent",
        "devops_infrastructure_agent",
        "final_arbiter_agent",
    }),
    "static_site": frozenset({
        "executive_vision_agent",
        "market_research_agent",
        "product_manager_agent",
        "brand_content_agent",
        "ux_ui_product_design_agent",
        "software_architect_agent",
        "senior_frontend_developer_agent",
        "qa_verification_agent",
        "security_compliance_agent",
        "devops_infrastructure_agent",
        "final_arbiter_agent",
    }),
    "frontend_app": frozenset({
        "executive_vision_agent",
        "market_research_agent",
        "product_manager_agent",
        "brand_content_agent",
        "ux_ui_product_design_agent",
        "software_architect_agent",
        "senior_frontend_developer_agent",
        "qa_verification_agent",
        "security_compliance_agent",
        "devops_infrastructure_agent",
        "growth_analytics_agent",
        "final_arbiter_agent",
    }),
    "full_stack_app": frozenset({
        "executive_vision_agent",
        "business_strategy_agent",
        "market_research_agent",
        "product_manager_agent",
        "brand_content_agent",
        "ux_ui_product_design_agent",
        "software_architect_agent",
        "senior_frontend_developer_agent",
        "senior_backend_developer_agent",
        "database_developer_agent",
        "qa_verification_agent",
        "security_compliance_agent",
        "devops_infrastructure_agent",
        "observability_reliability_agent",
        "final_arbiter_agent",
    }),
    "saas_product": frozenset({
        "executive_vision_agent",
        "business_strategy_agent",
        "market_research_agent",
        "product_manager_agent",
        "brand_content_agent",
        "ux_ui_product_design_agent",
        "software_architect_agent",
        "senior_frontend_developer_agent",
        "senior_backend_developer_agent",
        "database_developer_agent",
        "qa_verification_agent",
        "security_compliance_agent",
        "devops_infrastructure_agent",
        "observability_reliability_agent",
        "growth_analytics_agent",
        "support_operations_agent",
        "final_arbiter_agent",
    }),
    "ai_tool": frozenset({
        "executive_vision_agent",
        "market_research_agent",
        "product_manager_agent",
        "software_architect_agent",
        "senior_frontend_developer_agent",
        "senior_backend_developer_agent",
        "database_developer_agent",
        "qa_verification_agent",
        "security_compliance_agent",
        "devops_infrastructure_agent",
        "final_arbiter_agent",
    }),
    "internal_tool": frozenset({
        "executive_vision_agent",
        "product_manager_agent",
        "software_architect_agent",
        "senior_frontend_developer_agent",
        "senior_backend_developer_agent",
        "database_developer_agent",
        "qa_verification_agent",
        "security_compliance_agent",
        "devops_infrastructure_agent",
        "final_arbiter_agent",
    }),
    "research_project": frozenset({
        "executive_vision_agent",
        "market_research_agent",
        "product_manager_agent",
        "final_arbiter_agent",
    }),
}


# Artifact dependencies for each project type
_PROJECT_TYPE_ARTIFACTS: dict[str, frozenset[str]] = {
    "landing_page": frozenset({
        "business_brief", "strategic_direction",
        "market_research_report", "competitor_map",
        "product_requirements_doc", "user_stories", "acceptance_criteria",
        "brand_strategy", "brand_book",
        "UX_flow_map", "design_system", "UI_spec",
        "architecture_spec",
        "test_plan", "QA_report",
        "deployment_plan", "release_readiness_report",
        "final_arbiter_decision",
    }),
    "static_site": frozenset({
        "business_brief", "strategic_direction",
        "market_research_report", "competitor_map",
        "product_requirements_doc", "user_stories", "acceptance_criteria",
        "brand_strategy", "brand_book",
        "UX_flow_map", "design_system", "UI_spec",
        "architecture_spec",
        "security_requirements",
        "test_plan", "QA_report",
        "deployment_plan", "release_readiness_report",
        "final_arbiter_decision",
    }),
    "frontend_app": frozenset({
        "business_brief", "strategic_direction",
        "market_research_report", "competitor_map",
        "product_requirements_doc", "user_stories", "acceptance_criteria",
        "brand_strategy", "brand_book",
        "UX_flow_map", "design_system", "UI_spec",
        "architecture_spec", "API_contract",
        "security_requirements",
        "test_plan", "QA_report",
        "deployment_plan", "release_readiness_report",
        "final_arbiter_decision",
    }),
    "full_stack_app": frozenset({
        "business_brief", "strategic_direction",
        "market_research_report", "competitor_map", "target_personas",
        "product_requirements_doc", "user_stories", "acceptance_criteria",
        "brand_strategy", "brand_book",
        "UX_flow_map", "design_system", "UI_spec",
        "architecture_spec", "API_contract", "database_schema_spec",
        "security_requirements",
        "test_plan", "QA_report",
        "deployment_plan", "release_readiness_report",
        "final_arbiter_decision",
    }),
    "saas_product": frozenset({
        "business_brief", "strategic_direction",
        "market_research_report", "competitor_map", "target_personas",
        "user_journey_maps",
        "product_requirements_doc", "user_stories", "acceptance_criteria",
        "brand_strategy", "brand_book",
        "UX_flow_map", "design_system", "UI_spec",
        "architecture_spec", "API_contract", "database_schema_spec",
        "security_requirements",
        "test_plan", "QA_report",
        "deployment_plan", "release_readiness_report",
        "final_arbiter_decision",
    }),
    "ai_tool": frozenset({
        "business_brief", "strategic_direction",
        "market_research_report", "competitor_map",
        "product_requirements_doc", "user_stories", "acceptance_criteria",
        "UX_flow_map", "design_system", "UI_spec",
        "architecture_spec", "API_contract", "database_schema_spec",
        "security_requirements",
        "test_plan", "QA_report",
        "deployment_plan", "release_readiness_report",
        "final_arbiter_decision",
    }),
    "internal_tool": frozenset({
        "business_brief", "strategic_direction",
        "product_requirements_doc", "user_stories", "acceptance_criteria",
        "UX_flow_map", "design_system", "UI_spec",
        "architecture_spec", "API_contract", "database_schema_spec",
        "security_requirements",
        "test_plan", "QA_report",
        "deployment_plan", "release_readiness_report",
        "final_arbiter_decision",
    }),
    "research_project": frozenset({
        "business_brief", "strategic_direction",
        "market_research_report", "competitor_map",
        "product_requirements_doc",
        "final_arbiter_decision",
    }),
}


# Human-readable descriptions for each project type
_PROJECT_TYPE_DESCRIPTIONS: dict[str, str] = {
    "landing_page": "Single-page marketing landing page with brand, design, and deployment",
    "static_site": "Multi-page static site (blog, portfolio, docs) with security considerations",
    "frontend_app": "Client-side SPA with API dependency but no backend implementation",
    "full_stack_app": "Full-stack web application with frontend, backend, and database",
    "saas_product": "Multi-tenant SaaS with auth, payments, analytics, and support",
    "ai_tool": "AI-powered tool with ML features, API, and UI",
    "internal_tool": "Internal dashboard or admin tool with authentication and database",
    "research_project": "Research-only project producing analysis and recommendations",
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
            parallel groups, critical path, and missing prerequisites.

        Raises:
            ValueError: If project_type is unknown.
        """
        if project_type not in _PROJECT_TYPE_AGENTS:
            known = ", ".join(sorted(_PROJECT_TYPE_AGENTS.keys()))
            raise ValueError(
                f"Unknown project type '{project_type}'. "
                f"Supported: {known}"
            )

        active_ids = _PROJECT_TYPE_AGENTS[project_type]
        required_artifacts = _PROJECT_TYPE_ARTIFACTS.get(
            project_type, frozenset()
        )

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

        def _depth(aid: str) -> int:
            if aid in depths:
                return depths[aid]
            agent = agent_map.get(aid)
            if agent is None or not agent.dependencies:
                depths[aid] = 0
                return 0
            max_dep = 0
            for dep_id in agent.dependencies:
                if dep_id in agent_ids:
                    d = _depth(dep_id)
                    if d > max_dep:
                        max_dep = d
            depths[aid] = max_dep + 1
            return depths[aid]

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
            reason=f"Required for {project_type}",
            required_artifacts_available=len(blocked) == 0,
            activation_phase=phase,
            blocked_by=tuple(blocked),
        )


# ---------------------------------------------------------------------------
# Convenience
# ---------------------------------------------------------------------------


_SUPPORTED_TYPES: tuple[str, ...] = tuple(_PROJECT_TYPE_AGENTS.keys())
