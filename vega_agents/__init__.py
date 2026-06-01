"""Vega Agent Runtime — token-aware agent selection and cost-controlled task routing."""

from .registry import AgentRole, get_default_agent_registry, find_agent_role, list_enabled_agents
from .selector import (
    TaskProfile,
    AgentSelectionDecision,
    should_escalate_to_fanout,
    select_agents_for_task,
    propose_new_agent_if_needed,
)
from .executor import (
    AgentExecutionStep,
    AgentExecutionPlan,
    build_execution_plan,
    summarize_execution_plan,
    should_execute_fanout,
)
from .blueprints import (
    AgentBlueprint,
    get_agent_blueprint_catalog,
    get_blueprint_count,
    list_blueprints,
    get_categories,
    find_blueprint,
    search_blueprints,
    propose_blueprints_for_task,
)

__all__ = [
    "AgentRole",
    "TaskProfile",
    "AgentSelectionDecision",
    "AgentExecutionStep",
    "AgentExecutionPlan",
    "AgentBlueprint",
    "get_default_agent_registry",
    "find_agent_role",
    "list_enabled_agents",
    "should_escalate_to_fanout",
    "select_agents_for_task",
    "propose_new_agent_if_needed",
    "build_execution_plan",
    "summarize_execution_plan",
    "should_execute_fanout",
    "get_agent_blueprint_catalog",
    "get_blueprint_count",
    "list_blueprints",
    "get_categories",
    "find_blueprint",
    "search_blueprints",
    "propose_blueprints_for_task",
]
