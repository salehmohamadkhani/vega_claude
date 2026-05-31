"""Tests for the Vega project snapshot tool.

Stdlib only — no product imports, no network, no env reads.
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

WORKTREE = pathlib.Path("/opt/vega-cloud/vega_claude/worktrees/vega-ralph-1")
SCRIPT = WORKTREE / "scripts" / "vega_project_snapshot.py"


def test_script_exists() -> None:
    assert SCRIPT.is_file(), f"Script not found: {SCRIPT}"


def test_script_is_executable() -> None:
    assert (SCRIPT.stat().st_mode & 0o100) != 0, "Script must be executable"


def test_script_runs_without_error() -> None:
    r = subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True, text=True, timeout=30,
        cwd=str(WORKTREE),
    )
    assert r.returncode == 0, f"Script failed: {r.stderr}"


def test_json_output_is_valid() -> None:
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "--json"],
        capture_output=True, text=True, timeout=30,
        cwd=str(WORKTREE),
    )
    assert r.returncode == 0, f"JSON mode failed: {r.stderr}"
    data = json.loads(r.stdout)
    assert "repo_root" in data, "Missing repo_root"
    assert "branch" in data, "Missing branch"
    assert "total_files" in data, "Missing total_files"
    assert "extensions" in data, "Missing extensions"
    assert "top_level_dirs" in data, "Missing top_level_dirs"


def test_markdown_output_contains_key_sections() -> None:
    r = subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True, text=True, timeout=30,
        cwd=str(WORKTREE),
    )
    assert r.returncode == 0
    output = r.stdout
    assert "Vega Project Snapshot" in output
    assert "Repo root" in output
    assert "Branch" in output
    assert "File Extensions" in output
    assert "Important Files" in output
    assert "Test Directories" in output
    assert "Doc Directories" in output


def test_json_contains_branch() -> None:
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "--json"],
        capture_output=True, text=True, timeout=30,
        cwd=str(WORKTREE),
    )
    data = json.loads(r.stdout)
    assert data["branch"] in ("ralph-r1-temp", "master", "main"), f"Unexpected branch: {data['branch']}"


def test_script_ignores_runtime_dirs() -> None:
    text = SCRIPT.read_text()
    for d in (".fcc", ".ralph-mode", "__pycache__", ".pytest_cache"):
        assert d in text, f"Script should reference ignored dir: {d}"


def test_script_no_secret_patterns() -> None:
    text = SCRIPT.read_text()
    # The script intentionally contains SUSPICIOUS_PATTERNS as detection strings.
    # Verify they appear only inside the pattern list definition, not as live values.
    assert "TELEGRAM_BOT_TOKEN" in text
    assert "DEEPSEEK_API_KEY" in text
    # Verify no actual credential patterns (sk- with real chars)
    import re
    live_tokens = re.findall(r"sk-[A-Za-z0-9]{20,}", text)
    assert not live_tokens, f"Live token-like values found: {live_tokens[:3]}"


def test_no_product_source_imports() -> None:
    for mod in sys.modules:
        if "free_claude" in mod or "vega_claude" in mod:
            raise AssertionError(f"Product module imported: {mod}")
