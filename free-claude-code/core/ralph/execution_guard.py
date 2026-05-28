"""Real execution safety guard for Ralph Runtime.

Validates that real execution is safe before the Claude Code execution
adapter is allowed to run. Dry-run mode bypasses all guard checks.

Safe defaults:
- Blocks execution on system roots (C:, C:\\Windows, etc.)
- Blocks execution on user home root
- Blocks execution on repo root unless explicitly allowed
- Blocks execution in dirty Git workspace unless explicitly allowed
- Enforces allowed/forbidden file rules after execution
- Clear structured failure reasons for every violation
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class RealExecutionGuardError(Exception):
    """Raised when the real execution guard blocks execution."""


@dataclass
class RealExecutionGuardResult:
    """Result of a real execution guard check."""

    allowed: bool = False
    failure_reasons: list[str] = field(default_factory=list)
    workspace_path: str = ""
    is_git_repo: bool = False
    is_dirty: bool = False
    changed_files_before: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "failure_reasons": list(self.failure_reasons),
            "workspace_path": self.workspace_path,
            "is_git_repo": self.is_git_repo,
            "is_dirty": self.is_dirty,
        }


# ---------------------------------------------------------------------------
# Forbidden paths — no real execution can target these
# ---------------------------------------------------------------------------

_FORBIDDEN_WORKSPACE_ROOTS: list[Path] = [
    Path(os.environ.get("SYSTEMROOT", "C:\\Windows")).resolve(),
    Path(os.environ.get("WINDIR", "C:\\Windows")).resolve(),
    Path("C:\\").resolve(),
    Path("C:\\Windows").resolve(),
    Path("C:\\Windows\\System32").resolve(),
    Path("C:\\Program Files").resolve(),
    Path("C:\\Program Files (x86)").resolve(),
]

_HOME = Path.home().resolve()


def _is_system_root(path: Path) -> bool:
    """Check if a path is a system root or user home root."""
    resolved = path.resolve()
    # Drive root (C:\, D:\, etc.) — anchor is a string (e.g. "C:\\")
    try:
        if resolved == Path(resolved.anchor):
            return True
    except Exception:
        pass
    # User home root
    return resolved == _HOME


def _detect_git_repo(path: Path) -> tuple[bool, bool, list[str]]:
    """Detect if path is in a Git repo and whether it has a dirty working tree.

    Returns ``(is_git_repo, is_dirty, changed_files)``.
    """
    git_dir = _find_git_dir(path)
    if git_dir is None:
        return False, False, []

    try:
        result = subprocess.run(
            ["git", "-C", str(path), "status", "--short"],
            capture_output=True,
            text=True,
            shell=False,
            timeout=15,
        )
        output = result.stdout.strip()
        if not output:
            return True, False, []
        lines = [line.strip() for line in output.split("\n") if line.strip()]
        # Parse status lines: "M file.py", "?? new.txt", etc.
        changed = []
        for line in lines:
            parts = line.split(None, 1)
            if len(parts) == 2:
                changed.append(parts[1])
            elif len(parts) == 1:
                changed.append(parts[0])
        return True, True, changed
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        return True, False, []


def _find_git_dir(path: Path) -> Path | None:
    """Walk up from path looking for a .git directory."""
    current = path.resolve()
    while current != current.parent:
        git_path = current / ".git"
        if git_path.is_dir() or git_path.is_file():
            return current
        current = current.parent
    return None


def _find_repo_root(path: Path) -> Path | None:
    """Find the repo root for a given workspace path.

    Finds the nearest ancestor directory containing ``.git``, regardless
    of whether ``path`` itself is inside a git repository.
    """
    git_dir = _find_git_dir(path)
    if git_dir is not None:
        return git_dir
    return None


# ---------------------------------------------------------------------------
# Guard
# ---------------------------------------------------------------------------


def check_real_execution_safety(
    workspace_path: str,
    *,
    allow_repo_root_execution: bool = False,
    allow_dirty_git: bool = False,
    enforce_allowed_files: bool = True,
) -> RealExecutionGuardResult:
    """Check if real execution is safe for the given workspace.

    Parameters
    ----------
    workspace_path:
        Absolute or relative path to the workspace.
    allow_repo_root_execution:
        If True, allow real execution even when workspace is a repo root.
    allow_dirty_git:
        If True, allow real execution even when the Git workspace is dirty.
    enforce_allowed_files:
        If True, enforce allowed/forbidden file rules.

    Returns
    -------
    ``RealExecutionGuardResult`` with ``allowed``, ``failure_reasons``,
    and diagnostic fields.

    Raises
    ------
    ``RealExecutionGuardError`` only on internal guard failures, not
    on policy violations. Policy violations are returned in the result.
    """
    reasons: list[str] = []
    ws = Path(workspace_path).resolve()

    if not ws.exists():
        reasons.append(f"Workspace path does not exist: {ws}")

    # 1. System root / home root check
    if _is_system_root(ws):
        reasons.append(
            f"Real execution blocked: workspace {ws} is a system or user home root."
        )

    # 2. Forbidden paths (exact match only — not ancestor match)
    for forbidden in _FORBIDDEN_WORKSPACE_ROOTS:
        if ws == forbidden:
            reasons.append(
                f"Real execution blocked: workspace {ws} is a "
                f"forbidden path."
            )
            break

    # 3. Repo root check
    repo_root = _find_repo_root(ws)
    is_repo_root = repo_root is not None and repo_root == ws
    if is_repo_root and not allow_repo_root_execution:
        reasons.append(
            f"Real execution blocked: workspace {ws} is a Git repository root. "
            f"Use --allow-repo-root-execution to override."
        )

    # 4. Dirty Git workspace check
    is_git, is_dirty, changed_before = _detect_git_repo(ws)
    if is_dirty and not allow_dirty_git:
        reasons.append(
            f"Real execution blocked: Git working tree is dirty "
            f"({len(changed_before)} changed file(s)). "
            f"Use --allow-dirty-git to override."
        )

    if reasons:
        return RealExecutionGuardResult(
            allowed=False,
            failure_reasons=reasons,
            workspace_path=str(ws),
            is_git_repo=is_git,
            is_dirty=is_dirty,
            changed_files_before=changed_before,
        )

    return RealExecutionGuardResult(
        allowed=True,
        workspace_path=str(ws),
        is_git_repo=is_git,
        is_dirty=is_dirty,
        changed_files_before=changed_before,
    )


def check_changed_files_safe(
    changed_files: list[str],
    *,
    allowed_files: list[str] | None = None,
    forbidden_files: list[str] | None = None,
) -> list[str]:
    """Check if changed files violate allowed/forbidden rules.

    Parameters
    ----------
    changed_files:
        List of file paths changed during execution.
    allowed_files:
        If provided, only changes to these files are permitted.
    forbidden_files:
        If provided, changes to these files always fail.

    Returns
    -------
    List of failure reason strings (empty if safe).
    """
    reasons: list[str] = []

    safe_allowed = allowed_files or []
    safe_forbidden = forbidden_files or []

    for changed in changed_files:
        cp = Path(changed)

        # Check forbidden list
        for forbidden in safe_forbidden:
            fp = Path(forbidden)
            try:
                cp.relative_to(fp)
                reasons.append(
                    f"Changed file {changed} is in forbidden path {forbidden}."
                )
                break
            except ValueError:
                continue

        # Check allowed list (if enforced)
        if safe_allowed:
            allowed_match = False
            for allowed in safe_allowed:
                ap = Path(allowed)
                try:
                    cp.relative_to(ap)
                    allowed_match = True
                    break
                except ValueError:
                    continue
            if not allowed_match:
                reasons.append(
                    f"Changed file {changed} is not in allowed files: {safe_allowed}."
                )

    return reasons
