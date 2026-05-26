"""FCC-native Ralph Runtime — core orchestration layer.

The Ralph Runtime provides task planning, run tracking, scoring,
verification planning, multi-agent roles, and loop guard logic
for iterative AI-assisted development workflows.

FCC owns provider routing, API keys, model config, Claude Code proxy,
CLI launcher, Admin UI, and messaging. The Ralph Runtime builds on top
of FCC without duplicating those concerns.
"""

from .agent_profiles import AgentProfile, AgentProfileRegistry
from .arbiter import ArbiterAction, ArbiterDecision, ArbiterEngine
from .checkpoint import Checkpoint, CheckpointStore
from .context_builder import ContextBuilder, GitContext, RalphContextSnapshot
from .critic import CriticEngine, CriticReview
from .loop_guard import LoopAction, LoopGuard, LoopGuardDecision
from .memory import MemoryRecord, MemoryStore
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
from .run_lifecycle import RunLifecycle, RunLifecycleResult
from .run_table import RunTable, RunTableEntry
from .scoring import HallucinationRisk, ScoreCard
from .smoke_adapter import FCCSmokeAdapter, SmokePlan
from .task_groups import TaskGroup, TaskGroupStore
from .task_library import TaskLibrary, TaskLibraryEntry, TaskLibraryError
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
from .workspace import (
    PathTraversalError,
    RalphWorkspace,
    RalphWorkspacePaths,
)

__all__ = [
    "AGENT_ROLE_LABELS",
    "AGENT_TO_MODEL_ROLE",
    "AgentProfile",
    "AgentProfileRegistry",
    "AgentRole",
    "ArbiterAction",
    "ArbiterDecision",
    "ArbiterEngine",
    "Checkpoint",
    "CheckpointStore",
    "ClarifyingQuestion",
    "CommandExecutionResult",
    "ContextBuilder",
    "CriticDecision",
    "CriticEngine",
    "CriticReview",
    "FCCSmokeAdapter",
    "GitContext",
    "HallucinationRisk",
    "IterationStatus",
    "LoopAction",
    "LoopGuard",
    "LoopGuardDecision",
    "MemoryRecord",
    "MemoryStore",
    "ModelRole",
    "ModelRoleResolution",
    "ModelRoleRouter",
    "ModelRoleRoutingPolicy",
    "PathTraversalError",
    "ProjectGoal",
    "ProjectSpec",
    "QualityGate",
    "QualityGateResult",
    "RalphContextSnapshot",
    "RalphIteration",
    "RalphRun",
    "RalphTask",
    "RalphWorkspace",
    "RalphWorkspacePaths",
    "RunLifecycle",
    "RunLifecycleResult",
    "RunStatus",
    "RunTable",
    "RunTableEntry",
    "ScoreCard",
    "SmokePlan",
    "TaskGroup",
    "TaskGroupStore",
    "TaskLibrary",
    "TaskLibraryEntry",
    "TaskLibraryError",
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
