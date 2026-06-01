"""Agent Council V2 — Runtime Sandbox.

Isolated workspace management for deterministic evidence-gated backtests.

Provides sandbox run directories, manifest files, artifact collection,
cleanliness validation, and summaries — all outside the VegaClaw source tree.

Supports host-native mode and Docker-optional mode. All operations are
deterministic. No LLM/network calls. No shell commands in tests.

Intended sandbox root:
    /opt/vega-cloud/sandboxes

Fallback (used when /opt/vega-cloud is not writable):
    /tmp/vega-sandboxes
"""

from __future__ import annotations

import json
import os
import shutil
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

INTENDED_SANDBOX_ROOT = "/opt/vega-cloud/sandboxes"
FALLBACK_SANDBOX_ROOT = "/tmp/vega-sandboxes"

FORBIDDEN_PATH_PATTERNS: tuple[str, ...] = (
    ".fcc/",
    ".fcc-ralph/",
    ".claude/",
    ".env",
    ".git-credentials",
    "secrets",
    "credentials",
    "raw_research_repos",
    "/opt/vega-cloud/research/repos",
    "server_tracker",
    "logs/",
)

ALLOWED_EXTENSIONS: tuple[str, ...] = (
    ".py",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".cfg",
    ".md",
    ".txt",
    ".html",
    ".css",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".rs",
    ".go",
    ".java",
    ".c",
    ".h",
    ".cpp",
    ".hpp",
    ".sh",
    ".sql",
    ".graphql",
    ".svg",
    ".png",
    ".jpg",
    ".jpeg",
)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class SandboxManifest:
    """Metadata written alongside each sandbox run."""

    run_id: str = ""
    phase: str = ""
    project_type: str = ""
    project_goal: str = ""
    created_at: str = ""
    operator: str = "SPC"
    sandbox_mode: str = "host-native"  # host-native | docker
    sandbox_root: str = ""
    allowed_output_paths: list[str] = field(default_factory=list)
    forbidden_paths: list[str] = field(default_factory=list)
    expected_artifacts: list[str] = field(default_factory=list)
    verification_commands: list[str] = field(default_factory=list)
    evidence_gate_mode: str = "disabled"  # disabled | warning | strict
    docker_image: str = ""
    docker_command: list[str] = field(default_factory=list)
    notes: str = ""


@dataclass
class SandboxArtifactReport:
    """Collected artifacts and validation results from a sandbox run."""

    run_dir: str = ""
    run_id: str = ""
    files_found: list[str] = field(default_factory=list)
    files_empty: list[str] = field(default_factory=list)
    files_large: list[str] = field(default_factory=list)
    files_forbidden: list[str] = field(default_factory=list)
    extensions_found: dict[str, int] = field(default_factory=dict)
    total_files: int = 0
    total_size_bytes: int = 0
    manifest_valid: bool = False
    sandbox_clean: bool = True
    violations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------


def resolve_sandbox_root(requested: str = "") -> str:
    """Return the active sandbox root path.

    Uses the requested path if writable, then INTENDED_SANDBOX_ROOT,
    then FALLBACK_SANDBOX_ROOT.
    """
    if requested and os.path.isdir(requested):
        return requested
    if os.path.isdir(INTENDED_SANDBOX_ROOT) and os.access(
        INTENDED_SANDBOX_ROOT, os.W_OK
    ):
        return INTENDED_SANDBOX_ROOT
    return FALLBACK_SANDBOX_ROOT


# ---------------------------------------------------------------------------
# Run directory management
# ---------------------------------------------------------------------------


def create_sandbox_run_dir(
    root: str = "",
    prefix: str = "vegaclaw-backtest",
) -> str:
    """Create a timestamped sandbox run directory.

    Args:
        root: Sandbox root path (auto-resolved if empty).
        prefix: Directory name prefix.

    Returns:
        Absolute path to the created run directory.

    Raises:
        OSError: If the directory cannot be created.
    """
    sandbox_root = resolve_sandbox_root(root)
    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    dirname = f"{prefix}-{timestamp}"
    run_dir = os.path.join(sandbox_root, "runs", dirname)
    os.makedirs(run_dir, exist_ok=True)
    return run_dir


def _make_run_id(prefix: str = "vegaclaw") -> str:
    """Generate a simple run ID."""
    ts = int(time.time() * 1000)
    return f"{prefix}-{ts:x}"


