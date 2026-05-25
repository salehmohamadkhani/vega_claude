"""FCC-native Ralph Runtime — core orchestration layer.

The Ralph Runtime provides task planning, run tracking, scoring,
verification planning, multi-agent roles, and loop guard logic
for iterative AI-assisted development workflows.

FCC owns provider routing, API keys, model config, Claude Code proxy,
CLI launcher, Admin UI, and messaging. The Ralph Runtime builds on top
of FCC without duplicating those concerns.
"""

from .loop_guard import LoopAction, LoopGuard, LoopGuardDecision
from .models import (
    CriticDecision,
    IterationStatus,
    ProjectGoal,
    RalphIteration,
    RalphRun,
    RalphTask,
    RunStatus,
    TaskStatus,
    _new_id,
    _now_utc,
    run_status_from_str,
    task_status_from_str,
)
from .roles import (
    AGENT_ROLE_LABELS,
    AGENT_TO_MODEL_ROLE,
    AgentRole,
    ModelRole,
)
from .run_table import RunTable, RunTableEntry
from .scoring import HallucinationRisk, ScoreCard
from .verification import (
    VerificationPlan,
    VerificationResult,
    VerificationStatus,
    build_verification_plan_for_task,
)

__all__ = [
    "AGENT_ROLE_LABELS",
    "AGENT_TO_MODEL_ROLE",
    "AgentRole",
    "CriticDecision",
    "HallucinationRisk",
    "IterationStatus",
    "LoopAction",
    "LoopGuard",
    "LoopGuardDecision",
    "ModelRole",
    "ProjectGoal",
    "RalphIteration",
    "RalphRun",
    "RalphTask",
    "RunStatus",
    "RunTable",
    "RunTableEntry",
    "ScoreCard",
    "TaskStatus",
    "VerificationPlan",
    "VerificationResult",
    "VerificationStatus",
    "_new_id",
    "_now_utc",
    "build_verification_plan_for_task",
    "run_status_from_str",
    "task_status_from_str",
]
