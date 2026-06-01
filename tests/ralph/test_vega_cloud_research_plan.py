"""Tests for VEGA_CLOUD_RESEARCH_AND_DEV_PLAN.md (U9-LITE).

Verifies the plan document exists, has the required marker,
lists exactly 5 tasks, selects one next task, and contains
no secret-like values.
"""

from __future__ import annotations

import os
import re
import sys

# Ensure the worktree root is on sys.path
_worktree = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)
if _worktree not in sys.path:
    sys.path.insert(0, _worktree)

PLAN_PATH = os.path.join(
    _worktree, "docs", "vega_cloud", "VEGA_CLOUD_RESEARCH_AND_DEV_PLAN.md"
)


# ── Helpers ─────────────────────────────────────────────────────────────────────────


def _read_plan() -> str:
    if not os.path.isfile(PLAN_PATH):
        raise FileNotFoundError(f"Plan file not found: {PLAN_PATH}")
    with open(PLAN_PATH) as f:
        return f.read()


def _count_tasks(text: str) -> int:
    """Count lines like '### Task <Letter>:' which mark task headings."""
    return len(re.findall(r"^### Task [A-Z]", text, re.MULTILINE))


def _extract_task_names(text: str) -> list[str]:
    """Extract task names from '### Task <Letter>: <name>' lines."""
    return re.findall(r"^### Task [A-Z]: (.+)$", text, re.MULTILINE)


# ── Tests ────────────────────────────────────────────────────────────────────────────


def test_plan_file_exists() -> None:
    assert os.path.isfile(PLAN_PATH), f"Plan not found at {PLAN_PATH}"


def test_plan_has_marker() -> None:
    text = _read_plan()
    assert "VEGA_CLOUD_RESEARCH_DEV_READY" in text


def test_plan_contains_five_tasks() -> None:
    text = _read_plan()
    count = _count_tasks(text)
    assert count == 5, f"Expected 5 tasks, found {count}"


def test_plan_has_selected_next_task() -> None:
    text = _read_plan()
    # "Selected Next Task" section heading
    assert "Selected Next Task" in text or "## 5. Selected Next Task" in text


def test_plan_has_current_state_section() -> None:
    text = _read_plan()
    assert "Current Vega Cloud State" in text or "Current State" in text


def test_plan_has_research_repos_section() -> None:
    text = _read_plan()
    assert "Research Repos" in text or "research repos" in text


def test_plan_has_agent_system_status_section() -> None:
    text = _read_plan()
    assert "Agent System Status" in text or "What Exists" in text


def test_plan_tasks_have_unique_names() -> None:
    text = _read_plan()
    names = _extract_task_names(text)
    assert len(names) == len(set(names)), f"Duplicate task names: {names}"


def test_plan_contains_no_secret_patterns() -> None:
    """Verify no secret-like values appear in the plan."""
    text = _read_plan()
    secret_patterns = [
        r"sk-[a-zA-Z0-9]{20,}",       # OpenAI-style keys
        r"api[-_]?key['\"]?\s*[:=]\s*['\"]",  # api_key assignments
        r"ghp_[a-zA-Z0-9]{36}",        # GitHub PAT
        r"gho_[a-zA-Z0-9]{36}",        # GitHub OAuth
        r"token\s*[:=]\s*['\"][a-zA-Z0-9_-]{16,}",  # generic tokens
        r"AKIA[0-9A-Z]{16}",           # AWS access key IDs
        r"xox[baprs]-[a-zA-Z0-9-]{10,}",  # Slack tokens
    ]
    for pattern in secret_patterns:
        matches = re.findall(pattern, text)
        assert not matches, f"Found potential secret pattern: {matches[:3]}"


def test_plan_has_fanout_assessment_for_each_task() -> None:
    """Each task section should mention 'fan-out' or 'fanout'."""
    text = _read_plan()
    # Extract sections: lines between "### Task" headings
    sections = re.split(r"^### Task [A-Z]:", text, flags=re.MULTILINE)
    # First split element is prelude, remaining are task sections
    task_sections = [s for s in sections if s.strip()]
    task_sections = task_sections[-5:]  # last 5 = the actual task sections
    assert len(task_sections) == 5, f"Expected 5 task sections, got {len(task_sections)}"
    for i, section in enumerate(task_sections):
        assert "fan-out" in section.lower() or "fanout" in section.lower(), (
            f"Task {chr(65 + i)} (section {i}) missing fan-out assessment"
        )


def test_selected_task_has_implementation_sketch() -> None:
    text = _read_plan()
    assert "Implementation sketch" in text or "```python" in text or "```" in text