def write_sandbox_manifest(
    run_dir: str,
    manifest: dict[str, object],
) -> str:
    """Write a sandbox manifest file to the run directory.

    Args:
        run_dir: Path to the sandbox run directory.
        manifest: Dict with manifest fields.

    Returns:
        Path to the written manifest.json file.
    """
    os.makedirs(run_dir, exist_ok=True)
    manifest.setdefault("run_id", _make_run_id())
    manifest.setdefault("created_at", datetime.now(UTC).isoformat())

    manifest_path = os.path.join(run_dir, "manifest.json")
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2, default=str)
    return manifest_path


def read_sandbox_manifest(run_dir: str) -> dict[str, object] | None:
    """Read a sandbox manifest from a run directory.

    Returns None if no manifest exists.
    """
    path = os.path.join(run_dir, "manifest.json")
    if not os.path.isfile(path):
        return None
    with open(path) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Artifact collection and validation
# ---------------------------------------------------------------------------


def collect_sandbox_artifacts(run_dir: str) -> dict[str, object]:
    """Collect and catalog all artifacts in a sandbox run directory.

    Walks the directory tree, records file metadata, and detects
    forbidden paths and empty files.

    Args:
        run_dir: Path to the sandbox run directory.

    Returns:
        Dict with files_found, files_empty, files_forbidden,
        total_files, total_size_bytes, violations, warnings.
    """
    files_found: list[str] = []
    files_empty: list[str] = []
    files_forbidden: list[str] = []
    extensions: dict[str, int] = {}
    total_size = 0
    violations: list[str] = []
    warnings: list[str] = []

    if not os.path.isdir(run_dir):
        return {
            "files_found": [],
            "files_empty": [],
            "files_forbidden": [],
            "extensions_found": {},
            "total_files": 0,
            "total_size_bytes": 0,
            "violations": [f"Run directory not found: {run_dir}"],
            "warnings": [],
        }

    for dirpath, _dirnames, filenames in os.walk(run_dir):
        for fname in filenames:
            full_path = os.path.join(dirpath, fname)
            rel_path = os.path.relpath(full_path, run_dir)

            # Skip manifest itself
            if fname == "manifest.json":
                continue

            try:
                size = os.path.getsize(full_path)
            except OSError:
                warnings.append(f"Cannot read size: {rel_path}")
                continue

            total_size += size
            files_found.append(rel_path)

            # Check empty
            if size == 0:
                files_empty.append(rel_path)

            # Check forbidden
            for pattern in FORBIDDEN_PATH_PATTERNS:
                if pattern in full_path:
                    files_forbidden.append(rel_path)
                    violations.append(
                        f"Forbidden path pattern '{pattern}' found: {rel_path}"
                    )
                    break

            # Track extensions
            _, ext = os.path.splitext(fname)
            if ext:
                extensions[ext] = extensions.get(ext, 0) + 1

    return {
        "files_found": sorted(files_found),
        "files_empty": sorted(files_empty),
        "files_forbidden": sorted(files_forbidden),
        "extensions_found": extensions,
        "total_files": len(files_found),
        "total_size_bytes": total_size,
        "violations": sorted(violations),
        "warnings": sorted(warnings),
    }


def validate_sandbox_cleanliness(run_dir: str) -> dict[str, object]:
    """Validate that a sandbox run directory is clean.

    Checks:
    - No forbidden paths anywhere under the run directory
    - No empty expected artifact files
    - All files have allowed extensions (warn only)

    Args:
        run_dir: Path to the sandbox run directory.

    Returns:
        Dict with clean(bool), violations, warnings, summary.
    """
    artifacts = collect_sandbox_artifacts(run_dir)
    violations: list[str] = list(artifacts.get("violations", []))
    warnings: list[str] = list(artifacts.get("warnings", []))
    empty = artifacts.get("files_empty", [])

    # Empty file warnings
    warnings.extend(f"Empty file: {f}" for f in empty)

    # Allowed extension check (warn only)
    for f in artifacts.get("files_found", []):
        _, ext = os.path.splitext(f)
        if ext and ext not in ALLOWED_EXTENSIONS:
            warnings.append(f"Unusual extension '{ext}' for file: {f}")

    clean = len(violations) == 0

    return {
        "clean": clean,
        "violations": sorted(violations),
        "warnings": sorted(warnings),
        "empty_files": sorted(empty),
        "forbidden_files": artifacts.get("files_forbidden", []),
        "total_files": artifacts.get("total_files", 0),
        "summary": (
            f"Sandbox {'clean' if clean else 'DIRTY'}: "
            f"{len(violations)} violations, "
            f"{len(warnings)} warnings, "
            f"{artifacts.get('total_files', 0)} files"
        ),
    }


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------


