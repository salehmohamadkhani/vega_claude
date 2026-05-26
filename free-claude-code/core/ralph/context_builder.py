"""Build structured project context snapshots for future agents.

Gathers git state, file context, and task summaries into a deterministic
snapshot. All git commands are read-only with timeout enforcement.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .models import RalphTask
from .verification import VerificationResult
from .workspace import RalphWorkspace


@dataclass
class GitContext:
    """Read-only git state snapshot."""

    branch: str = ""
    commit: str = ""
    status_summary: str = ""
    recent_commits: list[str] = field(default_factory=list)
    diff_summary: str = ""


@dataclass
class FileContext:
    """Files relevant to the current task context."""

    included_files: list[str] = field(default_factory=list)
    excluded_files: list[str] = field(default_factory=list)
    notes: str = ""


@dataclass
class RalphContextSnapshot:
    """A complete context snapshot for agent consumption."""

    goal_id: str = ""
    run_id: str = ""
    task_id: str = ""
    git: GitContext = field(default_factory=GitContext)
    files: FileContext = field(default_factory=FileContext)
    task_summary: str = ""
    verification_summary: str = ""
    created_at: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )


_GIT_TIMEOUT_SECONDS = 10


class ContextBuilder:
    """Build structured context snapshots using read-only git commands.

    All git calls use ``shell=False`` with strict timeouts. Non-git
    directories are handled gracefully.
    """

    def __init__(
        self,
        workspace: RalphWorkspace | None = None,
        repo_root: str | Path | None = None,
    ) -> None:
        self._workspace = workspace or RalphWorkspace()
        self._repo_root = Path(repo_root).resolve() if repo_root else Path.cwd()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build_snapshot(
        self,
        goal_id: str,
        run_id: str,
        task_id: str,
        task: RalphTask | None = None,
        verification_result: VerificationResult | None = None,
    ) -> RalphContextSnapshot:
        """Build a context snapshot with git state and task summaries."""
        git = self._collect_git_context()
        files = FileContext()
        if task:
            files.included_files = list(task.allowed_files)
            files.excluded_files = list(task.forbidden_files)

        task_summary = task.title if task else ""
        task_summary += f"\n{task.description}" if task and task.description else ""

        verification_summary = ""
        if verification_result:
            vs = verification_result.status.value
            cmd_count = len(verification_result.command_results)
            verification_summary = f"Status: {vs} | Commands: {cmd_count}"

        return RalphContextSnapshot(
            goal_id=goal_id,
            run_id=run_id,
            task_id=task_id,
            git=git,
            files=files,
            task_summary=task_summary,
            verification_summary=verification_summary,
        )

    def save_snapshot(self, snapshot: RalphContextSnapshot) -> Path:
        """Persist a context snapshot as JSON under ``.fcc-ralph/context/``."""
        data: dict[str, Any] = {
            "goal_id": snapshot.goal_id,
            "run_id": snapshot.run_id,
            "task_id": snapshot.task_id,
            "git": {
                "branch": snapshot.git.branch,
                "commit": snapshot.git.commit,
                "status_summary": snapshot.git.status_summary,
                "recent_commits": snapshot.git.recent_commits,
                "diff_summary": snapshot.git.diff_summary,
            },
            "files": {
                "included_files": snapshot.files.included_files,
                "excluded_files": snapshot.files.excluded_files,
                "notes": snapshot.files.notes,
            },
            "task_summary": snapshot.task_summary,
            "verification_summary": snapshot.verification_summary,
            "created_at": snapshot.created_at,
        }
        relative = f"context/{snapshot.run_id}_{snapshot.task_id}_{snapshot.goal_id[:8]}.json"
        return self._workspace.write_json(relative, data)

    # ------------------------------------------------------------------
    # Git context collection
    # ------------------------------------------------------------------

    def _collect_git_context(self) -> GitContext:
        """Collect read-only git state from the repo root."""
        return GitContext(
            branch=self._safe_git_cmd(["git", "branch", "--show-current"]),
            commit=self._safe_git_cmd(["git", "rev-parse", "--short", "HEAD"]),
            status_summary=self._safe_git_cmd(["git", "status", "--short"]),
            recent_commits=self._safe_git_log(),
            diff_summary=self._safe_git_cmd(["git", "diff", "--stat"]),
        )

    def _safe_git_cmd(self, argv: list[str]) -> str:
        """Run a read-only git command with timeout. Returns output or ''."""
        try:
            proc = subprocess.run(
                argv,
                capture_output=True,
                text=True,
                shell=False,
                cwd=str(self._repo_root),
                timeout=_GIT_TIMEOUT_SECONDS,
            )
            if proc.returncode == 0:
                return proc.stdout.strip()
            return ""
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            return ""

    def _safe_git_log(self) -> list[str]:
        """Run ``git log --oneline -5`` and return lines or []. """
        try:
            proc = subprocess.run(
                ["git", "log", "--oneline", "-5"],
                capture_output=True,
                text=True,
                shell=False,
                cwd=str(self._repo_root),
                timeout=_GIT_TIMEOUT_SECONDS,
            )
            if proc.returncode == 0:
                return [line.strip() for line in proc.stdout.split("\n") if line.strip()]
            return []
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            return []
