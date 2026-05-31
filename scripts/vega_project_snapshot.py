#!/usr/bin/env python3
"""Vega Project Snapshot — static worktree map (no LLM calls)."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path

IGNORE_DIRS = {
    ".git", ".venv", ".fcc", ".ralph-mode",
    ".pytest_cache", "__pycache__", "node_modules", ".mypy_cache",
}
IGNORE_FILES = {
    ".env", ".env.example", ".env.local",
    "sessions.sqlite", "state.json",
}
IGNORE_EXTS = {".pyc", ".pyo", ".log"}

SUSPICIOUS_PATTERNS = [
    "TELEGRAM_BOT_TOKEN", "DEEPSEEK_API_KEY", "sk-ghp_", "-----BEGIN ",
]


def _get_root() -> Path:
    """Discover repo root via git, fall back to CWD."""
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=5,
        )
        if r.returncode == 0:
            return Path(r.stdout.strip())
    except Exception:
        pass
    return Path.cwd().resolve()


def _get_branch(root: Path) -> str:
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=root, capture_output=True, text=True, timeout=5,
        )
        if r.returncode == 0:
            return r.stdout.strip()
    except Exception:
        pass
    return "unknown"


def _scan(root: Path) -> dict:
    """Scan the worktree and return a structured dict."""
    branch = _get_branch(root)
    all_files: list[Path] = []
    total_size = 0

    for p in root.rglob("*"):
        if not p.is_file():
            continue
        try:
            rel = p.relative_to(root)
        except ValueError:
            continue
        parts = rel.parts
        if any(part in IGNORE_DIRS for part in parts):
            continue
        if p.name in IGNORE_FILES:
            continue
        if p.suffix in IGNORE_EXTS:
            continue
        all_files.append(rel)
        try:
            total_size += p.stat().st_size
        except OSError:
            pass

    extensions = Counter(p.suffix for p in all_files if p.suffix)
    top_dirs_seen: set[str] = set()
    for p in all_files:
        parts = p.parts
        if parts:
            top_dirs_seen.add(parts[0])

    test_dirs = sorted(
        d.relative_to(root) for d in root.rglob("tests")
        if d.is_dir() and ".git" not in str(d)
    )
    doc_dirs = sorted(
        d.relative_to(root) for d in root.rglob("docs")
        if d.is_dir() and ".git" not in str(d)
    )

    important_files = [
        str(p) for p in all_files
        if p.name in ("README.md", "CLAUDE.md", "AGENTS.md", "pyproject.toml", "Makefile",
                      "ralph-adapter.sh", "ralph-loop-guarded.sh")
        or p.name.startswith("test_")
        or p.name == "vega_project_snapshot.py"
    ]

    # Check for suspicious content
    suspicious: list[str] = []
    for rel_path in all_files[:50]:  # limit to first 50 files
        try:
            text = (root / rel_path).read_text(errors="replace")
            for pat in SUSPICIOUS_PATTERNS:
                if pat in text:
                    suspicious.append(str(rel_path))
                    break
        except Exception:
            pass

    return {
        "repo_root": str(root),
        "branch": branch,
        "git_clean": _git_clean(root),
        "total_files": len(all_files),
        "total_size_bytes": total_size,
        "top_level_dirs": sorted(top_dirs_seen),
        "extensions": dict(extensions.most_common(20)),
        "important_files": important_files,
        "test_dirs": [str(d) for d in test_dirs],
        "doc_dirs": [str(d) for d in doc_dirs],
        "suspicious_count": len(suspicious),
        "suspicious_files": suspicious[:10],
    }


def _git_clean(root: Path) -> bool:
    try:
        r = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=root, capture_output=True, text=True, timeout=5,
        )
        return r.returncode == 0 and not r.stdout.strip()
    except Exception:
        return False


def _render_markdown(data: dict) -> str:
    lines = [
        "# Vega Project Snapshot",
        "",
        f"**Repo root:** `{data['repo_root']}`",
        f"**Branch:** `{data['branch']}`",
        f"**Git clean:** {data['git_clean']}",
        f"**Total source-like files:** {data['total_files']}",
        f"**Total size:** {_fmt_size(data['total_size_bytes'])}",
        "",
        "## Top-Level Directories",
        "",
    ]
    for d in data["top_level_dirs"]:
        lines.append(f"- `{d}/`")
    lines += [
        "",
        "## File Extensions",
        "",
        "| Extension | Count |",
        "|-----------|-------|",
    ]
    for ext, count in data["extensions"].items():
        lines.append(f"| `{ext}` | {count} |")
    lines += ["", "## Important Files", ""]
    for f in data["important_files"]:
        lines.append(f"- `{f}`")
    lines += ["", "## Test Directories", ""]
    for d in data["test_dirs"]:
        lines.append(f"- `{d}/`")
    lines += ["", "## Doc Directories", ""]
    for d in data["doc_dirs"]:
        lines.append(f"- `{d}/`")
    if data["suspicious_count"] > 0:
        lines += ["", "## Suspicious Content", ""]
        lines.append(f"{data['suspicious_count']} file(s) matched suspicious patterns.")
        for f in data["suspicious_files"]:
            lines.append(f"- `{f}`")
    else:
        lines += ["", "## Suspicious Content", "", "None detected."]
    return "\n".join(lines)


def _fmt_size(b: int) -> str:
    if b < 1024:
        return f"{b} B"
    if b < 1024 ** 2:
        return f"{b / 1024:.1f} KB"
    return f"{b / 1024 ** 2:.1f} MB"


def main() -> int:
    parser = argparse.ArgumentParser(description="Vega Project Snapshot")
    parser.add_argument("--json", action="store_true", help="Output JSON instead of Markdown")
    args = parser.parse_args()

    root = _get_root()
    data = _scan(root)

    if args.json:
        json.dump(data, sys.stdout, indent=2)
        print()
    else:
        print(_render_markdown(data))

    return 0


if __name__ == "__main__":
    sys.exit(main())
