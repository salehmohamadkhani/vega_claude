"""Single iteration runner for Ralph Runtime.

Orchestrates one iteration of a task: build prompt → execute →
verify → quality gate → checkpoint. Does not manage multi-iteration
loops or task selection — that is the RunExecutor's responsibility.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .checkpoint import Checkpoint, CheckpointStore
from .claude_execution import ClaudeCodeExecutionAdapter
from .context_builder import ContextBuilder
from .execution import ExecutionMode, ExecutionRequest, ExecutionResult, ExecutionStatus
from .models import (
    ProjectGoal,
    RalphRun,
    RalphTask,
    TaskStatus,
)
from .prompt_builder import TaskPromptBuilder, TaskPromptContext
from .quality_gate import QualityGate, QualityGateResult
from .run_table import RunTable
from .task_library import TaskLibrary
from .verification import build_verification_plan_for_task
from .workspace import RalphWorkspace


@dataclass
class IterationRunnerConfig:
    """Configuration for IterationRunner behavior.

    Safe default: dry-run only. Real execution requires explicit
    opt-in via ``execution_mode=ExecutionMode.REAL``.

    When ``gate_config`` is provided, Agent Council evidence gates are
    enforced against task results during the quality gate step.
    """

    execution_mode: ExecutionMode = ExecutionMode.DRY_RUN
    gate_config: object | None = (
        None  # RuntimeGateConfig (lazy to avoid circular import)
    )


@dataclass
class IterationRunResult:
    """Structured outcome of a single iteration."""

    run_id: str = ""
    task_id: str = ""
    iteration: int = 0
    execution_result: ExecutionResult = field(default_factory=ExecutionResult)
    quality_gate_result: QualityGateResult = field(default_factory=QualityGateResult)
    checkpoint: Checkpoint = field(default_factory=Checkpoint)
    next_action: str = ""
    passed: bool = False
    failure_reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class IterationRunner:
    """Run a single iteration of a task through the full pipeline.

    Pipeline::

        build_verification_plan → build_prompt → execute → quality_gate
        → checkpoint → IterationRunResult
    """

    def __init__(
        self,
        config: IterationRunnerConfig | None = None,
        workspace: RalphWorkspace | None = None,
        task_library: TaskLibrary | None = None,
        execution_adapter: ClaudeCodeExecutionAdapter | None = None,
        prompt_builder: TaskPromptBuilder | None = None,
        quality_gate: QualityGate | None = None,
        checkpoint_store: CheckpointStore | None = None,
        context_builder: ContextBuilder | None = None,
        run_table: RunTable | None = None,
    ) -> None:
        self._config = config or IterationRunnerConfig()
        self._workspace = workspace or RalphWorkspace()
        self._task_library = task_library or TaskLibrary(self._workspace)
        self._adapter = execution_adapter or ClaudeCodeExecutionAdapter()
        self._prompt_builder = prompt_builder or TaskPromptBuilder()
        self._quality_gate = quality_gate or QualityGate()
        self._checkpoint_store = checkpoint_store or CheckpointStore(self._workspace)
        self._context_builder = context_builder or ContextBuilder(
            workspace=self._workspace, repo_root="."
        )
        self._run_table = run_table or RunTable()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run_iteration(
        self,
        run: RalphRun,
        task: RalphTask,
        iteration_number: int = 1,
        goal: ProjectGoal | None = None,
    ) -> IterationRunResult:
        """Run a single iteration of the given task.

        Parameters
        ----------
        run:
            The parent RalphRun.
        task:
            The task to iterate on.
        iteration_number:
            Which iteration this is (1-based).
        goal:
            Optional ProjectGoal for prompt context.

        Returns
        -------
        An IterationRunResult with all intermediate outputs.
        """
        # Step 1: Build verification plan from task
        plan = build_verification_plan_for_task(task)

        # Step 2: Build prompt
        prompt_context = TaskPromptContext(
            goal=goal,
            task=task,
            verification_plan=plan,
        )
        prompt = self._prompt_builder.build_task_prompt(prompt_context)

        # Step 3: Execute via adapter
        exec_request = ExecutionRequest(
            run_id=run.id,
            task_id=task.id,
            task_title=task.title,
            prompt=prompt,
            workspace_path=str(self._workspace.paths().root),
            mode=self._config.execution_mode,
            allowed_files=list(task.allowed_files),
            forbidden_files=list(task.forbidden_files),
        )
        exec_result = self._adapter.execute(exec_request)

        # Step 4: Run quality gate (uses empty verification result in dry-run)
        gate_args: dict[str, Any] = {}
        gc = self._config.gate_config
        if gc is not None:
            use_gates = getattr(gc, "use_agent_council_gates", False)
            strict_gates = getattr(gc, "strict_agent_council_gates", False)
            if use_gates:
                gate_args["use_agent_council_gates"] = True
                gate_args["strict_agent_council_gates"] = strict_gates
                # Build council context if project type is available
                ptype = getattr(gc, "project_type", None) or ""
                pgoal = getattr(gc, "project_goal", None) or goal.title if goal else ""
                if ptype or pgoal:
                    try:
                        from .agent_council.planner_integration import (
                            build_agent_council_task_context,
                        )

                        council_ctx = build_agent_council_task_context(
                            goal=str(pgoal) if pgoal else task.title,
                            project_type=ptype or None,
                            strict_mode=strict_gates,
                        )
                        gate_args["agent_council_context"] = council_ctx
                    except Exception:
                        pass

        gate_result = self._quality_gate.evaluate(
            task=task,
            retry_count=iteration_number - 1,
            **gate_args,
        )

        # Step 5: Determine next action and pass/fail
        next_action = gate_result.arbiter_decision.action.value
        passed = gate_result.all_passed and gate_result.is_approved()

        if not passed:
            # In dry-run mode, the quality gate has no real verification
            # output, so it will not pass. Report this clearly.
            if exec_result.status == ExecutionStatus.SKIPPED:
                failure_reason = (
                    "Dry-run: execution was skipped. "
                    "No verification results to evaluate."
                )
            else:
                failure_reason = exec_result.failure_reason or gate_result.summary
        else:
            failure_reason = ""

        # Step 6: Update run table entry
        entry = self._run_table.get_entry(task.id)
        if entry is not None:
            entry.status = TaskStatus.PASSED if passed else TaskStatus.NEEDS_FIX
            entry.iteration_number = iteration_number
            entry.next_action = next_action

        # Step 7: Save checkpoint
        checkpoint = Checkpoint.from_run_state(
            run_id=run.id,
            task_id=task.id,
            iteration_number=iteration_number,
            run_status=run.status,
            task_status=TaskStatus.PASSED if passed else TaskStatus.NEEDS_FIX,
            score_card=gate_result.score_card
            if hasattr(gate_result, "score_card")
            else None,
            arbiter_action=next_action,
            next_action=next_action,
            execution_skipped=(exec_result.status == ExecutionStatus.SKIPPED),
            execution_mode=exec_result.mode.value,
            execution_status=exec_result.status.value,
            execution_exit_code=exec_result.exit_code,
            execution_timed_out=exec_result.timed_out,
            quality_gate_action=next_action,
        )
        self._checkpoint_store.save_checkpoint(checkpoint)

        # Step 8: Save context snapshot
        context = self._context_builder.build_snapshot(
            goal_id=run.goal_id,
            run_id=run.id,
            task_id=task.id,
            task=task,
        )
        self._context_builder.save_snapshot(context)

        return IterationRunResult(
            run_id=run.id,
            task_id=task.id,
            iteration=iteration_number,
            execution_result=exec_result,
            quality_gate_result=gate_result,
            checkpoint=checkpoint,
            next_action=next_action,
            passed=passed,
            failure_reason=failure_reason,
        )