def summarize_sandbox_run(run_dir: str) -> str:
    """Produce a human-readable summary of a sandbox run.

    Args:
        run_dir: Path to the sandbox run directory.

    Returns:
        Multi-line summary string.
    """
    manifest = read_sandbox_manifest(run_dir)
    cleanliness = validate_sandbox_cleanliness(run_dir)

    lines: list[str] = []
    lines.append("=" * 60)
    lines.append("SANDBOX RUN SUMMARY")
    lines.append("=" * 60)
    lines.append(f"Run Dir:   {run_dir}")

    if manifest:
        lines.append(f"Run ID:    {manifest.get('run_id', 'unknown')}")
        lines.append(f"Phase:     {manifest.get('phase', 'unknown')}")
        lines.append(f"Project:   {manifest.get('project_type', 'unknown')}")
        lines.append(f"Goal:      {manifest.get('project_goal', 'unknown')}")
        lines.append(f"Mode:      {manifest.get('sandbox_mode', 'unknown')}")
        lines.append(f"Gate Mode: {manifest.get('evidence_gate_mode', 'disabled')}")

    lines.append("")
    lines.append(
        f"Clean:     {'Yes' if cleanliness['clean'] else 'NO — see violations'}"
    )
    lines.append(f"Files:     {cleanliness.get('total_files', 0)}")
    lines.append(f"Violations: {len(cleanliness.get('violations', []))}")
    lines.append(f"Warnings:  {len(cleanliness.get('warnings', []))}")

    violations = cleanliness.get("violations", [])
    if violations:
        lines.append("")
        lines.append("VIOLATIONS:")
        lines.extend(f"  !! {v}" for v in violations)

    warnings_list = cleanliness.get("warnings", [])
    if warnings_list:
        lines.append("")
        lines.append("WARNINGS:")
        lines.extend(f"  ! {w}" for w in warnings_list[:10])
        if len(warnings_list) > 10:
            lines.append(f"  ... and {len(warnings_list) - 10} more")

    empty_files = cleanliness.get("empty_files", [])
    if empty_files:
        lines.append("")
        lines.append("EMPTY FILES:")
        lines.extend(f"  - {f}" for f in empty_files[:10])

    lines.append("")
    lines.append("=" * 60)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Convenience
# ---------------------------------------------------------------------------


def create_backtest_run(
    project_type: str = "",
    project_goal: str = "",
    phase: str = "",
    evidence_gate_mode: str = "warning",
    sandbox_root: str = "",
) -> str:
    """Create a complete backtest run directory with manifest.

    Returns the run directory path.
    """
    run_dir = create_sandbox_run_dir(root=sandbox_root)
    resolved_root = resolve_sandbox_root(sandbox_root)
    manifest: dict[str, object] = {
        "run_id": _make_run_id(),
        "phase": phase or "backtest",
        "project_type": project_type,
        "project_goal": project_goal,
        "operator": "SPC",
        "sandbox_mode": "host-native",
        "sandbox_root": resolved_root,
        "allowed_output_paths": [run_dir],
        "forbidden_paths": list(FORBIDDEN_PATH_PATTERNS),
        "expected_artifacts": [],
        "verification_commands": [],
        "evidence_gate_mode": evidence_gate_mode,
    }
    write_sandbox_manifest(run_dir, manifest)
    return run_dir


def cleanup_sandbox_run(run_dir: str, *, move_to_trash: bool = True) -> bool:
    """Remove or trash a sandbox run directory.

    Args:
        run_dir: Path to the run directory to clean up.
        move_to_trash: If True, moves to trash/ instead of deleting.

    Returns:
        True if the directory no longer exists.
    """
    if not os.path.isdir(run_dir):
        return True

    try:
        if move_to_trash:
            sandbox_root = resolve_sandbox_root()
            trash_dir = os.path.join(sandbox_root, "trash")
            os.makedirs(trash_dir, exist_ok=True)
            target = os.path.join(
                trash_dir, f"{os.path.basename(run_dir)}-{int(time.time())}"
            )
            shutil.move(run_dir, target)
        else:
            shutil.rmtree(run_dir)
    except OSError:
        return False

    return not os.path.isdir(run_dir)
