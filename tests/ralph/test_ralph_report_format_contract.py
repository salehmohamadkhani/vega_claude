"""Ralph report format contract test.

Verifies that Ralph/SEPCC report documents use required markers and basic
structure.  Stdlib only — no product imports, no network, no env reads.
"""

from __future__ import annotations

import pathlib
import re

# ── constants ──────────────────────────────────────────────────────────

WORKTREE = pathlib.Path(
    "/opt/vega-cloud/vega_claude/worktrees/vega-ralph-1"
)
RALPH_DOCS = WORKTREE / "docs" / "ralph"

# Reports that must end with a DONE line
R2_R12_REPORTS = tuple(
    f"RALPH_R{n}_" for n in (2, 3, 4, 5, 6, 7, 8, 9, 12)
)

# Phase reports — do NOT require DONE (they are historical)
PHASE_REPORTS = ("PHASE_9_9_", "PHASE_9_10_")

SUSPICIOUS_PATTERNS = [
    (r"(?:TELEGRAM_BOT_TOKEN|BOT_TOKEN)\s*[=:]\s*\S+", "TOKEN variable"),
    (r"(?:DEEPSEEK_API_KEY|API_KEY|api_key)\s*[=:]\s*\S+", "API key variable"),
    (r"\d{9,10}:AA[A-Za-z0-9_-]{30,}", "Telegram token pattern"),
    (r"(?:-----BEGIN\s+PRIVATE\s+KEY-----)", "Private key PEM"),
    (r"(?:ghp_|gho_|ghu_)[A-Za-z0-9_]{36,}", "GitHub token pattern"),
]


# ── helpers ────────────────────────────────────────────────────────────

def _is_r2_r12_report(name: str) -> bool:
    """Return True if the filename matches a RALPH_R<n>_ report."""
    return any(name.startswith(p) for p in R2_R12_REPORTS)


def _is_phase_report(name: str) -> bool:
    return any(name.startswith(p) for p in PHASE_REPORTS)


# ── tests ──────────────────────────────────────────────────────────────

def test_ralph_docs_directory_exists() -> None:
    assert RALPH_DOCS.is_dir(), f"Directory not found: {RALPH_DOCS}"


def test_ralph_docs_are_readable() -> None:
    md_files = sorted(RALPH_DOCS.glob("*.md"))
    assert len(md_files) > 0, "No Markdown files in docs/ralph/"
    for f in md_files:
        assert f.is_file(), f"Not a file: {f}"
        content = f.read_text()
        assert len(content) > 50, f"File too short: {f.name} ({len(content)} chars)"


# Reports that must end with a final DONE line (completion reports)
_DONE_REPORTS = {
    "RALPH_R2_CONTROLLED_ARTIFACT_REPORT.md",
    "RALPH_R3_RISKS_AND_GUARDRAILS.md",
    "RALPH_R4_TELEGRAM_MINIAPP_CONTROL_GUIDE.md",
    "RALPH_R6_TEST_ONLY_VERIFICATION_REPORT.md",
    "RALPH_R7_SMOKE_SUITE_REPORT.md",
    "RALPH_R8_FIRST_LIMITED_TEST_IMPLEMENTATION_REPORT.md",
    "RALPH_R9_CONTROLLED_IMPLEMENTATION_REPORT.md",
    "RALPH_R12_GUARDED_IMPLEMENTATION_RUN_REPORT.md",
}


def test_r2_r12_reports_end_with_done() -> None:
    """Selected Ralph completion reports should end with exactly DONE."""
    for name in _DONE_REPORTS:
        f = RALPH_DOCS / name
        assert f.is_file(), f"Report not found: {name}"
        content = f.read_text().strip()
        last_line = content.split("\n")[-1].strip() if content else ""
        assert last_line == "DONE", (
            f"{name}: last line is {last_line!r}, expected 'DONE'"
        )


def test_r2_r12_reports_have_title() -> None:
    """Ralph reports should start with an H1 title."""
    for f in sorted(RALPH_DOCS.glob("*.md")):
        if not _is_r2_r12_report(f.name):
            continue
        content = f.read_text()
        first_line = content.split("\n")[0].strip()
        assert first_line.startswith("# "), (
            f"{f.name}: first line {first_line!r} is not an H1 title"
        )


_MARKER_REPORTS = {
    "RALPH_R9_CONTROLLED_IMPLEMENTATION_REPORT.md": "R9_CONTROLLED_IMPLEMENTATION_READY_FOR_REVIEW",
    "RALPH_R12_GUARDED_IMPLEMENTATION_RUN_REPORT.md": "R12_GUARDED_RUN_READY_FOR_REVIEW",
    "RALPH_R8_FIRST_LIMITED_TEST_IMPLEMENTATION_REPORT.md": "R8_LIMITED_TEST_READY_FOR_REVIEW",
    "RALPH_R7_SMOKE_SUITE_REPORT.md": "R7_SMOKE_SUITE_READY_FOR_REVIEW",
    "RALPH_R6_TEST_ONLY_VERIFICATION_REPORT.md": "R6_TEST_ONLY_READY_FOR_REVIEW",
    "RALPH_R5_GO_NO_GO_DECISION.md": "GO_FOR_R6_DOCUMENTATION_OR_TEST_ONLY",
    "RALPH_R9_SELECTED_SCOPE.md": "R9_SCOPE_APPROVED_FOR_CONTROLLED_IMPLEMENTATION",
}


def test_r2_r12_reports_have_decision_marker() -> None:
    """Ralph reports with a defined marker should contain it."""
    for name, marker in _MARKER_REPORTS.items():
        f = RALPH_DOCS / name
        assert f.is_file(), f"Report not found: {name}"
        content = f.read_text()
        assert marker in content, (
            f"{name}: marker {marker!r} not found in content"
        )


def test_no_suspicious_secrets_in_docs() -> None:
    """Check docs/ralph for obvious secret-like content."""
    for f in sorted(RALPH_DOCS.glob("*.md")):
        content = f.read_text()
        for pattern, label in SUSPICIOUS_PATTERNS:
            match = re.search(pattern, content, re.IGNORECASE)
            assert not match, (
                f"{f.name}: found {label} match: {match.group()[:20]}..."
            )


def test_phase_reports_exist() -> None:
    """Historical phase reports from the main workspace should exist."""
    names = [f.name for f in RALPH_DOCS.glob("PHASE_*.md")]
    assert len(names) >= 2, (
        f"Expected at least 2 phase reports, found {len(names)}"
    )


def test_no_product_source_imports() -> None:
    """Meta-check: no product code imported in the test file."""
    import sys
    for mod in list(sys.modules.keys()):
        if "free_claude" in mod or "vega_claude" in mod:
            raise AssertionError(f"Product module imported: {mod}")


def test_all_reports_have_consistent_newlines() -> None:
    """All reports should use \\n (Unix) line endings."""
    for f in sorted(RALPH_DOCS.glob("*.md")):
        raw = f.read_bytes()
        assert b"\r\n" not in raw, f"{f.name}: contains CRLF line endings"
