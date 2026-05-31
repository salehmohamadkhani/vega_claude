"""Tests for the Vega Agent Runtime foundation.

Covers registry, selector, and escalation logic.
Stdlib only — no product imports, no network, no env reads.
"""

from __future__ import annotations

import os
import sys

# Ensure the worktree root is on sys.path so core.vega_agents is importable
_worktree = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)
if _worktree not in sys.path:
    sys.path.insert(0, _worktree)

from vega_agents import registry, selector
from vega_agents.registry import (
    AgentRole,
    find_agent_role,
    get_default_agent_registry,
    list_enabled_agents,
)
from vega_agents.selector import (
    MAX_FANOUT_AGENTS,
    AgentSelectionDecision,
    TaskProfile,
    propose_new_agent_if_needed,
    select_agents_for_task,
    should_escalate_to_fanout,
)


# ── Registry tests ────────────────────────────────────────────────────────────────

def test_default_registry_contains_expected_agents() -> None:
    registry = get_default_agent_registry()
    names = {r.name for r in registry}
    assert "codebase_auditor" in names
    assert "implementation_planner" in names
    assert "test_planner" in names
    assert "guardrail_reviewer" in names
    assert "research_scanner" in names
    assert "security_reviewer" in names
    assert len(registry) >= 6


def test_registry_roles_have_required_fields() -> None:
    for role in get_default_agent_registry():
        assert role.name, f"Missing name in role"
        assert role.purpose, f"Missing purpose in {role.name}"
        assert role.risk_level in ("low", "medium", "high"), f"Invalid risk in {role.name}"
        assert role.estimated_cost_level in ("low", "medium", "high"), f"Invalid cost in {role.name}"
        assert 1 <= role.max_parallel <= 10


def test_find_agent_role_by_name() -> None:
    role = find_agent_role("codebase_auditor")
    assert role is not None
    assert role.name == "codebase_auditor"
    assert role.default_enabled is True


def test_find_agent_role_unknown_returns_none() -> None:
    assert find_agent_role("nonexistent_agent") is None


def test_list_enabled_agents() -> None:
    enabled = list_enabled_agents()
    names = {r.name for r in enabled}
    assert "codebase_auditor" in names
    assert "implementation_planner" in names
    assert "test_planner" in names
    assert "guardrail_reviewer" in names
    assert "research_scanner" not in names  # default_enabled=False
    assert "security_reviewer" not in names  # default_enabled=False


# ── Escalation tests ──────────────────────────────────────────────────────────────

def test_default_mode_is_direct_for_simple_task() -> None:
    profile = TaskProfile(task_text="Fix a typo in a doc file")
    assert should_escalate_to_fanout(profile) is False
    decision = select_agents_for_task(profile)
    assert decision.mode == "direct"


def test_fanout_proposed_for_high_risk_task() -> None:
    profile = TaskProfile(
        task_text="Add auth middleware",
        touched_files_count=5,
        touches_auth=True,
        touches_secrets=True,
    )
    assert should_escalate_to_fanout(profile) is True
    decision = select_agents_for_task(profile)
    assert decision.mode == "fanout_proposed"


def test_fanout_requires_user_approval() -> None:
    profile = TaskProfile(
        task_text="Deploy new API endpoint",
        touches_networking=True,
        touches_deployment=True,
    )
    decision = select_agents_for_task(profile)
    assert decision.requires_user_approval is True
    assert decision.mode == "fanout_proposed"


def test_max_selected_agents_does_not_exceed_limit() -> None:
    profile = TaskProfile(
        task_text="Large multi-module refactor",
        touched_files_count=8,
        touches_auth=True,
        touches_secrets=False,
        requires_research=True,
    )
    decision = select_agents_for_task(profile)
    assert len(decision.selected_agents) <= MAX_FANOUT_AGENTS


