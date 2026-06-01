#!/usr/bin/env python3
"""Vega Agent CLI Runner — build and display execution plans.

Usage:
  python3 scripts/vega_agent_runner.py "Add login endpoint"
  python3 scripts/vega_agent_runner.py --json "Deploy to staging"
  echo "Refactor auth module" | python3 scripts/vega_agent_runner.py

Default mode: SEPCC direct.
No LLM calls. No fan-out execution. No env/secrets access.
Stdlib only.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import textwrap

# ── Path setup ────────────────────────────────────────────────────────────────────
# Ensure vega_agents package is importable from the worktree root.
_worktree = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _worktree not in sys.path:
    sys.path.insert(0, _worktree)

# ── Imports from Vega Agent Runtime ───────────────────────────────────────────────

try:
    from vega_agents.executor import (
        AgentExecutionPlan,
        build_execution_plan,
        summarize_execution_plan,
    )
    from vega_agents.selector import TaskProfile
except ImportError:
    # Standalone fallback — shouldn't happen in the worktree but keeps
    # the script importable for syntax checking outside the project.
    print("ERROR: vega_agents package not found on sys.path", file=sys.stderr)
    sys.exit(1)


# ── Detection helpers ──────────────────────────────────────────────────────────────


def _word_in_text(word: str, text: str) -> bool:
    """Check if *word* appears as a whole word (bounded by non-alnum or edges).

    Handles single-word and multi-word (phrase) keywords. For multi-word
    phrases the boundary check only applies to the first character of the
    first word and the last character of the last word.
    """
    i = text.find(word)
    while i != -1:
        before = i == 0 or not text[i - 1].isalnum()
        after = i + len(word) >= len(text) or not text[i + len(word)].isalnum()
        if before and after:
            return True
        i = text.find(word, i + 1)
    return False


def _detect_task_traits(task_text: str) -> dict[str, bool | int]:
    """Heuristic trait detection for building a TaskProfile.

    No env reads, no file access, no network calls.
    Uses whole-word matching to avoid false positives (e.g. "author" ↛ auth).
    """
    lower = task_text.lower()
    return {
        "touches_auth": any(
            _word_in_text(kw, lower) for kw in ("auth", "login", "oauth", "token", "session")
        ),
        "touches_secrets": any(
            _word_in_text(kw, lower)
            for kw in ("secret", "credential", "password", "api_key", "key rotation")
        ),
        "touches_networking": any(
            _word_in_text(kw, lower) for kw in ("network", "port", "http", "connect", "websocket")
        ),
        "touches_deployment": any(
            _word_in_text(kw, lower)
            for kw in ("deploy", "docker", "caddy", "port 8082", "staging", "prod")
        ),
        "requires_research": any(
            _word_in_text(kw, lower)
            for kw in ("research", "pattern", "reference", "example", "investigate")
        ),
        # Rough estimate from the text — no file scanning
        "touched_files_count": _estimate_file_count(task_text),
    }


def _estimate_file_count(task_text: str) -> int:
    """Guess how many files a task might touch from its description."""
    lower = task_text.lower()
    count = 1  # baseline
    if any(_word_in_text(kw, lower) for kw in ("refactor", "migrate", "restructure", "rename")):
        count += 2
    if any(_word_in_text(kw, lower) for kw in ("module", "package", "multiple files", "many")):
        count += 2
    if any(_word_in_text(kw, lower) for kw in ("deploy", "infrastructure", "docker", "config")):
        count += 1
    # Cap at a reasonable upper bound — no file system reads
    return min(count, 8)


# ── Profile builder ───────────────────────────────────────────────────────────────


def build_profile_from_task(task_text: str) -> TaskProfile:
    """Build a TaskProfile from raw task text using heuristic detection.

    No LLM calls. No file access. No network.
    """
    traits = _detect_task_traits(task_text)
    return TaskProfile(
        task_text=task_text,
        touched_files_count=traits["touched_files_count"],  # type: ignore[arg-type]
        touches_auth=traits["touches_auth"],  # type: ignore[arg-type]
        touches_secrets=traits["touches_secrets"],  # type: ignore[arg-type]
        touches_networking=traits["touches_networking"],  # type: ignore[arg-type]
        touches_deployment=traits["touches_deployment"],  # type: ignore[arg-type]
        requires_research=traits["requires_research"],  # type: ignore[arg-type]
    )


# ── Output formatters ──────────────────────────────────────────────────────────────


def format_markdown_plan(plan: AgentExecutionPlan) -> str:
    """Format the execution plan as a markdown table."""
    lines: list[str] = []
    lines.append("# Agent Execution Plan")
    lines.append("")
    lines.append(f"**Mode:** `{plan.mode}`")
    lines.append(f"**Reason:** {plan.reason}")
    lines.append(f"**Estimated LLM calls:** {plan.estimated_total_calls}")
    lines.append(f"**User approval required:** {'Yes' if plan.requires_user_approval else 'No'}")
    lines.append("")

    if plan.steps:
        lines.append("## Selected Agents")
        lines.append("")
        lines.append("| Agent | Mode | LLM Calls | Approval | Purpose |")
        lines.append("|-------|------|-----------|----------|---------|")
        for step in plan.steps:
            llm_str = f"~{step.estimated_calls}" if step.estimated_calls > 0 else "0"
            approval_str = "Yes" if step.approval_required else "No"
            lines.append(
                f"| {step.agent_name} | {step.mode} | {llm_str} | {approval_str} | {step.purpose} |"
            )

    if plan.proposed_new_agent:
        lines.append("")
        lines.append(f"## Proposed New Agent\n")
        lines.append(f"{plan.proposed_new_agent}")

    return "\n".join(lines)


def format_json_plan(plan: AgentExecutionPlan) -> str:
    """Format the execution plan as a JSON object."""
    payload: dict[str, object] = {
        "mode": plan.mode,
        "reason": plan.reason,
        "estimated_total_calls": plan.estimated_total_calls,
        "requires_user_approval": plan.requires_user_approval,
        "steps": [
            {
                "agent_name": s.agent_name,
                "mode": s.mode,
                "estimated_calls": s.estimated_calls,
                "approval_required": s.approval_required,
                "purpose": s.purpose,
            }
            for s in plan.steps
        ],
    }
    if plan.proposed_new_agent:
        payload["proposed_new_agent"] = plan.proposed_new_agent
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


# ── CLI entrypoint ─────────────────────────────────────────────────────────────────


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="vega_agent_runner",
        description="Build and display a Vega Agent execution plan from a task description.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Examples:
              %(prog)s "Add login endpoint"
              %(prog)s --json "Deploy to staging"
              echo "Refactor auth module" | %(prog)s
        """),
    )
    parser.add_argument(
        "task",
        nargs="?",
        help="Task description. Reads from stdin if omitted.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="output_json",
        help="Output the plan as JSON instead of markdown.",
    )
    return parser.parse_args(argv)


def _read_task(args_task: str | None) -> str:
    """Read task text from argument or stdin."""
    if args_task:
        return args_task
    # Read from stdin — handles pipes and redirects
    stdin_text = sys.stdin.read().strip()
    if stdin_text:
        return stdin_text
    print("ERROR: no task provided. Pass as argument or pipe to stdin.", file=sys.stderr)
    sys.exit(1)


def main(argv: list[str] | None = None) -> int:
    """Main entrypoint. Returns exit code (0 = success, 1 = error)."""
    args = _parse_args(argv)
    task_text = _read_task(args.task)

    # Build profile and execution plan — no LLM, no fan-out, no network
    profile = build_profile_from_task(task_text)
    plan = build_execution_plan(profile)

    if args.output_json:
        print(format_json_plan(plan), end="")
    else:
        print(format_markdown_plan(plan))

    return 0


if __name__ == "__main__":
    sys.exit(main())
