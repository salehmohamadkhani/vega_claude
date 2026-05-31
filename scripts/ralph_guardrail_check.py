#!/usr/bin/env python3
"""
Ralph Self-Verifying Guardrail Check
=====================================
Pre-commit safety gate for Ralph-controlled implementations.

Checks:
  1. Git / worktree safety (branch, dirty, staged/unstaged, unexpected files)
  2. Secret scan (obvious patterns, .env/.pem/.key/.json files — redacted)
  3. Test safety (py_compile + pytest via uv run or python3 -m)
  4. Port / service safety (protected ports untouched — read-only)
  5. Report generation (Markdown at /opt/vega-cloud/spc/reports/)

Exit 0 only when ALL critical gates pass.
Exit non-zero and print the failed gate(s) otherwise.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# ── paths ───────────────────────────────────────────────────────────────────

HARDCODED_ROOT = Path("/opt/vega-cloud/vega_claude/worktrees/vega-ralph-1")


def _discover_root() -> Path:
    """Use git rev-parse --show-toplevel, or fall back to CWD."""
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=10,
        )
        if r.returncode == 0:
            return Path(r.stdout.strip())
    except Exception:
        pass
    return Path.cwd().resolve()


ROOT = _discover_root()
MAIN_REPO = Path("/opt/vega-cloud/vega_claude/free-claude-code")
REPORTS_DIR = Path("/opt/vega-cloud/spc/reports")
PROTECTED_PORTS = [8082]

# Nested subrepos / dirs in the worktree that are NOT Ralph's to validate
SUBREPO_DIRS = {
    "free-claude-code",
    "copilot-ralph-mode",
}

# Allowed path prefixes for git changes (relative to ROOT)
ALLOWED_PREFIXES = [
    "docs/ralph/",
    "scripts/ralph_",
    "scripts/",
    "tests/ralph/",
    "tests/",
]
ALLOWED_FILES = {
    "ralph-adapter.sh",
}
GENERATED_EXTS = {".pyc", ".pyo", ".log"}
GENERATED_DIRS = {"__pycache__", ".pytest_cache", ".mypy_cache", ".venv"}

RUNTIME_DIRS = {".fcc", ".ralph-mode"}

RISKY_FILE_PATTERNS = [
    r"\.env(\..*)?$",
    r"\.pem$",
    r"\.key$",
    r"service-account.*\.json$",
    r"credentials.*\.json$",
    r"secrets\.(yml|yaml|json|toml)$",
]
SECRET_PATTERNS = [
    (r'(?:TELEGRAM_BOT_TOKEN|BOT_TOKEN)\s*[=:]\s*\S+', "TOKEN variable"),
    (r'(?:DEEPSEEK_API_KEY|API_KEY|api_key)\s*[=:]\s*\S+', "API key variable"),
    (r'\d{9,10}:AA[A-Za-z0-9_-]{30,}', "Telegram bot token"),
    (r'(?:sk-)[A-Za-z0-9]{20,}', "API key (sk-...)"),
    (r'(?:ghp_|gho_|ghu_|ghs_|ghr_)[A-Za-z0-9_]{36,}', "GitHub token"),
    (r'(?:-----BEGIN\s+(?:RSA\s+)?PRIVATE\s+KEY-----)', "Private key PEM"),
    (r'(?:-----BEGIN\s+OPENSSH\s+PRIVATE\s+KEY-----)', "SSH private key"),
]

# ── state ───────────────────────────────────────────────────────────────────

results: list[dict] = []
secret_matches: list[dict] = []
all_pass = True


def _is_in_subrepo(path: Path) -> bool:
    """Return True if path is inside a nested git checkout (not Ralph's code)."""
    try:
        rel = path.relative_to(ROOT)
    except ValueError:
        return True
    for part in rel.parts:
        if part in SUBREPO_DIRS:
            return True
    return False


def _is_runtime(path: Path) -> bool:
    """Return True if path is a runtime dir that should never be committed."""
    try:
        rel = path.relative_to(ROOT)
    except ValueError:
        return False
    for part in rel.parts:
        if part in RUNTIME_DIRS:
            return True
    return False


PASS_C = "\033[32m"
WARN_C = "\033[33m"
FAIL_C = "\033[31m"
RST = "\033[0m"

def _log(gate: str, status: str, detail: str = "") -> None:
    results.append({"gate": gate, "status": status, "detail": detail})
    if status == "PASS":
        print(f"  [{PASS_C}PASS{RST}] {gate}")
    elif status == "WARN":
        print(f"  [{WARN_C}WARN{RST}] {gate}" + (f" — {detail}" if detail else ""))
    else:
        global all_pass
        all_pass = False
        print(f"  [{FAIL_C}{status}{RST}] {gate}" + (f" — {detail}" if detail else ""))


def _run(cmd: list[str], cwd: Path | None = None, timeout: int = 30) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(cmd, cwd=cwd or str(ROOT), capture_output=True,
                              text=True, timeout=timeout)
    except FileNotFoundError:
        return subprocess.CompletedProcess(args=cmd, returncode=-1, stdout="", stderr=f"binary not found: {cmd[0]}")


def _redact(text: str) -> str:
    for pat, _ in SECRET_PATTERNS:
        text = re.sub(pat, "***REDACTED***", text, flags=re.IGNORECASE)
    return text


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Git / worktree safety
# ═══════════════════════════════════════════════════════════════════════════════

def check_git_safety() -> None:
    _log("git.root", "PASS", f"ROOT={ROOT}")

    if not (ROOT / ".git").exists():
        _log("git.worktree_exists", "FAIL", f"No .git found at {ROOT}")
        return

    branch = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    status = _run(["git", "status", "--short"])
    staged = _run(["git", "diff", "--cached", "--name-only"])

    branch_name = branch.stdout.strip() if branch.returncode == 0 else "unknown"
    status_lines = [l for l in status.stdout.split("\n") if l.strip()] if status.returncode == 0 else []
    staged_lines = [l for l in staged.stdout.split("\n") if l.strip()] if staged.returncode == 0 else []

    _log("git.branch", "PASS" if branch_name else "WARN", f"branch={branch_name}")
    _log("git.untracked", "WARN" if status_lines else "PASS", f"{len(status_lines)} untracked files" if status_lines else "clean")
    if staged_lines:
        _log("git.staged", "WARN", f"{len(staged_lines)} staged ({', '.join(staged_lines[:5])})")

    # Check for unexpected files (only top-level — skip subrepo content)
    unexpected = []
    for line in status_lines:
        if len(line) < 4:
            continue
        path = line[3:].strip()
        # Skip nested subrepo paths entirely
        p = Path(path)
        if any(part in SUBREPO_DIRS for part in p.parts):
            continue
        # Skip runtime dirs
        if any(part in RUNTIME_DIRS for part in p.parts):
            continue
        if any(path.startswith(prefix) or path == f for prefix in ALLOWED_PREFIXES for f in ALLOWED_FILES):
            continue
        if path in ALLOWED_FILES:
            continue
        if p.suffix in GENERATED_EXTS or p.name in GENERATED_DIRS:
            continue
        unexpected.append(path)

    if unexpected:
        _log("git.unexpected", "FAIL" if len(unexpected) > 5 else "WARN",
             f"{len(unexpected)} file(s) outside allowed paths ({', '.join(unexpected[:6])})")
    else:
        _log("git.unexpected", "PASS", "all files in allowed paths")

    # Check main VegaClaw untouched
    main_status = _run(["git", "status", "--short"], cwd=MAIN_REPO)
    if main_status.returncode == 0 and main_status.stdout.strip():
        lines = [l for l in main_status.stdout.split("\n") if l.strip()
                 and "../worktrees/" not in l and "worktrees/" not in l]
        tracked_changes = [l for l in lines if not l.startswith("??")]
        if tracked_changes:
            _log("git.main_untouched", "FAIL",
                 f"main repo has tracked changes ({len(tracked_changes)} line(s))")
        elif lines:
            _log("git.main_untouched", "PASS", "main repo clean (only untracked worktree refs)")
        else:
            _log("git.main_untouched", "PASS", "main repo completely clean")
    else:
        _log("git.main_untouched", "PASS", "main repo clean")


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Secret scan
# ═══════════════════════════════════════════════════════════════════════════════

def _scan_file_for_secrets(path: Path) -> list[dict]:
    found: list[dict] = []
    try:
        text = path.read_text(errors="replace")
    except Exception:
        return found
    for pattern, label in SECRET_PATTERNS:
        for m in re.finditer(pattern, text, re.IGNORECASE):
            found.append({"file": str(path.relative_to(ROOT)), "pattern": label, "match": m.group()[:30] + "..."})
    return found


def check_secret_safety() -> None:
    risky_files = []
    for pattern in RISKY_FILE_PATTERNS:
        for p in ROOT.rglob("*"):
            if not p.is_file() or _is_in_subrepo(p) or _is_runtime(p):
                continue
            if re.search(pattern, p.name, re.IGNORECASE):
                risky_files.append(p)

    for p in risky_files:
        _log("secrets.risky_file", "WARN",
             f"file with risky extension: {p.relative_to(ROOT)}")

    files_to_scan = []
    EXCLUDED_DIRS = (".git/", ".venv/", "__pycache__/", ".mypy_cache/",
                     ".pytest_cache/", ".ralph-mode/", ".fcc/")
    for p in ROOT.rglob("*"):
        if not p.is_file():
            continue
        if _is_in_subrepo(p) or _is_runtime(p):
            continue
        rel_str = str(p.relative_to(ROOT))
        if any(rel_str.startswith(d) for d in EXCLUDED_DIRS):
            continue
        if p.suffix in (".pyc", ".pyo", ".log"):
            continue
        if p.stat().st_size > 500_000:
            continue
        files_to_scan.append(p)

    total_matches = 0
    for f in files_to_scan:
        matches = _scan_file_for_secrets(f)
        for m in matches:
            total_matches += 1
            secret_matches.append(m)
            if total_matches <= 5:
                _log("secrets.found", "FAIL" if not m["match"].startswith("***") else "WARN",
                     f"{m['file']}: {m['pattern']} ({_redact(m['match'])})")

    if total_matches == 0:
        _log("secrets.scan", "PASS", "no secrets detected in worktree files")
    else:
        redacted_only = all("***REDACTED***" in m.get("match", "") for m in secret_matches)
        _log("secrets.scan", "FAIL" if not redacted_only else "WARN",
             f"{total_matches} pattern(s) matched (all pre-redacted or benign)")


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Test safety
# ═══════════════════════════════════════════════════════════════════════════════

def check_test_safety() -> None:
    # ── py_compile (only Ralph's own Python files, no subrepos) ────────────
    python_files = []
    for p in ROOT.rglob("*.py"):
        if ".git" in str(p) or ".venv" in str(p):
            continue
        if _is_in_subrepo(p) or _is_runtime(p):
            continue
        python_files.append(p)

    if not python_files:
        _log("tests.py_compile", "SKIP", "no Ralph Python files to compile")
    else:
        all_ok = True
        for pf in python_files:
            r = _run(["python3", "-m", "py_compile", str(pf)])
            if r.returncode != 0:
                all_ok = False
                stderr_line = r.stderr.split("\n")[-2] if r.stderr else ""
                _log("tests.py_compile", "FAIL", f"{pf.relative_to(ROOT)}: {stderr_line}")
        if all_ok:
            _log("tests.py_compile", "PASS", f"{len(python_files)} Ralph file(s) compiled OK")

    # ── pytest (try uv run pytest first, then python3 -m pytest) ─────────
    test_dirs = list((ROOT / "tests").glob("*")) if (ROOT / "tests").exists() else []
    if not test_dirs:
        _log("tests.pytest", "SKIP", "no tests/ directory found")
    else:
        # Try uv run pytest
        cmd = None
        uv_bin = shutil.which("uv")
        if uv_bin:
            cmd = [uv_bin, "run", "pytest", "tests/", "-q", "--tb=short"]
        else:
            cmd = ["python3", "-m", "pytest", "tests/", "-q", "--tb=short"]

        r = _run(cmd, timeout=120)
        if r.returncode == 0:
            last_line = [l for l in r.stdout.split("\n") if l.strip()][-1] if r.stdout.strip() else r.stdout[:80]
            _log("tests.pytest", "PASS", last_line)
        else:
            _log("tests.pytest", "FAIL",
                 f"exit={r.returncode}: {r.stdout.split(chr(10))[-3] if r.stdout else r.stderr[:100]}".strip())

    # ── Guarded script syntax check ──────────────────────────────────────
    r99_script = ROOT / "scripts" / "ralph_r9_guarded_run_check.sh"
    if r99_script.exists():
        r = _run(["bash", "-n", str(r99_script)])
        _log("tests.script_syntax", "PASS" if r.returncode == 0 else "FAIL",
             "ralph_r9_guarded_run_check.sh syntax check")


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Port / service safety
# ═══════════════════════════════════════════════════════════════════════════════

def check_port_safety() -> None:
    ss = _run(["ss", "-ltnp"])
    if ss.returncode != 0:
        _log("ports.ss_check", "FAIL", "ss command failed")
        return

    for port in PROTECTED_PORTS:
        if f":{port}" in ss.stdout:
            _log("ports.protected", "PASS", f"port {port} is present (untouched)")
        else:
            _log("ports.protected", "FAIL", f"port {port} NOT FOUND!")


# ═══════════════════════════════════════════════════════════════════════════════
# 5. Report generation
# ═══════════════════════════════════════════════════════════════════════════════

def generate_report() -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    branch = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"]).stdout.strip() or "unknown"

    status_out = _run(["git", "status", "--short"])
    changed_files = [l.strip() for l in status_out.stdout.split("\n") if l.strip()] if status_out.returncode == 0 else []

    passes = sum(1 for r in results if r["status"] == "PASS")
    warns = sum(1 for r in results if r["status"] == "WARN")
    fails = sum(1 for r in results if r["status"] == "FAIL")
    skips = sum(1 for r in results if r["status"] == "SKIP")
    verdict = "PASS" if all_pass and fails == 0 else "FAIL"

    report_lines = [
        "# Ralph R10 Self-Verifying Guardrails Report",
        "",
        f"**Date:** {ts}",
        f"**Verdict:** {verdict}",
        f"**Root:** {ROOT}",
        "",
        "## Summary",
        "",
        "| Gate | Count |",
        "|------|-------|",
        f"| PASS | {passes} |",
        f"| WARN | {warns} |",
        f"| FAIL | {fails} |",
        f"| SKIP | {skips} |",
        "",
        "## Current Branch",
        "",
        branch,
        "",
        "## Files Changed",
        "",
        "```",
        "\n".join(changed_files) if changed_files else "(no changes)",
        "```",
        "",
        "## Guardrail Checks",
        "",
        "| Gate | Status | Detail |",
        "|------|--------|--------|",
    ]
    for r in results:
        detail = r["detail"].replace("|", "\\|").replace("\n", " ") if r["detail"] else ""
        report_lines.append(f"| {r['gate']} | {r['status']} | {detail} |")

    report_lines.append("")
    report_lines.append("## Secret Scan")
    report_lines.append("")
    if secret_matches:
        report_lines.append(f"{len(secret_matches)} match(es) found:")
        for m in secret_matches[:10]:
            report_lines.append(f"- {m['file']}: {m['pattern']} — {_redact(m['match'])}")
        if len(secret_matches) > 10:
            report_lines.append(f"- ... and {len(secret_matches) - 10} more")
    else:
        report_lines.append("No secrets detected.")

    py_result = "FAIL" if any(r["gate"] == "tests.py_compile" and r["status"] == "FAIL" for r in results) else "PASS" if any(r["gate"] == "tests.py_compile" and r["status"] == "PASS" for r in results) else "SKIP"
    pytest_result = "FAIL" if any(r["gate"] == "tests.pytest" and r["status"] == "FAIL" for r in results) else "PASS" if any(r["gate"] == "tests.pytest" and r["status"] == "PASS" for r in results) else "SKIP"

    report_lines.extend([
        "",
        "## Test Results",
        "",
        f"- py_compile: {py_result}",
        f"- pytest: {pytest_result}",
        "",
        "## Protected Ports",
        "",
        f"- 8082: {'PASS (present)' if any(r['gate'] == 'ports.protected' and r['status'] == 'PASS' for r in results) else 'FAIL'}",
        "",
        "## Unexpected Worktree Edits",
        "",
        _list_unexpected(),
        "",
        "## Commit Readiness",
        "",
        f"**{'READY — all critical gates pass' if all_pass else 'NOT READY — failures above must be resolved'}**",
        "",
        "## Remaining Risks",
        "",
        "- Guardrail script itself should be reviewed before first production use.",
        "- Secret scanning is regex-based; false positives may occur.",
        "- The guardrail only checks the worktree; main repo should be independently verified.",
        "",
        "## Recommended R11",
        "",
        "Run this guardrail script as part of the Ralph loop itself, creating a",
        "self-validating workflow where Ralph rejects its own output if guardrails fail.",
    ])

    report = "\n".join(report_lines)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORTS_DIR / "RALPH_MODE_R10_SELF_VERIFYING_GUARDRAILS_REPORT.md"
    report_path.write_text(report)
    _log("report.generated", "PASS", f"report written to {report_path}")
    return report_path


def _list_unexpected() -> str:
    r = _run(["git", "status", "--short"])
    if r.returncode != 0:
        return "(could not check)"
    lines = [l.strip() for l in r.stdout.split("\n") if l.strip() and not l.strip().startswith("?? ")]
    return "\n".join(lines) if lines else "None."


# ═══════════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════════

def main() -> int:
    print("=" * 60)
    print("  Ralph Self-Verifying Guardrail Check")
    print("=" * 60)
    print()

    check_git_safety()
    print()
    check_secret_safety()
    print()
    check_test_safety()
    print()
    check_port_safety()
    print()

    report_path = generate_report()

    print()
    print(f"Report: {report_path}")
    print(f"Verdict: {'PASS' if all_pass else 'FAIL'}")

    if not all_pass:
        print("\nOne or more critical gates failed. Review and fix before proceeding.")
        return 1

    print("\nAll critical gates pass. Ready for commit.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
