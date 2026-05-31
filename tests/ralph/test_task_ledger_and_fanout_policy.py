"""Tests for the U4-Lite task ledger and fan-out policy document.

Verifies the policy doc exists, contains required markers and rules, and
does not contain fake secrets or raw env examples.  Stdlib only.
"""

from __future__ import annotations

import pathlib

WORKTREE = pathlib.Path("/opt/vega-cloud/vega_claude/worktrees/vega-ralph-1")
POLICY_DOC = WORKTREE / "docs" / "ralph" / "U4_LITE_TASK_LEDGER_AND_FANOUT_POLICY.md"

REQUIRED_CONTENT = [
    "U4_TASK_LEDGER_POLICY_READY",
    "SEPCC Direct",
    "Fan-out",
    "escalation criteria",
    "Max 3 agents",
    "actual LLM calls",
    "commit hash",
    "GitHub verification",
    "Stop Conditions",
]

SUSPICIOUS_PATTERNS = [
    "TELEGRAM_BOT_TOKEN",
    "DEEPSEEK_API_KEY",
    "sk-",
]


def test_policy_doc_exists() -> None:
    assert POLICY_DOC.is_file(), f"Policy doc not found: {POLICY_DOC}"


def test_policy_doc_is_readable() -> None:
    content = POLICY_DOC.read_text()
    assert len(content) > 200, f"Policy doc too short ({len(content)} chars)"


def test_policy_doc_contains_required_content() -> None:
    content = POLICY_DOC.read_text()
    for item in REQUIRED_CONTENT:
        assert item in content, (
            f"Required content '{item}' not found in policy doc"
        )


def test_policy_doc_no_suspicious_secrets() -> None:
    content = POLICY_DOC.read_text()
    for pattern in SUSPICIOUS_PATTERNS:
        assert pattern not in content, (
            f"Suspicious pattern '{pattern}' found in policy doc"
        )


def test_policy_doc_marker_on_final_line() -> None:
    content = POLICY_DOC.read_text().strip()
    last_line = content.split("\n")[-1].strip()
    assert last_line == "U4_TASK_LEDGER_POLICY_READY", (
        f"Final line is {last_line!r}, expected 'U4_TASK_LEDGER_POLICY_READY'"
    )


def test_policy_doc_title_is_correct() -> None:
    content = POLICY_DOC.read_text()
    first_h1 = [l for l in content.split("\n") if l.startswith("# ")][0]
    assert "Task Ledger" in first_h1, f"H1 title {first_h1!r} missing 'Task Ledger'"


def test_policy_doc_has_fanout_criteria_table() -> None:
    content = POLICY_DOC.read_text()
    assert "| 1 |" in content, "Fan-out escalation criteria table missing"
    assert "| 8 |" in content, "Expected at least 8 escalation criteria"


def test_no_product_source_imports() -> None:
    import sys
    for mod in sys.modules:
        if "free_claude" in mod or "vega_claude" in mod:
            raise AssertionError(f"Product module imported: {mod}")
