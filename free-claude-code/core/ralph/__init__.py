"""FCC-native Ralph Runtime — core orchestration layer.

The Ralph Runtime provides task planning, run tracking, scoring,
verification planning, multi-agent roles, and loop guard logic
for iterative AI-assisted development workflows.

FCC owns provider routing, API keys, model config, Claude Code proxy,
CLI launcher, Admin UI, and messaging. The Ralph Runtime builds on top
of FCC without duplicating those concerns.
"""

from .arbiter import ArbiterAction, ArbiterDecision, ArbiterEngine
from .critic import CriticEngine, CriticReview
from .loop_guard import LoopAction, LoopGuard, LoopGuardDecision
from .model_router import ModelRoleResolution, ModelRoleRouter, ModelRoleRoutingPolicy
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
from .planner import ClarifyingQuestion, ProjectSpec, TaskPlan, TaskPlanner
from .quality_gate import QualityGate, QualityGateResult
from .roles import (
    AGENT_ROLE_LABELS,
    AGENT_TO_MODEL_ROLE,
    AgentRole,
    ModelRole,
)
from .run_table import RunTable, RunTableEntry
from .scoring import HallucinationRisk, ScoreCard
from .smoke_adapter import FCCSmokeAdapter, SmokePlan
from .verification import (
    VerificationPlan,
    VerificationResult,
    VerificationStatus,
    build_verification_plan_for_task,
)
from .verification_runner import (
    CommandExecutionResult,
    VerificationRunner,
    VerificationRunnerConfig,
)

__all__ = [
    "AGENT_ROLE_LABELS",
    "AGENT_TO_MODEL_ROLE",
    "AgentRole",
    "ArbiterAction",
    "ArbiterDecision",
    "ArbiterEngine",
    "ClarifyingQuestion",
    "CommandExecutionResult",
    "CriticDecision",
    "CriticEngine",
    "CriticReview",
    "FCCSmokeAdapter",
    "HallucinationRisk",
    "IterationStatus",
    "LoopAction",
    "LoopGuard",
    "LoopGuardDecision",
    "ModelRole",
    "ModelRoleResolution",
    "ModelRoleRouter",
    "ModelRoleRoutingPolicy",
    "ProjectGoal",
    "ProjectSpec",
    "QualityGate",
    "QualityGateResult",
    "RalphIteration",
    "RalphRun",
    "RalphTask",
    "RunStatus",
    "RunTable",
    "RunTableEntry",
    "ScoreCard",
    "SmokePlan",
    "TaskPlan",
    "TaskPlanner",
    "TaskStatus",
    "VerificationPlan",
    "VerificationResult",
    "VerificationRunner",
    "VerificationRunnerConfig",
    "VerificationStatus",
    "_new_id",
    "_now_utc",
    "build_verification_plan_for_task",
    "run_status_from_str",
    "task_status_from_str",
]
