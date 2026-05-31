"""Tests for the U5-Lite persistent task ledger document.

Verifies the ledger exists, contains all required entries and fields,
and does not contain fake secrets.  Stdlib only.
"""

from __future__ import annotations

import pathlib

WORKTREE = pathlib.Path("/opt/vega-cloud/vega_claude/worktrees/vega-ralph-1")
LEDGER_DOC = WORKTREE / "docs" / "ralph" / "U5_LITE_TASK_LEDGER.md"

REQUIRED_ENTRIES = ["U3-LITE", "U4-LITE", "U5-LITE"]

REQUIRED_FIELDS = [
    "actual LLM calls",
    "commit hash",
    "push result",
    "GitHub verification",
    "fan-out used",
    "mode",
    "date",
    "files changed",
    "tests run",
]

SUSPICIOUS_PATTERNS = [
    "TELEGRAM_BOT_TOKEN",
    "DEEPSEEK_API_KEY",
    "sk-",
]


def _ledger_text() -> str:
    return LEDGER_DOC.read_text()


def test_ledger_doc_exists() -> None:
    assert LEDGER_DOC.is_file(), f"Ledger doc not found: {LEDGER_DOC}"


def test_ledger_doc_is_readable() -> None:
    text = _ledger_text()
    assert len(text) > 300, f"Ledger doc too short ({len(text)} chars)"


def test_ledger_doc_contains_marker() -> None:
    text = _ledger_text()
    assert "U5_TASK_LEDGER_READY" in text, "Missing final marker"


def test_ledger_doc_contains_all_entries() -> None:
    text = _ledger_text()
    for entry in REQUIRED_ENTRIES:
        assert entry in text, f"Missing entry: {entry}"


def test_every_entry_has_required_fields() -> None:
    text = _ledger_text()
    # Split entries by "### Entry:"
    sections = text.split("### Entry:")
    assert len(sections) >= 4, "Expected at least 3 entry sections"
    for section in sections[1:]:  # skip header
        for field in REQUIRED_FIELDS:
            assert field in section, (
                f"Entry missing field '{field}' in section: {section[:60]}..."
            )


def test_ledger_doc_no_suspicious_secrets() -> None:
    text = _ledger_text()
    for pattern in SUSPICIOUS_PATTERNS:
        assert pattern not in text, (
            f"Suspicious pattern '{pattern}' found in ledger"
        )


def test_u3_entry_has_known_commit() -> None:
    text = _ledger_text()
    assert "52d486e" in text, "U3 commit hash missing"
    assert "U3-LITE" in text


def test_u4_entry_has_known_commit() -> None:
    text = _ledger_text()
    assert "b19d200" in text, "U4 commit hash missing"
    assert "U4-LITE" in text


def test_no_product_source_imports() -> None:
    import sys
    for mod in sys.modules:
        if "free_claude" in mod or "vega_claude" in mod:
            raise AssertionError(f"Product module imported: {mod}")
