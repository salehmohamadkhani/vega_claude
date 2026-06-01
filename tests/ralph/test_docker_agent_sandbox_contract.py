"""U13-DOCKER-LITE — Contract tests for the Docker agent test sandbox.

Verifies:
- Dockerfile.test exists at project root
- scripts/run_agent_tests_in_docker.sh exists and is executable
- Shell script does not use --privileged
- Shell script does not mount /opt/vega-cloud/env
- Dockerfile does not copy .env files
- Report marker exists
"""

from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

DOCKERFILE = PROJECT_ROOT / "Dockerfile.test"
RUNNER_SCRIPT = PROJECT_ROOT / "scripts" / "run_agent_tests_in_docker.sh"
REPORT = PROJECT_ROOT / "docs" / "vega_cloud" / "U13_DOCKER_TEST_SANDBOX_REPORT.md"


# ---------------------------------------------------------------------------
# Existence checks
# ---------------------------------------------------------------------------


def test_dockerfile_exists() -> None:
    assert DOCKERFILE.is_file(), f"Missing: {DOCKERFILE}"


def test_runner_script_exists() -> None:
    assert RUNNER_SCRIPT.is_file(), f"Missing: {RUNNER_SCRIPT}"


def test_runner_script_is_executable() -> None:
    mode = RUNNER_SCRIPT.stat().st_mode
    assert mode & stat.S_IXUSR, f"{RUNNER_SCRIPT} is not executable"
    assert mode & stat.S_IXGRP, f"{RUNNER_SCRIPT} is not group-executable"


# ---------------------------------------------------------------------------
# Safety — no privileged mode
# ---------------------------------------------------------------------------


def test_script_no_privileged_flag() -> None:
    """Shell script must not contain --privileged."""
    content = RUNNER_SCRIPT.read_text()
    assert "--privileged" not in content, (
        "Runner script uses --privileged — forbidden by U13 isolation rules"
    )


def test_script_no_env_mount() -> None:
    """Shell script must not mount /opt/vega-cloud/env."""
    content = RUNNER_SCRIPT.read_text()
    assert "/opt/vega-cloud/env" not in content, (
        "Runner script mounts env files — forbidden by U13 isolation rules"
    )


def test_dockerfile_no_env_copy() -> None:
    """Dockerfile must not COPY or ADD .env (or .env.example)."""
    content = DOCKERFILE.read_text()
    lower = content.lower()
    assert ".env" not in lower, (
        "Dockerfile contains .env reference — forbidden by U13 isolation rules"
    )


# ---------------------------------------------------------------------------
# Report marker
# ---------------------------------------------------------------------------


def test_report_marker_exists() -> None:
    assert REPORT.is_file(), f"Missing: {REPORT}"
    content = REPORT.read_text()
    assert "U13_DOCKER_SANDBOX_READY" in content, (
        "Report is missing the final marker U13_DOCKER_SANDBOX_READY"
    )
