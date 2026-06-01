# Ralph Runtime — FCC-Native Core

## What This Is

The Ralph Runtime is FCC's native implementation of autonomous AI agent
orchestration. It manages task planning, run tracking, multi-agent roles,
quality scoring, verification plans, loop guard logic, and Agent Council
integration — all without direct provider access or subprocess execution.

## Separation of Concerns

| Owned By | Concerns |
|---|---|
| **FCC Platform** | Providers, API keys, model routing, Claude Code proxy, CLI, Admin UI, messaging, rate limiting, tracing |
| **Ralph Runtime** | Task planning, run table, agent roles, scoring, verification plans, loop guard, critic/arbiter, Agent Council, evidence gates, sandbox |

The Ralph Runtime never calls providers directly, never launches
Claude Code, and never reads FCC credentials. Real execution is
delegated to the `ClaudeCodeExecutionAdapter` which goes through
the FCC proxy.

## Modules

| Module | Status | Description |
|---|---|---|
| `planner.py` | ✅ **Implemented** | Heuristic-based task planning from goal text — decomposes into structured tasks |
| `model_router.py` | ✅ **Implemented** | `ModelRoleRouter` maps Ralph agent roles to FCC provider/model routes |
| `arbiter.py` | ✅ **Implemented** | `ArbiterEngine` — 9 priority-ordered rules deciding APPROVE/RETRY/DEBUG/ESCALATE/STOP |
| `critic.py` | ✅ **Implemented** | `CriticEngine` — reviews verification results against success criteria |
| `loop_guard.py` | ✅ **Implemented** | `LoopGuard` — 6 deterministic rules (max iterations, error repetition, timeouts, etc.) |
| `loop_runner.py` | ✅ **Implemented** | `RalphLoopRunner` — multi-iteration per-task orchestration with memory |
| `iteration_runner.py` | ✅ **Implemented** | 8-step single-iteration pipeline: plan → prompt → execute → gate → decide |
| `quality_gate.py` | ✅ **Implemented** | Full pipeline: Verification→ScoreCard→Critic→LoopGuard→Arbiter |
| `verification.py` | ✅ **Implemented** | `VerificationPlan`, `VerificationResult` with pass/fail criteria |
| `verification_runner.py` | ✅ **Implemented** | Executes verification commands, captures results |
| `verification_policy.py` | ✅ **Implemented** | Command classification (build, test, lint, smoke, security, etc.) |
| `verification_profiles.py` | ✅ **Implemented** | 4 profiles: fast, standard, thorough, security |
| `scoring.py` | ✅ **Implemented** | `ScoreCard` — weighted scoring across implementation, test, KPI, risk, confidence |
| `kpi.py` | ✅ **Implemented** | KPI types and evaluator for measurable outcomes |
| `memory.py` | ✅ **Implemented** | `MemoryStore` — 4-level episodic memory with keyword-based retrieval |
| `claude_execution.py` | ✅ **Implemented** | `ClaudeCodeExecutionAdapter` — real execution bridge to Claude Code |
| `execution_guard.py` | ✅ **Implemented** | Real execution safety guard — blocks dangerous paths and commands |
| `run_executor.py` | ✅ **Implemented** | Multi-task coordinator with Policy A (strict ordered execution) |
| `run_lifecycle.py` | ✅ **Implemented** | Run state transitions (PENDING→APPROVED→RUNNING→PASSED/FAILED) |
| `run_table.py` | ✅ **Implemented** | In-memory task tracking table |
| `checkpoint.py` | ✅ **Implemented** | `CheckpointStore` — JSON persistence of iteration checkpoints |
| `task_library.py` | ✅ **Implemented** | `TaskLibrary` — Markdown/YAML task persistence |
| `context_builder.py` | ✅ **Implemented** | Git context snapshots for reproducibility |
| `prompt_builder.py` | ✅ **Implemented** | `TaskPromptBuilder` — builds structured prompts for Claude Code |
| `agent_profiles.py` | ✅ **Implemented** | `AgentProfile` and `AgentProfileRegistry` for role-specific behavior |
| `workspace.py` | ✅ **Implemented** | `.fcc-ralph/` workspace directory management |
| `execution.py` | ✅ **Implemented** | `ExecutionRequest`/`Result`/`Config` models |
| `smoke_adapter.py` | ✅ **Implemented** | `FCCSmokeAdapter` for controlled smoke test execution |
| `real_pilot.py` | ✅ **Implemented** | `RealPilot` for controlled execution validation |
| `_frontmatter.py` | ✅ **Implemented** | Minimal YAML frontmatter parser (no PyYAML dependency) |
| `cli.py` | ✅ **Implemented** | 8 CLI commands: plan, review, approve, run, status, council-plan, council-gates, sandbox-smoke, report |

### Agent Council (agent_council/)

