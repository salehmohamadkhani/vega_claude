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

__all__ = [
    "AgentRole",
    "TaskProfile",
    "AgentSelectionDecision",
    "AgentExecutionStep",
    "AgentExecutionPlan",
    "get_default_agent_registry",
    "find_agent_role",
    "list_enabled_agents",
    "should_escalate_to_fanout",
    "select_agents_for_task",
    "propose_new_agent_if_needed",
    "build_execution_plan",
    "summarize_execution_plan",
    "should_execute_fanout",
]
