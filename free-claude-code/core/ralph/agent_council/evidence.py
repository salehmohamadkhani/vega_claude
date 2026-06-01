"""Agent Council V2 — Evidence Model.

Simple evidence utilities for Agent Council V2:
- Create evidence items
- Validate evidence has source/path/claim
- Attach evidence to agent decisions
- Summarize evidence counts by type
- Reject unsupported claims

This connects to QualityGate in later phases but does not deeply integrate yet.
"""

from __future__ import annotations

from collections import Counter

from .models import EvidenceItem, EvidenceType

# ---------------------------------------------------------------------------
# Validation errors
# ---------------------------------------------------------------------------


class EvidenceValidationError(ValueError):
    """Raised when evidence fails validation."""


# ---------------------------------------------------------------------------
# Evidence creation and validation
# ---------------------------------------------------------------------------


def create_evidence(
    source_path: str,
    claim: str,
    evidence_type: EvidenceType = EvidenceType.REPO_PATTERN,
    agent_source: str = "",
    notes: str = "",
    evidence_id: str = "",
) -> EvidenceItem:
    """Create a validated evidence item.

    Args:
        source_path: Path to source (repo, file, agent output).
        claim: The claim this evidence supports.
        evidence_type: Type of evidence.
        agent_source: Agent that produced this evidence.
        notes: Optional context notes.
        evidence_id: Optional unique ID (auto-generated with prefix if empty).

    Returns:
        A new EvidenceItem.

    Raises:
        EvidenceValidationError: If source_path or claim is empty.
    """
    if not source_path:
        raise EvidenceValidationError("source_path must not be empty")
    if not claim:
        raise EvidenceValidationError("claim must not be empty")

    eid = (
        evidence_id if evidence_id else f"ev-{hash((source_path, claim)) & 0xFFFF:04x}"
    )
    return EvidenceItem(
        evidence_id=eid,
        source_path=source_path,
        claim=claim,
        evidence_type=evidence_type,
        agent_source=agent_source,
        quality="unvalidated",
        notes=notes,
    )


def validate_evidence(item: EvidenceItem) -> list[str]:
    """Validate an evidence item. Returns list of error messages.

    Evidence is valid if it has a source_path, claim, and valid evidence_type.
    """
    errors: list[str] = []
    if not item.source_path:
        errors.append("source_path is empty")
    if not item.claim:
        errors.append("claim is empty")
    if not item.evidence_type or not item.evidence_type.value:
        errors.append("evidence_type is invalid")
    return errors


def reject_unsupported_claims(
    items: tuple[EvidenceItem, ...],
) -> tuple[EvidenceItem, ...]:
    """Filter out evidence items that fail basic validation.

    Returns only items that pass validate_evidence (no errors).
    """
    return tuple(item for item in items if not validate_evidence(item))


# ---------------------------------------------------------------------------
# Evidence collection
# ---------------------------------------------------------------------------


class EvidenceCollector:
    """Collects and summarizes evidence items for agent decisions."""

    def __init__(self) -> None:
        self._items: list[EvidenceItem] = []

    def add(self, item: EvidenceItem) -> None:
        """Add an evidence item to the collection.

        Raises EvidenceValidationError if the item is invalid.
        """
        errors = validate_evidence(item)
        if errors:
            raise EvidenceValidationError(f"Invalid evidence item: {', '.join(errors)}")
        self._items.append(item)

    def add_batch(self, items: tuple[EvidenceItem, ...]) -> None:
        """Add multiple evidence items. Invalid items are silently skipped."""
        for item in items:
            if not validate_evidence(item):
                self._items.append(item)

    def attach_to_decision(
        self,
        agent_id: str,
        items: tuple[EvidenceItem, ...],
    ) -> tuple[EvidenceItem, ...]:
        """Attach evidence items to an agent's decision context.

        Args:
            agent_id: The agent these items support.
            items: Evidence items to attach.

        Returns:
            Tuple of validated evidence items (invalid items filtered out).
        """
        valid = reject_unsupported_claims(items)
        for item in valid:
            self._items.append(item)
        return valid

    @property
    def items(self) -> tuple[EvidenceItem, ...]:
        """Return all collected evidence items."""
        return tuple(self._items)

    @property
    def count(self) -> int:
        """Total number of evidence items collected."""
        return len(self._items)

    def clear(self) -> None:
        """Remove all collected evidence."""
        self._items.clear()

    # -- Summaries -----------------------------------------------------------

    def summarize_by_type(self) -> dict[str, int]:
        """Return evidence counts grouped by type."""
        counter: Counter[str] = Counter()
        for item in self._items:
            counter[item.evidence_type.value] += 1
        return dict(counter)

    def summarize_by_agent(self) -> dict[str, int]:
        """Return evidence counts grouped by source agent."""
        counter: Counter[str] = Counter()
        for item in self._items:
            if item.agent_source:
                counter[item.agent_source] += 1
        return dict(counter)

    def summarize_by_quality(self) -> dict[str, int]:
        """Return evidence counts grouped by quality rating."""
        counter: Counter[str] = Counter()
        for item in self._items:
            counter[item.quality] += 1
        return dict(counter)

    def validate_all(self) -> int:
        """Mark all unvalidated items as validated. Returns count of items updated."""
        count = 0
        for i, item in enumerate(self._items):
            if item.quality == "unvalidated":
                self._items[i] = EvidenceItem(
                    evidence_id=item.evidence_id,
                    source_path=item.source_path,
                    claim=item.claim,
                    evidence_type=item.evidence_type,
                    agent_source=item.agent_source,
                    quality="validated",
                    notes=item.notes,
                )
                count += 1
        return count

    def reject_invalid(self) -> int:
        """Remove all rejected or invalid items. Returns count of items removed."""
        before = len(self._items)
        self._items = [
            item
            for item in self._items
            if not validate_evidence(item) and item.quality != "rejected"
        ]
        return before - len(self._items)
