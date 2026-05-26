"""Persist resumable run state via checkpoints.

Checkpoints capture the state of a task within a run at a point in time,
enabling resume after interruption. Stored as JSON under
``.fcc-ralph/checkpoints/``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .models import RunStatus, TaskStatus, _new_id
from .scoring import ScoreCard
from .workspace import RalphWorkspace


class CheckpointError(Exception):
    """Base error for checkpoint operations."""


class CheckpointNotFoundError(CheckpointError):
    """Raised when a checkpoint is not found."""


@dataclass
class Checkpoint:
    """A single checkpoint capturing run/task state at a point in time."""

    id: str = field(default_factory=_new_id)
    run_id: str = ""
    task_id: str = ""
    iteration_number: int = 0
    run_status: str = "created"
    task_status: str = "pending"
    score: dict[str, float] = field(default_factory=dict)
    arbiter_action: str = ""
    next_action: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_run_state(
        cls,
        run_id: str,
        task_id: str,
        iteration_number: int = 0,
        run_status: RunStatus = RunStatus.CREATED,
        task_status: TaskStatus = TaskStatus.PENDING,
        score_card: ScoreCard | None = None,
        arbiter_action: str = "",
        next_action: str = "",
        **metadata: Any,
    ) -> Checkpoint:
        """Create a checkpoint from run/task state."""
        score_dict: dict[str, float] = {}
        if score_card is not None:
            score_dict = {
                "implementation_score": float(score_card.implementation_score),
                "test_score": float(score_card.test_score),
                "kpi_score": float(score_card.kpi_score),
                "risk_score": float(score_card.risk_score),
                "confidence_score": float(score_card.confidence_score),
                "final_weighted_score": score_card.final_weighted_score(),
            }
        return cls(
            run_id=run_id,
            task_id=task_id,
            iteration_number=iteration_number,
            run_status=run_status.value,
            task_status=task_status.value,
            score=score_dict,
            arbiter_action=arbiter_action,
            next_action=next_action,
            metadata=metadata,
        )


class CheckpointStore:
    """Persist and load checkpoints as JSON files.

    Uses ``RalphWorkspace`` for filesystem access. Checkpoints are stored
    as ``{checkpoint_id}.json`` under ``.fcc-ralph/checkpoints/``.
    """

    def __init__(self, workspace: RalphWorkspace | None = None) -> None:
        self._workspace = workspace or RalphWorkspace()
        self._checkpoints_dir = "checkpoints"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def save_checkpoint(self, checkpoint: Checkpoint) -> Path:
        """Save a checkpoint as JSON. Returns the file path."""
        data: dict[str, Any] = {
            "id": checkpoint.id,
            "run_id": checkpoint.run_id,
            "task_id": checkpoint.task_id,
            "iteration_number": checkpoint.iteration_number,
            "run_status": checkpoint.run_status,
            "task_status": checkpoint.task_status,
            "score": checkpoint.score,
            "arbiter_action": checkpoint.arbiter_action,
            "next_action": checkpoint.next_action,
            "created_at": checkpoint.created_at,
            "metadata": checkpoint.metadata,
        }
        relative = f"{self._checkpoints_dir}/{checkpoint.id}.json"
        return self._workspace.write_json(relative, data)

    def load_checkpoint(self, checkpoint_id: str) -> Checkpoint:
        """Load a checkpoint by ID. Raises CheckpointNotFoundError if missing."""
        relative = f"{self._checkpoints_dir}/{checkpoint_id}.json"
        try:
            data = self._workspace.read_json(relative)
        except FileNotFoundError as exc:
            raise CheckpointNotFoundError(
                f"Checkpoint not found: {checkpoint_id}"
            ) from exc

        return Checkpoint(
            id=data.get("id", checkpoint_id),
            run_id=data.get("run_id", ""),
            task_id=data.get("task_id", ""),
            iteration_number=data.get("iteration_number", 0),
            run_status=data.get("run_status", "created"),
            task_status=data.get("task_status", "pending"),
            score=data.get("score", {}),
            arbiter_action=data.get("arbiter_action", ""),
            next_action=data.get("next_action", ""),
            created_at=data.get("created_at", ""),
            metadata=data.get("metadata", {}),
        )

    def latest_for_run(self, run_id: str) -> Checkpoint | None:
        """Return the latest checkpoint for a run (by iteration number, then created_at)."""
        checkpoints = self.list_for_run(run_id)
        if not checkpoints:
            return None

        # Sort: highest iteration first, then latest created_at
        checkpoints.sort(
            key=lambda c: (c.iteration_number, c.created_at or ""), reverse=True
        )
        return checkpoints[0]

    def list_for_run(self, run_id: str) -> list[Checkpoint]:
        """Return all checkpoints for a run, sorted by iteration then created_at."""
        paths = self._workspace.list_paths(f"{self._checkpoints_dir}/*.json")
        result: list[Checkpoint] = []
        for p in paths:
            try:
                cp = self.load_checkpoint(p.stem)
                if cp.run_id == run_id:
                    result.append(cp)
            except CheckpointNotFoundError:
                continue
        result.sort(
            key=lambda c: (c.iteration_number, c.created_at or ""), reverse=True
        )
        return result

    def delete_checkpoint(self, checkpoint_id: str) -> bool:
        """Delete a checkpoint by ID. Returns True if deleted."""
        relative = f"{self._checkpoints_dir}/{checkpoint_id}.json"
        return self._workspace.delete_path(relative)
