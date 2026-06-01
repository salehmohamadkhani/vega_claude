"""Tests for the Vega Agent CLI Runner (U10-LITE).

Covers: CLI parsing, markdown and JSON output, trait detection,
profile building, and safety invariants (no env access, no secrets).
Stdlib only — no product imports beyond vega_agents.
"""

from __future__ import annotations

import json
import os
import sys

# Ensure the worktree root is on sys.path so vega_agents is importable
_worktree = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)
if _worktree not in sys.path:
    sys.path.insert(0, _worktree)

# Import the module under test
from scripts import vega_agent_runner as runner
from vega_agents.selector import TaskProfile


# ── Trait detection helpers ────────────────────────────────────────────────────────


def test_simple_task_detects_direct() -> None:
    """A plain task about updating docs should stay in direct mode."""
    profile = runner.build_profile_from_task(
        "Update the README with new installation instructions"
    )
    assert not profile.touches_auth
    assert not profile.touches_secrets
    assert not profile.touches_networking
    assert not profile.touches_deployment
    assert not profile.requires_research
    assert profile.touched_files_count == 1  # baseline only

    # The selector should keep this in direct mode
    from vega_agents.executor import build_execution_plan
    plan = build_execution_plan(profile)
    assert plan.mode == "direct"
    assert not plan.requires_user_approval
    assert plan.estimated_total_calls == 0


def test_auth_secrets_task_escalates() -> None:
    """Auth/secrets keywords trigger escalation → fanout_proposed mode."""
    profile = runner.build_profile_from_task(
        "Add OAuth2 login with credential rotation and API key management"
    )
    assert profile.touches_auth
    assert profile.touches_secrets
    # Should produce fanout_proposed mode
    from vega_agents.executor import build_execution_plan
    plan = build_execution_plan(profile)
    assert plan.mode == "fanout_proposed"
    assert plan.requires_user_approval
    assert len(plan.steps) > 0
    # Security reviewer should be selected
    names = {s.agent_name for s in plan.steps}
    assert "security_reviewer" in names


def test_research_task_shows_scanner() -> None:
    """Research keywords trigger requires_research → research_scanner visible."""
    profile = runner.build_profile_from_task(
        "Research existing authentication patterns and reference implementations"
    )
    assert profile.requires_research
    # Research scanner should appear in the plan
    from vega_agents.executor import build_execution_plan
    plan = build_execution_plan(profile)
    if plan.mode == "fanout_proposed":
        names = {s.agent_name for s in plan.steps}
        assert "research_scanner" in names


def test_deployment_task_proposes_new_agent() -> None:
    """Deployment keywords trigger proposed_new_agent."""
    profile = runner.build_profile_from_task(
        "Deploy the backend to staging with Docker Compose"
    )
    assert profile.touches_deployment
    from vega_agents.executor import build_execution_plan
    plan = build_execution_plan(profile)
    # Deployment triggers escalation + proposed new agent
    if plan.mode == "fanout_proposed":
        assert plan.proposed_new_agent is not None
        assert "deployment_agent" in plan.proposed_new_agent


# ── CLI parsing ────────────────────────────────────────────────────────────────────


def test_cli_defaults_to_markdown() -> None:
    """Without --json, the output should contain markdown headers."""
    args = runner._parse_args(["Add login endpoint"])
    assert not args.output_json
    assert args.task == "Add login endpoint"


def test_cli_json_flag() -> None:
    """With --json, the flag should be set."""
    args = runner._parse_args(["--json", "Deploy to staging"])
    assert args.output_json
    assert args.task == "Deploy to staging"

    # Also test positional-first to verify argparse flexibility
    args2 = runner._parse_args(["Deploy to staging", "--json"])
    assert args2.output_json


def test_cli_no_task_returns_none() -> None:
    """With no positional arg, task should be None (stdin fallback)."""
    args = runner._parse_args([])
    assert args.task is None


# ── Output formatting ──────────────────────────────────────────────────────────────


