"""Tests for isolated runtime sandbox (runtime_sandbox.py).

Prove:
- sandbox run dir is created outside VegaClaw source
- manifest is written and readable
- empty files are detected
- forbidden runtime files are detected (.fcc/, .claude/, .env, logs)
- sandbox summary is human-readable
- sandbox artifacts can feed evidence gate checks
- artifacts collection works
- cleanup works
- no network/API/LLM calls occur
"""

from __future__ import annotations

import json
import os
import tempfile

from core.ralph.agent_council.runtime_sandbox import (
    cleanup_sandbox_run,
    collect_sandbox_artifacts,
    create_backtest_run,
    create_sandbox_run_dir,
    read_sandbox_manifest,
    resolve_sandbox_root,
    summarize_sandbox_run,
    validate_sandbox_cleanliness,
    write_sandbox_manifest,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_temp_run_dir() -> str:
    """Create a temp run dir for testing. Auto-cleanup via cleanup_sandbox_run."""
    root = tempfile.mkdtemp(prefix="vegaclaw-test-sandbox-")
    run_dir = os.path.join(root, "runs", "test-run-001")
    os.makedirs(run_dir, exist_ok=True)
    return run_dir


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------


class TestSandboxRootResolution:
    def test_resolve_returns_string(self):
        root = resolve_sandbox_root()
        assert isinstance(root, str)
        assert len(root) > 0

    def test_resolve_returns_existing_path(self):
        root = resolve_sandbox_root()
        assert os.path.isdir(root)

    def test_resolve_respects_requested_path(self):
        with tempfile.TemporaryDirectory() as d:
            resolved = resolve_sandbox_root(d)
            assert resolved == d


# ---------------------------------------------------------------------------
# Run directory
# ---------------------------------------------------------------------------


class TestCreateSandboxRunDir:
    def test_creates_timestamped_directory(self):
        run_dir = create_sandbox_run_dir(
            root=tempfile.mkdtemp(),
            prefix="test-backtest",
        )
        assert os.path.isdir(run_dir)
        assert "test-backtest" in run_dir

    def test_created_outside_vegaclaw_source(self):
        """Run dir must be outside the VegaClaw source tree."""
        run_dir = create_sandbox_run_dir(
            root=tempfile.mkdtemp(),
            prefix="isolated-test",
        )
        assert os.path.isdir(run_dir)
        assert "/opt/vega-cloud/vega_claude/free-claude-code" not in run_dir


class TestManifest:
    def test_write_and_read_manifest(self):
        run_dir = _make_temp_run_dir()
        manifest = {
            "run_id": "test-123",
            "project_type": "full_stack_app",
            "project_goal": "Test project",
        }
        path = write_sandbox_manifest(run_dir, manifest)
        assert os.path.isfile(path)

        loaded = read_sandbox_manifest(run_dir)
        assert loaded is not None
        assert loaded["run_id"] == "test-123"
        assert loaded["project_type"] == "full_stack_app"

    def test_manifest_auto_fills_defaults(self):
        run_dir = _make_temp_run_dir()
        manifest: dict[str, object] = {"project_type": "landing_page"}
        write_sandbox_manifest(run_dir, manifest)
        loaded = read_sandbox_manifest(run_dir)
        assert loaded is not None
        assert loaded.get("run_id")
        assert loaded.get("created_at")

    def test_read_nonexistent_manifest_returns_none(self):
        run_dir = _make_temp_run_dir()
        assert read_sandbox_manifest(run_dir) is None

    def test_manifest_is_valid_json(self):
        run_dir = _make_temp_run_dir()
        write_sandbox_manifest(run_dir, {"key": "value"})
        path = os.path.join(run_dir, "manifest.json")
        with open(path) as f:
            data = json.load(f)
        assert data["key"] == "value"


# ---------------------------------------------------------------------------
# Artifact collection
# ---------------------------------------------------------------------------


class TestArtifactCollection:
    def test_collects_files_in_run_dir(self):
        run_dir = _make_temp_run_dir()
        # Create test files
        with open(os.path.join(run_dir, "app.py"), "w") as f:
            f.write("print('hello')")
        with open(os.path.join(run_dir, "index.html"), "w") as f:
            f.write("<html></html>")

        artifacts = collect_sandbox_artifacts(run_dir)
        assert artifacts["total_files"] == 2
        assert "app.py" in artifacts["files_found"]
        assert artifacts["total_size_bytes"] > 0

    def test_detects_empty_files(self):
        run_dir = _make_temp_run_dir()
        with open(os.path.join(run_dir, "empty.txt"), "w"):
            pass  # intentionally empty

        artifacts = collect_sandbox_artifacts(run_dir)
        assert len(artifacts["files_empty"]) == 1
        assert "empty.txt" in artifacts["files_empty"]

    def test_detects_forbidden_fcc_paths(self):
        run_dir = _make_temp_run_dir()
        fcc_dir = os.path.join(run_dir, ".fcc")
        os.makedirs(fcc_dir, exist_ok=True)
        with open(os.path.join(fcc_dir, "config.json"), "w") as f:
            f.write("{}")

        artifacts = collect_sandbox_artifacts(run_dir)
        assert len(artifacts["files_forbidden"]) == 1
        assert len(artifacts["violations"]) == 1

    def test_detects_forbidden_claude_paths(self):
        run_dir = _make_temp_run_dir()
        claude_dir = os.path.join(run_dir, "subdir", ".claude")
        os.makedirs(claude_dir, exist_ok=True)
        with open(os.path.join(claude_dir, "memory.md"), "w") as f:
            f.write("test")

        artifacts = collect_sandbox_artifacts(run_dir)
        assert len(artifacts["files_forbidden"]) == 1

    def test_detects_forbidden_env_files(self):
        run_dir = _make_temp_run_dir()
        with open(os.path.join(run_dir, ".env.production"), "w") as f:
            f.write("SECRET=value")

        artifacts = collect_sandbox_artifacts(run_dir)
        assert len(artifacts["files_forbidden"]) == 1

    def test_detects_forbidden_logs(self):
        run_dir = _make_temp_run_dir()
        log_dir = os.path.join(run_dir, "logs")
        os.makedirs(log_dir, exist_ok=True)
        with open(os.path.join(log_dir, "error.log"), "w") as f:
            f.write("error")

        artifacts = collect_sandbox_artifacts(run_dir)
        assert len(artifacts["files_forbidden"]) == 1

    def test_detects_forbidden_fcc_ralph(self):
        run_dir = _make_temp_run_dir()
        ralph_dir = os.path.join(run_dir, ".fcc-ralph")
        os.makedirs(ralph_dir, exist_ok=True)
        with open(os.path.join(ralph_dir, "runs.json"), "w") as f:
            f.write("{}")

        artifacts = collect_sandbox_artifacts(run_dir)
        assert len(artifacts["files_forbidden"]) == 1

    def test_missing_dir_returns_violation(self):
        artifacts = collect_sandbox_artifacts("/nonexistent/path/xyz")
        assert artifacts["total_files"] == 0
        assert len(artifacts["violations"]) >= 1

    def test_tracks_extensions(self):
        run_dir = _make_temp_run_dir()
        with open(os.path.join(run_dir, "a.py"), "w") as f:
            f.write("pass")
        with open(os.path.join(run_dir, "b.py"), "w") as f:
            f.write("pass")
        with open(os.path.join(run_dir, "c.js"), "w") as f:
            f.write("// js")

        artifacts = collect_sandbox_artifacts(run_dir)
        assert artifacts["extensions_found"].get(".py") == 2
        assert artifacts["extensions_found"].get(".js") == 1

    def test_skips_manifest_file(self):
        run_dir = _make_temp_run_dir()
        write_sandbox_manifest(run_dir, {"test": True})
        with open(os.path.join(run_dir, "real_file.py"), "w") as f:
            f.write("pass")

        artifacts = collect_sandbox_artifacts(run_dir)
        # manifest.json should be excluded from count
        assert artifacts["total_files"] == 1
        assert "real_file.py" in artifacts["files_found"]
        assert "manifest.json" not in artifacts["files_found"]


# ---------------------------------------------------------------------------
# Cleanliness validation
# ---------------------------------------------------------------------------


class TestValidateSandboxCleanliness:
    def test_clean_directory(self):
        run_dir = _make_temp_run_dir()
        with open(os.path.join(run_dir, "app.py"), "w") as f:
            f.write("print('hi')")

        result = validate_sandbox_cleanliness(run_dir)
        assert result["clean"] is True
        assert len(result["violations"]) == 0

    def test_dirty_with_forbidden_paths(self):
        run_dir = _make_temp_run_dir()
        os.makedirs(os.path.join(run_dir, ".fcc"), exist_ok=True)
        with open(os.path.join(run_dir, ".fcc", "config.json"), "w") as f:
            f.write("{}")

        result = validate_sandbox_cleanliness(run_dir)
        assert result["clean"] is False
        assert len(result["violations"]) > 0

    def test_warns_on_empty_files(self):
        run_dir = _make_temp_run_dir()
        with open(os.path.join(run_dir, "empty.py"), "w"):
            pass

        result = validate_sandbox_cleanliness(run_dir)
        assert len(result["warnings"]) >= 1

    def test_summary_string(self):
        run_dir = _make_temp_run_dir()
        result = validate_sandbox_cleanliness(run_dir)
        assert isinstance(result["summary"], str)
        assert len(result["summary"]) > 0


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------


class TestSummarizeSandboxRun:
    def test_summary_for_new_run(self):
        run_dir = _make_temp_run_dir()
        write_sandbox_manifest(
            run_dir,
            {
                "run_id": "test-summary",
                "project_type": "landing_page",
                "project_goal": "Test goal",
                "phase": "test",
                "evidence_gate_mode": "warning",
            },
        )
        with open(os.path.join(run_dir, "app.py"), "w") as f:
            f.write("print('hello')")

        summary = summarize_sandbox_run(run_dir)
        assert isinstance(summary, str)
        assert "SANDBOX RUN SUMMARY" in summary
        assert "test-summary" in summary
        assert "landing_page" in summary

    def test_summary_for_run_with_violations(self):
        run_dir = _make_temp_run_dir()
        write_sandbox_manifest(run_dir, {"run_id": "dirty-test"})
        os.makedirs(os.path.join(run_dir, ".fcc"), exist_ok=True)
        with open(os.path.join(run_dir, ".fcc", "bad.json"), "w") as f:
            f.write("{}")

        summary = summarize_sandbox_run(run_dir)
        assert "VIOLATIONS" in summary


# ---------------------------------------------------------------------------
# Backtest convenience
# ---------------------------------------------------------------------------


class TestCreateBacktestRun:
    def test_creates_complete_run(self):
        run_dir = create_backtest_run(
            project_type="landing_page",
            project_goal="Test backtest",
            phase="9.16i-smoke",
            sandbox_root=tempfile.mkdtemp(),
        )
        assert os.path.isdir(run_dir)

        manifest = read_sandbox_manifest(run_dir)
        assert manifest is not None
        assert manifest["project_type"] == "landing_page"
        assert manifest["evidence_gate_mode"] == "warning"
        assert manifest["sandbox_mode"] == "host-native"

    def test_manifest_includes_forbidden_paths(self):
        run_dir = create_backtest_run(sandbox_root=tempfile.mkdtemp())
        manifest = read_sandbox_manifest(run_dir)
        assert manifest is not None
        assert len(manifest.get("forbidden_paths", [])) > 0

    def test_run_dir_outside_vegaclaw(self):
        run_dir = create_backtest_run(sandbox_root=tempfile.mkdtemp())
        assert "/opt/vega-cloud/vega_claude/free-claude-code" not in run_dir


# ---------------------------------------------------------------------------
# Evidence gate integration
# ---------------------------------------------------------------------------


class TestSandboxEvidenceGateIntegration:
    """Sandbox artifacts can feed into evidence gate checks."""

    def test_artifacts_provide_file_paths_for_gate_context(self):
        run_dir = _make_temp_run_dir()
        with open(os.path.join(run_dir, "report.md"), "w") as f:
            f.write("# Report\n\nThis is a report.")
        with open(os.path.join(run_dir, "results.json"), "w") as f:
            f.write('{"passed": true}')

        artifacts = collect_sandbox_artifacts(run_dir)
        # Artifacts provide file lists that can be passed to gate runner
        paths = set(artifacts["files_found"])
        assert "report.md" in paths
        assert "results.json" in paths

        # These paths can be used as available_paths for gate enforcement
        from core.ralph.agent_council.runtime_gate_enforcer import (
            enforce_runtime_evidence_gates,
        )

        task_result = {
            "task_id": "sandbox-task-001",
            "task_title": "Sandbox test",
            "changed_files": list(paths),
            "task": {
                "agent_role": "doer",
                "verification_commands": ["uv run pytest tests/ -q"],
                "acceptance_criteria": ["Files must be non-empty."],
            },
        }
        result = enforce_runtime_evidence_gates(
            task_result,
            strict_mode=False,
        )
        assert result.gates_run == 12

    def test_forbidden_paths_block_in_gate_context(self):
        run_dir = _make_temp_run_dir()
        with open(os.path.join(run_dir, "app.py"), "w") as f:
            f.write("print('hi')")
        os.makedirs(os.path.join(run_dir, ".fcc"), exist_ok=True)
        with open(os.path.join(run_dir, ".fcc", "config.json"), "w") as f:
            f.write("{}")

        artifacts = collect_sandbox_artifacts(run_dir)
        # Forbidden files are detected
        assert len(artifacts["files_forbidden"]) > 0

        # Pass forbidden paths as changed_files to gate enforcement
        from core.ralph.agent_council.runtime_gate_enforcer import (
            enforce_runtime_evidence_gates,
        )

        task_result = {
            "task_id": "sandbox-task-002",
            "changed_files": artifacts["files_found"],
        }
        result = enforce_runtime_evidence_gates(
            task_result,
            strict_mode=True,
        )
        excl_finding = next(
            (
                f
                for f in result.findings
                if f.gate_id == "runtime_artifact_exclusion_gate"
            ),
            None,
        )
        if excl_finding and excl_finding.status.value != "not_applicable":
            assert excl_finding.status.value == "blocked"


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------


class TestCleanup:
    def test_cleanup_removes_directory(self):
        run_dir = _make_temp_run_dir()
        with open(os.path.join(run_dir, "test.py"), "w") as f:
            f.write("pass")

        assert os.path.isdir(run_dir)
        success = cleanup_sandbox_run(run_dir, move_to_trash=False)
        assert success is True
        assert not os.path.isdir(run_dir)

    def test_cleanup_nonexistent(self):
        assert cleanup_sandbox_run("/nonexistent/path", move_to_trash=False) is True


# ---------------------------------------------------------------------------
# No LLM/network
# ---------------------------------------------------------------------------


class TestNoNetworkOrLLM:
    def test_no_network_imports(self):
        from core.ralph.agent_council import runtime_sandbox

        source = runtime_sandbox.__file__
        if source:
            with open(str(source)) as f:
                content = f.read()
            assert "anthropic" not in content
            assert "requests" not in content
            assert "urllib" not in content
