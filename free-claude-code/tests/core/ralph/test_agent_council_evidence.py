"""Tests for Agent Council V2 evidence model."""

from __future__ import annotations

import pytest

from core.ralph.agent_council.evidence import (
    EvidenceCollector,
    EvidenceValidationError,
    create_evidence,
    reject_unsupported_claims,
    validate_evidence,
)
from core.ralph.agent_council.models import EvidenceItem, EvidenceType


class TestCreateEvidence:
    def test_creates_valid_item(self):
        item = create_evidence(
            source_path="/test/path",
            claim="This is a claim",
            evidence_type=EvidenceType.REPO_PATTERN,
            agent_source="test_agent",
        )
        assert item.source_path == "/test/path"
        assert item.claim == "This is a claim"
        assert item.evidence_type == EvidenceType.REPO_PATTERN
        assert item.agent_source == "test_agent"
        assert item.quality == "unvalidated"
        assert item.is_valid()

    def test_empty_source_raises(self):
        with pytest.raises(EvidenceValidationError, match="source_path"):
            create_evidence(source_path="", claim="claim")

    def test_empty_claim_raises(self):
        with pytest.raises(EvidenceValidationError, match="claim"):
            create_evidence(source_path="src", claim="")

    def test_auto_generated_evidence_id(self):
        item = create_evidence(source_path="/src", claim="test")
        assert item.evidence_id.startswith("ev-")

    def test_custom_evidence_id(self):
        item = create_evidence(
            source_path="/src",
            claim="test",
            evidence_id="custom-001",
        )
        assert item.evidence_id == "custom-001"

    def test_default_evidence_type(self):
        item = create_evidence(source_path="/src", claim="test")
        assert item.evidence_type == EvidenceType.REPO_PATTERN


class TestValidateEvidence:
    def test_valid_passes(self):
        item = EvidenceItem(
            source_path="s", claim="c", evidence_type=EvidenceType.REPO_PATTERN
        )
        assert validate_evidence(item) == []

    def test_empty_source_fails(self):
        item = EvidenceItem(source_path="", claim="c")
        errors = validate_evidence(item)
        assert len(errors) >= 1
        assert any("source_path" in e for e in errors)

    def test_empty_claim_fails(self):
        item = EvidenceItem(source_path="s", claim="")
        errors = validate_evidence(item)
        assert len(errors) >= 1
        assert any("claim" in e for e in errors)


class TestRejectUnsupportedClaims:
    def test_keeps_valid_items(self):
        items = (
            EvidenceItem(
                source_path="s1", claim="c1", evidence_type=EvidenceType.REPO_PATTERN
            ),
            EvidenceItem(
                source_path="s2", claim="c2", evidence_type=EvidenceType.TEST_RESULT
            ),
        )
        result = reject_unsupported_claims(items)
        assert len(result) == 2

    def test_rejects_invalid_items(self):
        items = (
            EvidenceItem(
                source_path="", claim="c1", evidence_type=EvidenceType.REPO_PATTERN
            ),
            EvidenceItem(
                source_path="s2", claim="", evidence_type=EvidenceType.TEST_RESULT
            ),
            EvidenceItem(
                source_path="s3", claim="c3", evidence_type=EvidenceType.REPO_PATTERN
            ),
        )
        result = reject_unsupported_claims(items)
        assert len(result) == 1
        assert result[0].source_path == "s3"


class TestEvidenceCollector:
    @pytest.fixture
    def collector(self):
        return EvidenceCollector()

    def test_empty_collector(self, collector):
        assert collector.count == 0
        assert collector.items == ()

    def test_add_valid_item(self, collector):
        item = EvidenceItem(
            source_path="/src",
            claim="test",
            evidence_type=EvidenceType.REPO_PATTERN,
        )
        collector.add(item)
        assert collector.count == 1

    def test_add_invalid_item_raises(self, collector):
        item = EvidenceItem(source_path="", claim="test")
        with pytest.raises(EvidenceValidationError):
            collector.add(item)

    def test_add_batch_skips_invalid(self, collector):
        items = (
            EvidenceItem(
                source_path="s1", claim="c1", evidence_type=EvidenceType.REPO_PATTERN
            ),
            EvidenceItem(source_path="", claim="c2"),  # invalid, skipped
            EvidenceItem(
                source_path="s3", claim="c3", evidence_type=EvidenceType.TEST_RESULT
            ),
        )
        collector.add_batch(items)
        assert collector.count == 2  # invalid items (empty source) are filtered out

    def test_attach_to_decision(self, collector):
        items = (
            EvidenceItem(
                source_path="s1", claim="c1", evidence_type=EvidenceType.REPO_PATTERN
            ),
            EvidenceItem(source_path="", claim="c2"),  # invalid, filtered out
        )
        valid = collector.attach_to_decision("test_agent", items)
        assert len(valid) == 1
        assert valid[0].source_path == "s1"
        # Also added to collector
        assert collector.count == 1

    def test_clear(self, collector):
        collector.add(
            EvidenceItem(
                source_path="/src",
                claim="test",
                evidence_type=EvidenceType.REPO_PATTERN,
            )
        )
        assert collector.count == 1
        collector.clear()
        assert collector.count == 0

    def test_summarize_by_type(self, collector):
        collector.add(
            EvidenceItem(
                source_path="s1",
                claim="c1",
                evidence_type=EvidenceType.REPO_PATTERN,
            )
        )
        collector.add(
            EvidenceItem(
                source_path="s2",
                claim="c2",
                evidence_type=EvidenceType.TEST_RESULT,
            )
        )
        summary = collector.summarize_by_type()
        assert summary["repo_pattern"] == 1
        assert summary["test_result"] == 1

    def test_summarize_by_agent(self, collector):
        collector.add(
            EvidenceItem(
                source_path="s1",
                claim="c1",
                agent_source="agent_a",
                evidence_type=EvidenceType.REPO_PATTERN,
            )
        )
        collector.add(
            EvidenceItem(
                source_path="s2",
                claim="c2",
                agent_source="agent_a",
                evidence_type=EvidenceType.REPO_PATTERN,
            )
        )
        collector.add(
            EvidenceItem(
                source_path="s3",
                claim="c3",
                agent_source="agent_b",
                evidence_type=EvidenceType.REPO_PATTERN,
            )
        )
        summary = collector.summarize_by_agent()
        assert summary["agent_a"] == 2
        assert summary["agent_b"] == 1

    def test_summarize_by_quality(self, collector):
        collector.add(
            EvidenceItem(
                source_path="s1",
                claim="c1",
                evidence_type=EvidenceType.REPO_PATTERN,
            )
        )
        summary = collector.summarize_by_quality()
        assert summary["unvalidated"] == 1

    def test_validate_all(self, collector):
        collector.add(
            EvidenceItem(
                source_path="s1",
                claim="c1",
                evidence_type=EvidenceType.REPO_PATTERN,
            )
        )
        assert collector.validate_all() == 1
        summary = collector.summarize_by_quality()
        assert summary.get("validated", 0) == 1
        assert summary.get("unvalidated", 0) == 0

    def test_reject_invalid(self, collector):
        collector.add(
            EvidenceItem(
                source_path="s1",
                claim="c1",
                evidence_type=EvidenceType.REPO_PATTERN,
            )
        )
        # We can't add invalid items (they raise), so reject should be 0
        removed = collector.reject_invalid()
        assert removed == 0
        assert collector.count == 1