def test_research_scanner_activates_only_when_needed() -> None:
    profile_no_research = TaskProfile(task_text="Fix formatting")
    decision_no = select_agents_for_task(profile_no_research)
    names_no = {r.name for r in decision_no.selected_agents}
    assert "research_scanner" not in names_no

    profile_with_research = TaskProfile(
        task_text="Implement using known patterns",
        requires_research=True,
        touched_files_count=4,
    )
    decision_yes = select_agents_for_task(profile_with_research)
    names_yes = {r.name for r in decision_yes.selected_agents}
    assert "research_scanner" in names_yes, f"research_scanner not in {names_yes}"


def test_security_reviewer_activates_for_auth() -> None:
    profile = TaskProfile(
        task_text="Implement OAuth",
        touches_auth=True,
        touches_secrets=True,
    )
    decision = select_agents_for_task(profile)
    names = {r.name for r in decision.selected_agents}
    assert "security_reviewer" in names


def test_security_reviewer_activates_for_networking() -> None:
    profile = TaskProfile(
        task_text="Add network service",
        touches_networking=True,
    )
    decision = select_agents_for_task(profile)
    names = {r.name for r in decision.selected_agents}
    assert "security_reviewer" in names


def test_security_reviewer_activates_for_deployment() -> None:
    profile = TaskProfile(
        task_text="Deploy container",
        touches_deployment=True,
        touched_files_count=3,
    )
    decision = select_agents_for_task(profile)
    names = {r.name for r in decision.selected_agents}
    assert "security_reviewer" in names


def test_failed_direct_activates_guardrail_reviewer() -> None:
    profile = TaskProfile(
        task_text="Failed attempt",
        direct_attempt_failed=True,
    )
    decision = select_agents_for_task(profile)
    names = {r.name for r in decision.selected_agents}
    assert "guardrail_reviewer" in names


def test_direct_task_does_not_require_approval() -> None:
    profile = TaskProfile(task_text="Update readme")
    decision = select_agents_for_task(profile)
    assert decision.requires_user_approval is False


# ── New agent proposal tests ──────────────────────────────────────────────────────

def test_new_agent_proposed_for_deployment() -> None:
    profile = TaskProfile(touches_deployment=True, touched_files_count=3)
    proposal = propose_new_agent_if_needed(profile)
    assert proposal is not None
    assert "deployment_agent" in proposal


def test_no_new_agent_for_simple_task() -> None:
    profile = TaskProfile(task_text="Fix typo")
    proposal = propose_new_agent_if_needed(profile)
    assert proposal is None


def test_new_agent_not_auto_created() -> None:
    """Proposal text should describe the new agent but not create one."""
    profile = TaskProfile(touches_deployment=True, touched_files_count=3)
    proposal = propose_new_agent_if_needed(profile)
    assert proposal is not None
    assert "Proposed new agent" in proposal
    # Verify no side-effect — agent doesn't exist in registry
    assert find_agent_role("deployment_agent") is None


# ── Cost level tests ─────────────────────────────────────────────────────────────

def test_cost_level_is_low_for_simple_task() -> None:
    profile = TaskProfile(task_text="Fix typo")
    decision = select_agents_for_task(profile)
    assert decision.estimated_cost_level == "low"


def test_cost_level_is_high_for_complex_task() -> None:
    profile = TaskProfile(
        task_text="Multi-module auth refactor",
        touched_files_count=6,
        touches_auth=True,
        touches_secrets=True,
        direct_attempt_failed=True,
        requires_research=True,
    )
    decision = select_agents_for_task(profile)
    assert decision.estimated_cost_level in ("high", "medium")


# ── Isolation tests ───────────────────────────────────────────────────────────────

def test_no_env_file_access() -> None:
    """Modules should not depend on env file environment to import."""
    # Verify modules do not read env files or require them
    registry_code = open(registry.__file__).read()
    assert ".env" not in registry_code, "registry.py should not reference .env files"
    selector_code = open(selector.__file__).read()
    assert ".env" not in selector_code, "selector.py should not reference .env files"


def test_no_product_source_imports() -> None:
    """Meta-check: no product modules imported."""
    for mod in sys.modules:
        if "free_claude" in mod or "vega_claude" in mod:
            raise AssertionError(f"Product module imported: {mod}")
