"""Tests for the Vega Agent Execution Interface (U8-LITE).

Covers execution plan building, summarization, and the fan-out gate.
Stdlib only — no product imports, no network, no env reads.
"""

from __future__ import annotations

import os
import sys

# Ensure the worktree root is on sys.path so vega_agents is importable
_worktree = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)
if _worktree not in sys.path:
    sys.path.insert(0, _worktree)

from vega_agents.executor import (
    AgentExecutionPlan,
    AgentExecutionStep,
    build_execution_plan,
    summarize_execution_plan,
    should_execute_fanout,
)
from vega_agents.selector import TaskProfile


# ── Dataclass contract tests ──────────────────────────────────────────────────────


def test_execution_step_has_required_fields() -> None:
    step = AgentExecutionStep(
        agent_name="codebase_auditor",
        purpose="Scan the worktree",
        mode="fanout",
        requires_llm=True,
        estimated_calls=1,
        approval_required=False,
    )
    assert step.agent_name == "codebase_auditor"
    assert step.purpose == "Scan the worktree"
    assert step.mode == "fanout"
    assert step.requires_llm is True
    assert step.estimated_calls == 1
    assert step.approval_required is False


def test_execution_plan_has_required_fields() -> None:
    plan = AgentExecutionPlan(
        mode="direct",
        steps=[],
        estimated_total_calls=0,
        requires_user_approval=False,
        reason="Test plan",
        proposed_new_agent=None,
    )
    assert plan.mode == "direct"
    assert plan.estimated_total_calls == 0
    assert plan.requires_user_approval is False
    assert plan.reason == "Test plan"
    assert plan.proposed_new_agent is None


# ── build_execution_plan — direct mode ────────────────────────────────────────────


def test_direct_plan_for_simple_task() -> None:
    profile = TaskProfile(task_text="Fix a typo in a doc file")
    plan = build_execution_plan(profile)
    assert plan.mode == "direct"
    assert plan.requires_user_approval is False
    assert plan.estimated_total_calls == 0
    assert len(plan.steps) == 1
    assert plan.steps[0].agent_name == "seppc_direct"
    assert plan.steps[0].mode == "direct"
    assert plan.steps[0].estimated_calls == 0


def test_direct_plan_estimated_calls_is_zero_or_one() -> None:
    """Direct mode must have 0 or 1 estimated calls max."""
    profile = TaskProfile(task_text="Simple refactor")
    plan = build_execution_plan(profile)
    assert plan.estimated_total_calls in (0, 1)


def test_direct_plan_no_user_approval_required() -> None:
    profile = TaskProfile(task_text="Update readme")
    plan = build_execution_plan(profile)
    assert plan.requires_user_approval is False


# ── build_execution_plan — fanout proposed mode ────────────────────────────────────


def test_fanout_plan_for_high_risk_task() -> None:
    profile = TaskProfile(
        task_text="Add auth middleware",
        touched_files_count=5,
        touches_auth=True,
        touches_secrets=True,
    )
    plan = build_execution_plan(profile)
    assert plan.mode == "fanout_proposed"
    assert plan.requires_user_approval is True
    assert len(plan.steps) <= 3
    assert plan.estimated_total_calls > 0


def test_fanout_plan_agents_have_correct_mode() -> None:
    profile = TaskProfile(
        task_text="Deploy new API endpoint",
        touches_networking=True,
        touches_deployment=True,
    )
    plan = build_execution_plan(profile)
    assert plan.mode == "fanout_proposed"
    for step in plan.steps:
        assert step.mode == "fanout"


def test_fanout_max_three_steps() -> None:
    profile = TaskProfile(
        task_text="Large multi-module refactor",
        touched_files_count=8,
        touches_auth=True,
        touches_secrets=True,
        requires_research=True,
    )
    plan = build_execution_plan(profile)
    assert len(plan.steps) <= 3


def test_fanout_estimated_calls_bounded() -> None:
    """Fanout estimated calls must be finite and based on selected agents."""
    profile = TaskProfile(
        task_text="Full system refactor with auth",
        touched_files_count=6,
        touches_auth=True,
        touches_secrets=True,
        requires_research=True,
    )
    plan = build_execution_plan(profile)
    assert plan.estimated_total_calls >= 0
    # Max theoretical: 3 agents × 4 calls each = 12
    assert plan.estimated_total_calls <= 12


# ── Agent-specific LLM flag tests ─────────────────────────────────────────────────


def test_research_scanner_requires_llm_when_research_needed() -> None:
    profile = TaskProfile(
        task_text="Implement using known patterns",
        requires_research=True,
        touched_files_count=4,
    )
    plan = build_execution_plan(profile)
    research_step = next(
        (s for s in plan.steps if s.agent_name == "research_scanner"), None
    )
    if research_step:
        assert research_step.requires_llm is True
        assert research_step.estimated_calls >= 1


