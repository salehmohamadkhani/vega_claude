"""Tests for Agent Council V2 research map."""

from __future__ import annotations

import os
import tempfile

import pytest

from core.ralph.agent_council.research_map import ResearchMap


class TestResearchMapAvailability:
    def test_default_research_root_available(self):
        rm = ResearchMap()
        assert rm.is_available is True
        assert os.path.isdir(rm.indexes_dir)

    def test_missing_root_unavailable(self):
        rm = ResearchMap(research_root="/nonexistent/path/xyz")
        assert rm.is_available is False


class TestResearchMapLoading:
    def test_loads_without_error(self):
        rm = ResearchMap()
        rm.load()
        assert rm._loaded is True

    def test_load_is_idempotent(self):
        rm = ResearchMap()
        rm.load()
        rm.load()  # second call should not fail
        assert rm._loaded is True

    def test_load_with_missing_root_no_error(self):
        rm = ResearchMap(research_root="/nonexistent/path")
        rm.load()  # should not raise
        assert rm._loaded is True


class TestResearchMapQueries:
    @pytest.fixture
    def rm(self):
        return ResearchMap()

    def test_find_for_agent(self, rm):
        refs = rm.find_for_agent("security_engineer")
        # security_engineer should have repos after Phase 9.15D
        assert isinstance(refs, tuple)
        # If the index is parseable, we expect some refs

    def test_find_for_missing_agent(self, rm):
        refs = rm.find_for_agent("nonexistent_agent_xyz")
        assert refs == ()

    def test_find_for_layer(self, rm):
        refs = rm.find_for_layer(12)
        assert isinstance(refs, tuple)

    def test_find_patterns(self, rm):
        patterns = rm.find_patterns("scan")
        assert isinstance(patterns, tuple)

    def test_find_patterns_no_match(self, rm):
        patterns = rm.find_patterns("xyznonexistentpattern999")
        assert patterns == ()

    def test_list_patterns_returns_tuple(self, rm):
        patterns = rm.list_patterns()
        assert isinstance(patterns, tuple)

    def test_summary_returns_dict(self, rm):
        summary = rm.summary()
        assert isinstance(summary, dict)
        assert "research_root_available" in summary
        assert summary["research_root_available"] is True

    def test_repo_count_for_agent(self, rm):
        count = rm.repo_count_for_agent("nonexistent_agent")
        assert count == 0


class TestResearchMapWithTempIndexes:
    def test_handles_malformed_markdown(self):
        """Create temp indexes with malformed content, ensure no crash."""
        with tempfile.TemporaryDirectory() as tmpdir:
            indexes = os.path.join(tmpdir, "indexes")
            os.makedirs(indexes, exist_ok=True)

            # Write a malformed agent index
            with open(os.path.join(indexes, "AGENT_TO_REPO_INDEX.md"), "w") as f:
                f.write(
                    "# Agent to Repo\n\n| `security_engineer` | Trivy, E2B, Semgrep |\n"
                )
                f.write("This is not a valid row|\n")
                f.write("---\n")

            # Write a malformed pattern index
            with open(os.path.join(indexes, "PATTERN_INDEX.md"), "w") as f:
                f.write("# Patterns\n\n| Scanner matrix | Trivy |\n")
                f.write("| Pattern-as-code | Semgrep |\n")

            rm = ResearchMap(research_root=tmpdir)
            rm.load()

            # Should not crash
            refs = rm.find_for_agent("security_engineer")
            assert isinstance(refs, tuple)

    def test_empty_indexes_no_crash(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            indexes = os.path.join(tmpdir, "indexes")
            os.makedirs(indexes, exist_ok=True)

            # Empty files
            open(os.path.join(indexes, "AGENT_TO_REPO_INDEX.md"), "w").close()
            open(os.path.join(indexes, "PATTERN_INDEX.md"), "w").close()

            rm = ResearchMap(research_root=tmpdir)
            rm.load()

            assert rm.summary()["agents_with_repos"] == 0
