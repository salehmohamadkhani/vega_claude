"""Domain models for the FCC-native Ralph Runtime.

All models are deterministic dataclasses (not Pydantic) to match FCC
``core/`` conventions and avoid coupling the runtime layer to schema
validation concerns.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import UTC, datetime

from .roles import AgentRole

# ---------------------------------------------------------------------------
# Status enums
# ---------------------------------------------------------------------------


class TaskStatus(enum.Enum):
    """Status of a single task within a run."""

    PENDING = "pending"
    APPROVED = "approved"
    RUNNING = "running"
    VERIFYING = "verifying"
    NEEDS_FIX = "needs_fix"
    PASSED = "passed"
    FAILED = "failed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"


class RunStatus(enum.Enum):
    """Status of an entire Ralph run (a goal composed of multiple tasks)."""

    CREATED = "created"
    PLANNING = "planning"
    WAITING_FOR_APPROVAL = "waiting_for_approval"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class IterationStatus(enum.Enum):
    """Status of a single iteration within a task."""

    STARTED = "started"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def _now_utc() -> datetime:
    """Return the current UTC datetime (naive for serialisability)."""
    return datetime.now(UTC).replace(tzinfo=None)


def _new_id() -> str:
    """Return a short hex identifier (deterministic-enough for in-memory use)."""
    import uuid

    return uuid.uuid4().hex[:12]


# ---------------------------------------------------------------------------
# Core domain models
# ---------------------------------------------------------------------------


@dataclass
class ProjectGoal:
    """A high-level goal that a Ralph run aims to accomplish."""

    id: str = field(default_factory=_new_id)
    title: str = ""
    description: str = ""
    created_at: datetime = field(default_factory=_now_utc)
    constraints: list[str] = field(default_factory=list)
    success_kpis: list[str] = field(default_factory=list)


@dataclass
class RalphTask:
    """A single task within a Ralph run.

    Each task is assigned to an AgentRole and carries its own acceptance
    criteria, verification commands, and KPI targets.
    """

    id: str = field(default_factory=_new_id)
    title: str = ""
    description: str = ""
    status: TaskStatus = TaskStatus.PENDING
    agent_role: AgentRole = AgentRole.DOER
    allowed_files: list[str] = field(default_factory=list)
    forbidden_files: list[str] = field(default_factory=list)
    acceptance_criteria: list[str] = field(default_factory=list)
    verification_commands: list[str] = field(default_factory=list)
    smoke_targets: list[str] = field(default_factory=list)
    kpis: list[str] = field(default_factory=list)
    max_iterations: int = 10

    def __post_init__(self) -> None:
        if self.max_iterations < 1:
            raise ValueError("max_iterations must be >= 1")


@dataclass
class RalphIteration:
    """A single attempt at completing a task."""

    id: str = field(default_factory=_new_id)
    run_id: str = ""
    task_id: str = ""
    iteration_number: int = 0
    agent_role: AgentRole = AgentRole.DOER
    status: IterationStatus = IterationStatus.STARTED
    summary: str = ""
    started_at: datetime = field(default_factory=_now_utc)
    finished_at: datetime | None = None


@dataclass
class RalphRun:
    """A complete run composed of multiple tasks toward a goal."""

    id: str = field(default_factory=_new_id)
    goal_id: str = ""
    status: RunStatus = RunStatus.CREATED
    tasks: list[RalphTask] = field(default_factory=list)
    current_task_id: str | None = None
    created_at: datetime = field(default_factory=_now_utc)
    updated_at: datetime = field(default_factory=_now_utc)

    def __post_init__(self) -> None:
        if self.current_task_id is None and self.tasks:
            self.current_task_id = self.tasks[0].id

    def current_task(self) -> RalphTask | None:
        """Return the task currently being worked on, if any."""
        if not self.current_task_id:
            return None
        for task in self.tasks:
            if task.id == self.current_task_id:
                return task
        return None

    def add_task(self, task: RalphTask) -> None:
        """Append a task to the run."""
        self.tasks.append(task)
        if self.current_task_id is None:
            self.current_task_id = task.id
        self.updated_at = _now_utc()

    def advance_to_next_task(self) -> RalphTask | None:
        """Move current_task_id to the next pending task.

        Returns the next task, or None if all tasks are done.
        """
        if not self.tasks:
            return None
        # Find index of current task
        current_idx: int | None = None
        for i, t in enumerate(self.tasks):
            if t.id == self.current_task_id:
                current_idx = i
                break

        next_idx = (current_idx + 1) if current_idx is not None else 0
        if next_idx >= len(self.tasks):
            self.current_task_id = None
            self._update_status_from_tasks()
            return None

        task = self.tasks[next_idx]
        self.current_task_id = task.id
        self.updated_at = _now_utc()
        return task

    def _update_status_from_tasks(self) -> None:
        """Recompute run status based on all task statuses."""
        if not self.tasks:
            self.status = RunStatus.CREATED
            return
        all_passed = all(t.status == TaskStatus.PASSED for t in self.tasks)
        any_failed = any(
            t.status in (TaskStatus.FAILED, TaskStatus.CANCELLED) for t in self.tasks
        )
        any_blocked = any(t.status == TaskStatus.BLOCKED for t in self.tasks)

        if all_passed:
            self.status = RunStatus.COMPLETED
        elif any_failed:
            self.status = RunStatus.FAILED
        elif any_blocked:
            self.status = RunStatus.PAUSED


@dataclass
class CriticDecision:
    """A critic's evaluation of task output."""

    approved: bool = False
    reason: str = ""
    required_fixes: list[str] = field(default_factory=list)
    confidence: float = 0.0  # 0.0 — 1.0

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------


def task_status_from_str(value: str) -> TaskStatus:
    """Parse a TaskStatus from its string value. Case-insensitive."""
    for member in TaskStatus:
        if member.value == value.lower():
            return member
    raise ValueError(f"Unknown TaskStatus: {value!r}")


def run_status_from_str(value: str) -> RunStatus:
    """Parse a RunStatus from its string value. Case-insensitive."""
    for member in RunStatus:
        if member.value == value.lower():
            return member
    raise ValueError(f"Unknown RunStatus: {value!r}")