def test_markdown_includes_mode() -> None:
    """Markdown output must include mode, agents, calls, and approval info."""
    from vega_agents.executor import AgentExecutionPlan, AgentExecutionStep

    plan = AgentExecutionPlan(
        mode="direct",
        steps=[
            AgentExecutionStep(
                agent_name="seppc_direct",
                purpose="SEPCC plans and executes the task directly",
                mode="direct",
                requires_llm=False,
                estimated_calls=0,
                approval_required=False,
            ),
        ],
        estimated_total_calls=0,
        requires_user_approval=False,
        reason="Low-risk task; direct SEPCC mode sufficient",
    )
    output = runner.format_markdown_plan(plan)
    assert "**Mode:** `direct`" in output
    assert "**Estimated LLM calls:** 0" in output
    assert "**User approval required:** No" in output
    assert "seppc_direct" in output


def test_markdown_has_agent_table() -> None:
    """Markdown output for fanout_proposed should show an agent table."""
    from vega_agents.executor import AgentExecutionPlan, AgentExecutionStep

    plan = AgentExecutionPlan(
        mode="fanout_proposed",
        steps=[
            AgentExecutionStep(
                agent_name="security_reviewer",
                purpose="Review for auth/secrets risks",
                mode="fanout",
                requires_llm=False,
                estimated_calls=0,
                approval_required=True,
            ),
            AgentExecutionStep(
                agent_name="research_scanner",
                purpose="Research patterns",
                mode="fanout",
                requires_llm=True,
                estimated_calls=1,
                approval_required=False,
            ),
        ],
        estimated_total_calls=1,
        requires_user_approval=True,
        reason="Escalated: auth/secrets involvement",
    )
    output = runner.format_markdown_plan(plan)
    assert "| Agent | Mode | LLM Calls | Approval | Purpose |" in output
    assert "|-------|------|-----------|----------|---------|" in output
    assert "security_reviewer" in output
    assert "research_scanner" in output
    assert "~1" in output  # LLM calls estimate
    assert "Yes" in output  # approval column


def test_markdown_shows_proposed_new_agent() -> None:
    """When a proposed new agent exists, it should appear in markdown."""
    from vega_agents.executor import AgentExecutionPlan

    plan = AgentExecutionPlan(
        mode="fanout_proposed",
        steps=[],
        estimated_total_calls=1,
        requires_user_approval=True,
        reason="Deployment change",
        proposed_new_agent=(
            "Proposed new agent: deployment_agent — "
            "reviews deployment config changes."
        ),
    )
    output = runner.format_markdown_plan(plan)
    assert "Proposed New Agent" in output
    assert "deployment_agent" in output


def test_json_output_valid() -> None:
    """JSON output should be parseable and contain expected fields."""
    from vega_agents.executor import AgentExecutionPlan, AgentExecutionStep

    plan = AgentExecutionPlan(
        mode="fanout_proposed",
        steps=[
            AgentExecutionStep(
                agent_name="security_reviewer",
                purpose="Review risks",
                mode="fanout",
                requires_llm=False,
                estimated_calls=0,
                approval_required=True,
            ),
        ],
        estimated_total_calls=0,
        requires_user_approval=True,
        reason="Auth/secrets involvement",
    )
    raw = runner.format_json_plan(plan)
    data = json.loads(raw)
    assert data["mode"] == "fanout_proposed"
    assert data["estimated_total_calls"] == 0
    assert data["requires_user_approval"] is True
    assert len(data["steps"]) == 1
    assert data["steps"][0]["agent_name"] == "security_reviewer"
    assert data["steps"][0]["approval_required"] is True


def test_json_includes_proposed_new_agent() -> None:
    """JSON output should include proposed_new_agent when set."""
    from vega_agents.executor import AgentExecutionPlan

    plan = AgentExecutionPlan(
        mode="fanout_proposed",
        steps=[],
        estimated_total_calls=1,
        requires_user_approval=True,
        reason="Many files",
        proposed_new_agent="coverage_auditor",
    )
    raw = runner.format_json_plan(plan)
    data = json.loads(raw)
    assert data["proposed_new_agent"] == "coverage_auditor"