| Module | Status | Description |
|---|---|---|
| `registry.py` | ✅ **Implemented** | 56 default specialized agents across 17 layers with validation |
| `activation.py` | ✅ **Implemented** | Per-project type activation maps (8 project types) |
| `plan_generator.py` | ✅ **Implemented** | 15-step deterministic council plan generation |
| `planner_integration.py` | ✅ **Implemented** | Bridges Agent Council plans into Ralph task planning context |
| `dependency_graph.py` | ✅ **Implemented** | Graph utilities: topological sort, cycle detection, parallel groups, critical path |
| `artifact_contracts.py` | ✅ **Implemented** | 33 default artifact contracts with required fields and validation |
| `evidence_gates.py` | ✅ **Implemented** | 12 evidence gates: artifact_exists, claim_has_evidence, no_fake_echo, qa_behavior, etc. |
| `gate_runner.py` | ✅ **Implemented** | `run_evidence_gates()` and `run_all_gates()` with result summaries |
| `runtime_gate_enforcer.py` | ✅ **Implemented** | Runtime enforcement of evidence gates with block/override decisions |
| `runtime_evidence.py` | ✅ **Implemented** | 12 `RuntimeEvidenceSource` types mapping execution results to gate inputs |
| `runtime_gate_config.py` | ✅ **Implemented** | `RuntimeGateConfig` — configures gate behavior per run |
| `runtime_adapter.py` | ✅ **Implemented** | Bridges Agent Council to the Ralph runtime execution loop |
| `runtime_sandbox.py` | ✅ **Implemented** | Isolated sandbox for evidence-gated backtests with artifact collection |
| `research_map.py` | ✅ **Implemented** | Research corpus integration — maps past patterns to agent plans |

## CLI Usage

```bash
# Plan a run from a goal
fcc-ralph plan "Build a landing page"

# Review planned tasks
fcc-ralph review

# Approve a task for execution
fcc-ralph approve --task-id task-1

# Run tasks (with optional Agent Council evidence gating)
fcc-ralph run --use-agent-council-gates

# Show workspace/run status
fcc-ralph status

# Agent Council commands
fcc-ralph council-plan --project-type landing_page --project-goal "..." 
fcc-ralph council-gates --verify-path ./output --project-type landing_page

# Sandbox smoke test
fcc-ralph sandbox-smoke --project-type landing_page

# Generate report
fcc-ralph report
```

## Python Usage

```python
from core.ralph import (
    AgentRole, RalphTask, RalphRun,
    RunTable, RunTableEntry,
    ScoreCard, build_verification_plan_for_task,
    LoopGuard, LoopAction,
    ArbiterEngine, ArbiterAction,
    CriticEngine,
    TaskPlanner,
    ModelRoleRouter,
    MemoryStore,
)

# Plan tasks from a goal
planner = TaskPlanner()
run = planner.plan("Build a landing page with React")

# Run with quality gates and arbiter
from core.ralph.iteration_runner import IterationRunner
runner = IterationRunner()
result = runner.run_iteration(run=run, task=run.tasks[0], iteration_number=1)
```

All models are deterministic dataclasses. No network calls. No subprocesses.

## Architecture Overview

```
CLI (cli.py)
  │
  ├── plan ──────► TaskPlanner.plan() ──► RunLifecycle.prepare_run()
  │
  ├── run ───────► RunExecutor.run_until_blocked()
  │                  │
  │                  ├── IterationRunner.run_iteration()
  │                  │     ├── build_verification_plan
  │                  │     ├── TaskPromptBuilder.build_task_prompt
  │                  │     ├── ClaudeCodeExecutionAdapter.execute
  │                  │     └── QualityGate.evaluate()
  │                  │           ├── VerificationRunner
  │                  │           ├── ScoreCard
  │                  │           ├── CriticEngine
  │                  │           ├── LoopGuard
  │                  │           ├── ArbiterEngine
  │                  │           └── RuntimeGateEnforcer
  │                  │
  │                  └── RETRY → resets task to APPROVED, continues
  │                        (bounded by max_iterations_per_task)
  │
  ├── council-plan ──► CouncilPlanGenerator.generate()
  │     ├── registry activation (per project type)
  │     ├── topological sort → parallel groups → critical path
  │     └── artifact contracts → evidence gates → research map
  │
  ├── council-gates ──► run_evidence_gates()
  │     └── 12 evidence gates evaluated against context
  │
  └── sandbox-smoke ──► create sandbox → collect artifacts → validate
```

## Phase History

| Phase | Scope | Status |
|---|---|---|
| 9.15A–D | Agent Council V2 taxonomy, Research Corpus, Security Corpus | ✅ Done |
| 9.16A–I | Agent Council core, registry, plan generator, evidence gates, runtime sandbox | ✅ Done |
| 9.16T3/T7 | Telegram MiniApp integration | ✅ Done |
| **9.17** | **Runtime hardening, gap closure, RETRY, critical path, frontmatter fix, test coverage** | **✅ Done** |

---

*See `docs/ralph/` for full architecture documentation and phase reports.*
