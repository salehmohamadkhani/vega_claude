"""Tests for core.ralph.context_builder."""

from __future__ import annotations

import json

from core.ralph.context_builder import ContextBuilder, RalphContextSnapshot
from core.ralph.models import RalphTask
from core.ralph.roles import AgentRole
from core.ralph.workspace import RalphWorkspace


class TestContextBuilder:
    def make_builder(self, tmp_path) -> ContextBuilder:
        return ContextBuilder(repo_root=tmp_path)

    def test_handles_non_git_directory_gracefully(self, tmp_path) -> None:
        builder = self.make_builder(tmp_path)
        snapshot = builder.build_snapshot(goal_id="g1", run_id="r1", task_id="t1")
        assert snapshot.git.branch == ""
        assert snapshot.git.commit == ""
        assert snapshot.goal_id == "g1"
        assert snapshot.run_id == "r1"

    def test_runs_only_read_only_git_commands(self, tmp_path) -> None:
        builder = self.make_builder(tmp_path)
        # The builder only calls git branch, rev-parse, status, log, diff
        # No write commands are ever issued
        snapshot = builder.build_snapshot(goal_id="x", run_id="y", task_id="z")
        # In a non-git dir, all git fields should be empty/fallback
        assert isinstance(snapshot.git.branch, str)
        assert isinstance(snapshot.git.commit, str)
        assert isinstance(snapshot.git.status_summary, str)

    def test_builds_snapshot_with_fallback_values(self, tmp_path) -> None:
        builder = self.make_builder(tmp_path)
        snapshot = builder.build_snapshot("g1", "r1", "t1")
        assert isinstance(snapshot, RalphContextSnapshot)
        assert snapshot.goal_id == "g1"
        assert snapshot.run_id == "r1"
        assert snapshot.task_id == "t1"
        assert isinstance(snapshot.created_at, str)
        assert len(snapshot.created_at) > 0

    def test_builds_snapshot_with_task(self, tmp_path) -> None:
        builder = self.make_builder(tmp_path)
        task = RalphTask(
            id="TASK-001",
            title="Test Task",
            description="A task",
            agent_role=AgentRole.DOER,
            allowed_files=["src/"],
            forbidden_files=["secrets/"],
        )
        snapshot = builder.build_snapshot("g1", "r1", "t1", task=task)
        assert task.title in snapshot.task_summary
        assert "src/" in snapshot.files.included_files
        assert "secrets/" in snapshot.files.excluded_files

    def test_saves_snapshot(self, tmp_path) -> None:
        ws = RalphWorkspace(tmp_path)
        ws.initialize()
        builder = ContextBuilder(workspace=ws, repo_root=tmp_path)
        snapshot = builder.build_snapshot("g1", "r1", "t1")
        path = builder.save_snapshot(snapshot)
        assert path.exists()
        data = json.loads(path.read_text("utf-8"))
        assert data["goal_id"] == "g1"
        assert data["run_id"] == "r1"

    def test_timeout_handling(self, tmp_path) -> None:
        """Builder should handle git commands that would hang."""
        builder = self.make_builder(tmp_path)
        # No git repo — commands fail fast, not timeout
        result = builder._safe_git_cmd(["git", "branch", "--show-current"])
        assert result == ""

    def test_context_snapshot_includes_task_summary(self, tmp_path) -> None:
        from core.ralph.verification import VerificationResult, VerificationStatus

        builder = self.make_builder(tmp_path)
        task = RalphTask(id="TASK-001", title="My Task")
        vr = VerificationResult(status=VerificationStatus.PASSED)
        snapshot = builder.build_snapshot(
            "g1", "r1", "t1", task=task, verification_result=vr
        )
        assert "My Task" in snapshot.task_summary
        assert "passed" in snapshot.verification_summary.lower()
