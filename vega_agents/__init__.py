"""Vega Agent Runtime — token-aware agent selection and cost-controlled task routing."""

from .registry import AgentRole, get_default_agent_registry, find_agent_role, list_enabled_agents
from .selector import (
    TaskProfile,
    AgentSelectionDecision,
    should_escalate_to_fanout,
    select_agents_for_task,
    propose_new_agent_if_needed,
)

__all__ = [
    "AgentRole",
    "TaskProfile",
    "AgentSelectionDecision",
    "get_default_agent_registry",
    "find_agent_role",
    "list_enabled_agents",
    "should_escalate_to_fanout",
    "select_agents_for_task",
    "propose_new_agent_if_needed",
]
