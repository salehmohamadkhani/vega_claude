"""Tests for the U3-Lite low-cost development protocol document.

Verifies the protocol doc exists, contains required markers, and does not
contain fake secrets or raw env examples.  Stdlib only.
"""

from __future__ import annotations

import pathlib

WORKTREE = pathlib.Path("/opt/vega-cloud/vega_claude/worktrees/vega-ralph-1")
PROTOCOL_DOC = WORKTREE / "docs" / "ralph" / "U3_LITE_LOW_COST_DEVELOPMENT_PROTOCOL.md"

REQUIRED_CONTENT = [
    "U3_LOW_COST_PROTOCOL_READY",
    "Max 1 DeepSeek",
    "No Ralph loop",
    "Static inspection",
    "Tests before commit",
    "push",
]

SUSPICIOUS_PATTERNS = [
    "TELEGRAM_BOT_TOKEN",
    "DEEPSEEK_API_KEY",
    "sk-",
]


def test_protocol_doc_exists() -> None:
    assert PROTOCOL_DOC.is_file(), f"Protocol doc not found: {PROTOCOL_DOC}"


def test_protocol_doc_is_readable() -> None:
    content = PROTOCOL_DOC.read_text()
    assert len(content) > 200, f"Protocol doc too short ({len(content)} chars)"


def test_protocol_doc_contains_required_markers() -> None:
    content = PROTOCOL_DOC.read_text()
    for marker in REQUIRED_CONTENT:
        assert marker in content, (
            f"Required content '{marker}' not found in protocol doc"
        )


def test_protocol_doc_no_suspicious_secrets() -> None:
    content = PROTOCOL_DOC.read_text()
    for pattern in SUSPICIOUS_PATTERNS:
        assert pattern not in content, (
            f"Suspicious pattern '{pattern}' found in protocol doc"
        )


def test_protocol_doc_marker_on_final_line() -> None:
    content = PROTOCOL_DOC.read_text().strip()
    last_line = content.split("\n")[-1].strip()
    assert last_line == "U3_LOW_COST_PROTOCOL_READY", (
        f"Final line is {last_line!r}, expected 'U3_LOW_COST_PROTOCOL_READY'"
    )


def test_protocol_doc_title_is_correct() -> None:
    content = PROTOCOL_DOC.read_text()
    first_line = content.split("\n")[0].strip()
    assert "Low-Cost Development Protocol" in first_line, (
        f"First line {first_line!r} missing expected title"
    )


def test_no_product_source_imports() -> None:
    """Meta-check: no product modules imported by this test file."""
    import sys
    for mod in sys.modules:
        if "free_claude" in mod or "vega_claude" in mod:
            raise AssertionError(f"Product module imported: {mod}")
