"""Loop policy definitions for the CLI-driven Ralph loop.

Defines the policy that governs task iteration, retry, debug, escalation,
and approval behavior. Safe defaults ensure no unapproved or unintended
execution.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field


class LoopStopReason(enum.Enum):
    """Reason the Ralph loop stopped."""

    COMPLETED = "completed"
    APPROVAL_REQUIRED = "approval_required"
    MAX_TASKS_REACHED = "max_tasks_reached"
    MAX_ITERATIONS_REACHED = "max_iterations_reached"
    RETRY_REQUIRED = "retry_required"
    DEBUG_REQUIRED = "debug_required"
    ESCALATION_REQUIRED = "escalation_required"
    EXECUTION_FAILED = "execution_failed"
    VERIFICATION_FAILED = "verification_failed"
    QUALITY_GATE_FAILED = "quality_gate_failed"
    CANCELLED = "cancelled"
    ERROR = "error"


@dataclass
class LoopPolicy:
    """Policy governing the CLI-driven Ralph loop.

    Safe defaults:
    - Dry-run by default
    - Strict task order (Policy A)
    - Require approval for all tasks
    - No auto-approval
    - Stop on debug and escalate
    - Real execution requires explicit opt-in
    """

    max_tasks: int | None = None
    max_iterations_per_task: int = 3
    stop_on_debug: bool = True
    stop_on_escalate: bool = True
    stop_on_retry_required: bool = False
    require_approval: bool = True
    strict_task_order: bool = True
    dry_run: bool = True
    allow_real_execution: bool = False
    metadata: dict[str, object] = field(default_factory=dict)