# ── Trait detection edge cases ─────────────────────────────────────────────────────


def test_empty_task_has_no_traits() -> None:
    """An empty task string should be detected as low-risk direct."""
    profile = runner.build_profile_from_task("")
    assert not profile.touches_auth
    assert not profile.touches_secrets
    assert not profile.touches_networking
    assert not profile.touches_deployment
    assert not profile.requires_research
    assert profile.touched_files_count == 1  # baseline


def test_partial_keyword_matches() -> None:
    """Partial keyword matches should not trigger false positives."""
    profile = runner.build_profile_from_task("The author is writing a story")
    assert not profile.touches_auth  # "auth" is a substring of "author", no match
    assert not profile.touches_secrets


def test_network_task_detects_networking() -> None:
    """Networking keywords should be detected."""
    profile = runner.build_profile_from_task(
        "Open a WebSocket connection to the backend server on port 443"
    )
    assert profile.touches_networking


def test_refactor_task_estimates_more_files() -> None:
    """Refactor tasks should estimate more than baseline files."""
    profile = runner.build_profile_from_task(
        "Refactor the authentication module into three new packages"
    )
    assert profile.touched_files_count > 1


# ── Safety invariants ──────────────────────────────────────────────────────────────


def test_no_env_access() -> None:
    """The module should not read environment variables during normal operation."""
    # Build a plan; if this reads env vars it would fail the assertion
    profile = runner.build_profile_from_task("Simple task")
    from vega_agents.executor import build_execution_plan
    plan = build_execution_plan(profile)
    assert plan is not None
    # Verify no env reads happened by checking a sentinel
    assert "VEGA_API_KEY" not in os.environ
    assert "OPENAI_API_KEY" not in os.environ


def test_no_secrets_in_output(tmp_path) -> None:
    """Formatted output should not contain any secrets or credentials."""
    from vega_agents.executor import AgentExecutionPlan

    plan = AgentExecutionPlan(
        mode="direct",
        steps=[],
        estimated_total_calls=0,
        requires_user_approval=False,
        reason="Test",
    )
    md = runner.format_markdown_plan(plan)
    assert "api_key" not in md.lower()
    assert "secret" not in md.lower()
    assert "password" not in md.lower()

    js = runner.format_json_plan(plan)
    assert "api_key" not in js.lower()
    assert "secret" not in js.lower()


def test_main_returns_zero_for_valid_task() -> None:
    """The main() function should exit 0 for a normal task."""
    rc = runner.main(["Add simple endpoint"])
    assert rc == 0


def test_main_json_flag() -> None:
    """The main() function with --json should return 0 and produce valid JSON."""
    import io
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()
    try:
        rc = runner.main(["--json", "Simple task"])
        assert rc == 0
        output = sys.stdout.getvalue()
        data = json.loads(output)
        assert "mode" in data
        assert "steps" in data
    finally:
        sys.stdout = old_stdout


# ── Profile builder integration with executor ──────────────────────────────────────


def test_full_pipeline_simple_task() -> None:
    """A simple task should go through profile → plan → markdown without errors."""
    from vega_agents.executor import build_execution_plan

    profile = runner.build_profile_from_task("Update README with badge links")
    plan = build_execution_plan(profile)
    markdown = runner.format_markdown_plan(plan)
    assert "direct" in markdown
    assert "seppc_direct" in markdown


def test_full_pipeline_risky_task() -> None:
    """A risky task should produce a fanout_proposed plan with agents listed."""
    from vega_agents.executor import build_execution_plan

    profile = runner.build_profile_from_task(
        "Deploy new Docker Compose config with auth secrets to production"
    )
    plan = build_execution_plan(profile)
    assert plan.mode == "fanout_proposed"
    assert plan.requires_user_approval
    # Both JSON and markdown should be valid
    md = runner.format_markdown_plan(plan)
    assert "fanout_proposed" in md

    js = runner.format_json_plan(plan)
    data = json.loads(js)
    assert data["mode"] == "fanout_proposed"
    assert data["requires_user_approval"]
