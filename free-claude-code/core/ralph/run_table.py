"""Run table — tracks all task-level entries for a Ralph run.

Phase 1 is purely in-memory. No filesystem persistence.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .models import TaskStatus
from .roles import AgentRole
from .scoring import ScoreCard
from .verification import VerificationStatus


@dataclass
class RunTableEntry:
    """A single entry in the run table, representing one task's lifecycle."""

    run_id: str
    task_id: str
    task_title: str = ""
    agent_role: AgentRole = AgentRole.DOER
    model_role: str = ""  # resolved model role label
    status: TaskStatus = TaskStatus.PENDING
    iteration_number: int = 0
    score: ScoreCard | None = None
    verification_status: VerificationStatus = VerificationStatus.NOT_RUN
    critic_approved: bool = False
    last_error: str = ""
    next_action: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable dict representation."""
        base: dict[str, Any] = {
            "run_id": self.run_id,
            "task_id": self.task_id,
            "task_title": self.task_title,
            "agent_role": self.agent_role.value,
            "model_role": self.model_role,
            "status": self.status.value,
            "iteration_number": self.iteration_number,
            "verification_status": self.verification_status.value,
            "critic_approved": self.critic_approved,
            "last_error": self.last_error,
            "next_action": self.next_action,
        }
        if self.score is not None:
            base["score"] = {
                "implementation_score": self.score.implementation_score,
                "test_score": self.score.test_score,
                "kpi_score": self.score.kpi_score,
                "risk_score": self.score.risk_score,
                "confidence_score": self.score.confidence_score,
                "hallucination_risk": self.score.hallucination_risk.value,
                "final_weighted_score": self.score.final_weighted_score(),
                "is_passing": self.score.is_passing(),
            }
        return base


class RunTable:
    """In-memory table of run entries.

    Provides operations for tracking task lifecycle during a Ralph run.
    """

    def __init__(self) -> None:
        self._entries: dict[str, RunTableEntry] = {}  # task_id → entry
        self._run_entries: dict[str, list[str]] = {}  # run_id → [task_id, ...]

    # ---- Mutation ----

    def add_entry(self, entry: RunTableEntry) -> None:
        """Add or update an entry in the table.

        If an entry with the same task_id already exists, it is replaced
        (updated). The task_id is not duplicated in the run's entry list.
        """
        self._entries[entry.task_id] = entry
        self._run_entries.setdefault(entry.run_id, [])
        if entry.task_id not in self._run_entries[entry.run_id]:
            self._run_entries[entry.run_id].append(entry.task_id)

    def update_status(self, task_id: str, new_status: TaskStatus) -> bool:
        """Update the status of an entry by task_id.

        Returns True if the task was found and updated, False otherwise.
        """
        entry = self._entries.get(task_id)
        if entry is None:
            return False
        entry.status = new_status
        return True

    def update_score(self, task_id: str, score: ScoreCard) -> bool:
        """Attach a score card to an entry."""
        entry = self._entries.get(task_id)
        if entry is None:
            return False
        entry.score = score
        return True

    def record_error(self, task_id: str, error: str) -> bool:
        """Record an error message for an entry."""
        entry = self._entries.get(task_id)
        if entry is None:
            return False
        entry.last_error = error
        return True

    # ---- Queries ----

    def get_entry(self, task_id: str) -> RunTableEntry | None:
        """Get a single entry by task_id."""
        return self._entries.get(task_id)

    def get_entries_for_run(self, run_id: str) -> list[RunTableEntry]:
        """Get all entries for a run, in insertion order."""
        task_ids = self._run_entries.get(run_id, [])
        return [self._entries[tid] for tid in task_ids if tid in self._entries]

    def list_active_entries(self) -> list[RunTableEntry]:
        """Return entries whose status is PENDING, APPROVED, RUNNING, or NEEDS_FIX."""
        active_statuses = {
            TaskStatus.PENDING,
            TaskStatus.APPROVED,
            TaskStatus.RUNNING,
            TaskStatus.VERIFYING,
            TaskStatus.NEEDS_FIX,
        }
        return [e for e in self._entries.values() if e.status in active_statuses]

    def list_failed_entries(self) -> list[RunTableEntry]:
        """Return entries whose status is FAILED or BLOCKED."""
        failed_statuses = {TaskStatus.FAILED, TaskStatus.BLOCKED}
        return [e for e in self._entries.values() if e.status in failed_statuses]

    def completion_percentage(self, run_id: str) -> float:
        """Calculate the percentage of completed tasks for a run.

        Returns 0.0 if no tasks exist for the run.
        """
        entries = self.get_entries_for_run(run_id)
        if not entries:
            return 0.0
        done = sum(1 for e in entries if e.status == TaskStatus.PASSED)
        return (done / len(entries)) * 100.0

    def serializable(self) -> list[dict[str, Any]]:
        """Return the full table as a list of serialisable dicts."""
        return [entry.to_dict() for entry in self._entries.values()]

    def clear(self) -> None:
        """Remove all entries (for testing or reset)."""
        self._entries.clear()
        self._run_entries.clear()

    @property
    def entry_count(self) -> int:
        return len(self._entries)