def test_guardrail_reviewer_is_static_by_default() -> None:
    profile = TaskProfile(
        task_text="Failed attempt with security",
        direct_attempt_failed=True,
        touches_auth=True,
    )
    plan = build_execution_plan(profile)
    guardrail_step = next(
        (s for s in plan.steps if s.agent_name == "guardrail_reviewer"), None
    )
    if guardrail_step:
        assert guardrail_step.requires_llm is False
        assert guardrail_step.estimated_calls == 0


def test_security_reviewer_is_static_by_default() -> None:
    profile = TaskProfile(
        task_text="Implement OAuth",
        touches_auth=True,
        touches_secrets=True,
    )
    plan = build_execution_plan(profile)
    security_step = next(
        (s for s in plan.steps if s.agent_name == "security_reviewer"), None
    )
    if security_step:
        assert security_step.requires_llm is False
        assert security_step.estimated_calls == 0


# ── Proposed new agent ────────────────────────────────────────────────────────────


def test_proposed_new_agent_surfaced_not_created() -> None:
    """Proposed new agent appears in plan but is not auto-created."""
    profile = TaskProfile(
        task_text="Deploy container",
        touches_deployment=True,
        touched_files_count=3,
    )
    plan = build_execution_plan(profile)
    if plan.proposed_new_agent:
        assert "deployment_agent" in plan.proposed_new_agent


# ── summarize_execution_plan ──────────────────────────────────────────────────────


def test_summarize_direct_plan() -> None:
    profile = TaskProfile(task_text="Fix typo")
    plan = build_execution_plan(profile)
    summary = summarize_execution_plan(plan)
    assert "Execution Plan [direct]" in summary
    assert "selected" not in summary.lower() or "seppc_direct" in summary


def test_summarize_fanout_plan() -> None:
    profile = TaskProfile(
        task_text="Add auth middleware",
        touched_files_count=5,
        touches_auth=True,
    )
    plan = build_execution_plan(profile)
    summary = summarize_execution_plan(plan)
    assert "Execution Plan [fanout_proposed]" in summary
    assert "Reason:" in summary
    assert "User approval required: yes" in summary


def test_summarize_includes_estimated_calls() -> None:
    profile = TaskProfile(task_text="Fix typo")
    plan = build_execution_plan(profile)
    summary = summarize_execution_plan(plan)
    assert "Estimated LLM calls" in summary


def test_summarize_includes_proposed_new_agent() -> None:
    profile = TaskProfile(
        task_text="Deploy container",
        touches_deployment=True,
        touched_files_count=3,
    )
    plan = build_execution_plan(profile)
    summary = summarize_execution_plan(plan)
    if plan.proposed_new_agent:
        assert "Proposed new agent" in summary


# ── should_execute_fanout ─────────────────────────────────────────────────────────


def test_should_execute_fanout_true_when_approved() -> None:
    plan = AgentExecutionPlan(
        mode="fanout_proposed",
        steps=[],
        estimated_total_calls=3,
        requires_user_approval=True,
        reason="Test",
    )
    assert should_execute_fanout(plan, user_approved=True) is True


def test_should_execute_fanout_false_when_not_approved() -> None:
    plan = AgentExecutionPlan(
        mode="fanout_proposed",
        steps=[],
        estimated_total_calls=3,
        requires_user_approval=True,
        reason="Test",
    )
    assert should_execute_fanout(plan, user_approved=False) is False


def test_should_execute_fanout_false_for_direct_plan() -> None:
    plan = AgentExecutionPlan(
        mode="direct",
        steps=[],
        estimated_total_calls=0,
        requires_user_approval=False,
        reason="Test",
    )
    assert should_execute_fanout(plan, user_approved=True) is False


def test_should_execute_fanout_false_when_no_approval_required() -> None:
    """Even if approved, a plan that doesn't require approval returns False."""
    plan = AgentExecutionPlan(
        mode="fanout_proposed",
        steps=[],
        estimated_total_calls=3,
        requires_user_approval=False,
        reason="Test",
    )
    assert should_execute_fanout(plan, user_approved=True) is False


# ── Isolation tests ───────────────────────────────────────────────────────────────


def test_no_env_file_access() -> None:
    """executor.py should not reference .env files."""
    executor_code = open(
        os.path.join(os.path.dirname(__file__), "..", "..", "vega_agents", "executor.py")
    ).read()
    assert ".env" not in executor_code


def test_no_product_source_imports() -> None:
    """Meta-check: no product modules imported."""
    for mod in sys.modules:
        if "free_claude" in mod or "vega_claude" in mod:
            raise AssertionError(f"Product module imported: {mod}")


def test_executor_imports_only_stdlib_and_sibling_modules() -> None:
    """executor.py should only import stdlib and vega_agents modules."""
    executor_code = open(
        os.path.join(os.path.dirname(__file__), "..", "..", "vega_agents", "executor.py")
    ).read()
    # Should import from .registry and .selector, not from outside
    assert "from .registry import" in executor_code
    assert "from .selector import" in executor_code
    # Should not import from product modules
    assert "free_claude" not in executor_code
    assert "vega_claude" not in executor_code
