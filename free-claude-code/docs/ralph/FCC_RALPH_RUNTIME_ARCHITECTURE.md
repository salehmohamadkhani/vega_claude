# FCC-Native Ralph Runtime Architecture

> Phase 1 foundation document.

---

## Final Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         FCC Platform                                 │
│                                                                     │
│  ┌────────────┐  ┌────────────┐  ┌──────────┐  ┌───────────────┐  │
│  │  API Layer │  │  Admin UI  │  │   CLI    │  │  Messaging     │  │
│  │  /v1/*     │  │  /admin/*  │  │ fcc-*    │  │  Discord/TG    │  │
│  └─────┬──────┘  └──────┬─────┘  └────┬─────┘  └───────┬───────┘  │
│        │                │             │                │          │
│  ┌─────┴────────────────┴─────────────┴────────────────┴───────┐  │
│  │                    Provider Layer                             │  │
│  │  ProviderRegistry → 17 providers → ModelRouter → RateLimit   │  │
│  └──────────────────────────────────────────────────────────────┘  │
│        │                │             │                │          │
│  ┌─────┴────────────────┴─────────────┴────────────────┴───────┐  │
│  │                 Ralph Runtime (core/ralph/)                   │  │
│  │                                                               │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────────┐   │  │
│  │  │  Models  │  │  Roles   │  │Run Table │  │  Scoring   │   │  │
│  │  │ RalphTask│  │ AgentRole│  │  Track   │  │  ScoreCard │   │  │
│  │  │ RalphRun │  │ ModelRole│  │  Status   │  │  Weights   │   │  │
│  │  └──────────┘  └──────────┘  └──────────┘  └────────────┘   │  │
│  │                                                               │  │
│  │  ┌──────────────┐  ┌────────────┐  ┌────────────────────┐   │  │
│  │  │ Verification  │  │ Loop Guard │  │ Planner (Ph2+)     │   │  │
│  │  │ Plan & Result │  │ Decisions  │  │ Critic (Ph3+)      │   │  │
│  │  └──────────────┘  └────────────┘  │ Arbiter (Ph3+)      │   │  │
│  │                                    └────────────────────┘   │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                   Claude Code Proxy (api/)                    │  │
│  │  /v1/messages → ModelRouter → Provider → SSE stream          │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

## Why FCC Owns Model/API/Provider Routing

FCC already provides:
- **17 provider integrations** with credential management
- **Model routing** (opus/sonnet/haiku tier → provider/model mapping)
- **Rate limiting** per provider
- **Proxy auth** and security headers
- **SSE streaming** with content-type negotiation
- **Admin UI** for live config management
- **CLI launcher** (`fcc-claude`) that wraps Claude Code with FCC proxy env

Ralph Runtime MUST NOT duplicate any of these. Instead, it uses **abstract roles** (`ModelRole`) that future phases will resolve through FCC's provider layer.

## Why Ralph Runtime Owns Task Planning, Orchestration, Scoring, Verification

Ralph Runtime adds capabilities FCC never had:
- **Iterative task loops** — FCC proxies single requests; Ralph manages multi-turn task completion
- **Multi-agent deliberation** — Planner, Architect, Doer, Critic, Verifier, Debugger, Arbiter roles
- **Run table** — tracks task lifecycle across iterations
- **Scoring** — deterministic quality metrics per task and per run
- **Verification planning** — structured command/smoke/KPI plans from task definitions
- **Loop guard** — prevents infinite loops, detects stagnation, escalates failures

These are fundamentally **orchestration concerns**, not provider concerns. They belong in `core/ralph/`, layered above the provider stack.

## Why Claude Code Execution Goes Through FCC, Not Copilot CLI

- FCC already manages Claude Code subprocesses via `CLISessionManager`
- FCC already handles: proxy env injection, session IDs, forking, cleanup, PID tracking
- Reusing FCC's session management means Ralph Loop gets: network resilience, resource limits, clean shutdown, and integration with FCC's `/stop` endpoint — for free

## Phase Roadmap

```
Phase 1 [DONE]      Core models, roles, run table, scoring, verification plans, loop guard
                        ↓
Phase 2 [DONE]      Model role router, task planner foundation
                        ↓
Phase 3 [DONE]      Verification runner, smoke adapter, critic/arbiter, quality gate
                        ↓
Phase 3.5 [DONE]    Stabilization audit — bugs fixed, hardened, test coverage +15
                        ↓
Phase 4 [DONE]      Task library, context builder, memory store, agent profiles, run lifecycle
                        ↓
Phase 4.5 [DONE]    Persistence layer audit — PyYAML removed, path traversal hardened,
                    RunLifecycle validation, 8 new tests, 299 passing
                        ↓
Phase 5 [DONE]      First execution layer — execution models, prompt builder,
                    Claude Code execution adapter (dry-run), iteration runner, run executor
                        ↓
Phase 5.5 [DONE]    Execution safety audit — approval gate hardening, no auto-approve,
                    command fallback hardening, dry-run semantics, safety prompts
                        ↓
Phase 5.6 [DONE]    Execution lifecycle hardening — IterationRunnerConfig, max_iterations,
                    DEBUG/ESCALATE/RETRY handling, allowlist hardening, config validation
                        ↓
Phase 6             CLI surface for Ralph Runtime — fcc-ralph plan/review/approve/run/status/report
                        ↓
Phase 7             Admin UI for Ralph Runtime, KPI dashboard
                        ↓
Phase 8             Full Ralph Loop with Claude Code via FCC proxy
                        ↓
Phase 9             Playwright KPI verifier, browser-based acceptance testing
```

## What Phase 1 Implements Now

| Module | Files | Status |
|---|---|---|
| Domain models | `models.py` | ✅ `ProjectGoal`, `RalphTask`, `RalphRun`, `RalphIteration`, `CriticDecision` |
| Agent roles | `roles.py` | ✅ `AgentRole` (7 roles), `ModelRole` (5 roles) |
| Run table | `run_table.py` | ✅ `RunTable` with entries, status tracking, completion % |
| Scoring | `scoring.py` | ✅ `ScoreCard` with ranges, weighting, hallucination risk |
| Verification | `verification.py` | ✅ `VerificationPlan`, `VerificationResult`, plan builder |
| Loop guard | `loop_guard.py` | ✅ `LoopGuardDecision`, `LoopGuard` with deterministic rules |
| Tests | `tests/core/ralph/` | ✅ Unit tests for all 6 modules |

### Phase 1 Design Principles

1. **Deterministic** — No AI calls, no network, no subprocesses, no randomness
2. **Stateless by default** — In-memory run table; no filesystem persistence
3. **FCC-style** — Uses dataclasses (matching FCC `core/` conventions), not Pydantic
4. **Provider-agnostic** — Roles are abstract enums, not provider names
5. **Testable** — Every function returns deterministic output from deterministic input

## What Remains for Phase 6+

| Capability | Phase | Dependencies |
|---|---|---|
| Admin UI — Ralph tab in FCC admin | 6 | FCC `api/admin_routes.py` |
| Full Ralph Loop — Async Claude Code loop | 7 | `core/ralph/run_executor.py`, FCC `cli/manager.py` |
| Playwright KPI Verifier | 8 | Playwright, FCC smoke tests |

---

*Last updated: 2026-05-26 — Phase 5.6 complete*

---

## Phase 5 — First Execution Layer (Dry-Run)

### What Phase 5 Adds

| Module | File | Status |
|---|---|---|
| Execution Models | `core/ralph/execution.py` | ✅ `ExecutionMode`, `ExecutionStatus`, `ExecutionRequest`, `ExecutionResult`, `ExecutionConfig` |
| Prompt Builder | `core/ralph/prompt_builder.py` | ✅ `TaskPromptContext`, `TaskPromptBuilder` — deterministic prompt construction |
| Claude Code Execution | `core/ralph/claude_execution.py` | ✅ `ClaudeCodeCommandBuilder`, `ClaudeCodeExecutionAdapter` — dry-run by default |
| Iteration Runner | `core/ralph/iteration_runner.py` | ✅ `IterationRunResult`, `IterationRunner` — single iteration pipeline |
| Run Executor | `core/ralph/run_executor.py` | ✅ `RunExecutorResult`, `RunExecutor` — multi-task coordination |

### Architecture Integration

```
                        Ralph Runtime (core/ralph/) Phase 5

  ┌─────────────────────────────────────────────────────────────────┐
  │                        RunExecutor                               │
  │  run_next_task → run_until_blocked                               │
  │                                                                   │
  │  ┌──────────────────────────────────────────────────────────┐   │
  │  │                  IterationRunner                          │   │
  │  │  build_plan → build_prompt → execute → quality_gate      │   │
  │  │  → checkpoint → IterationRunResult                        │   │
  │  └──────────────────────────────────────────────────────────┘   │
  │                                                                   │
  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐   │
  │  │ PromptBuilder │  │ClaudeExec    │  │ ExecutionConfig      │   │
  │  │ TaskPromptCtx │  │ Adapter      │  │ dry_run=True         │   │
  │  │ deterministic │  │ allowlist    │  │ allow_real=False     │   │
  │  └──────────────┘  └──────────────┘  └──────────────────────┘   │
  │                                                                   │
  │  Uses: RunLifecycle, QualityGate, CheckpointStore, RunTable     │
  └─────────────────────────────────────────────────────────────────┘
```

### Execution Safety Design

- **Default: dry-run only** — `ExecutionConfig(dry_run=True, allow_real_execution=False)`
- **Command allowlist** — only `fcc-claude` and `claude` are permitted executables
- **No shell=True** — all subprocess calls use explicit argv lists
- **Timeout enforcement** — configurable per-command timeout (default 300s)
- **Output truncation** — bounded stdout/stderr capture (default 50KB)
- **No provider calls** — the adapter runs Claude Code CLI, not provider APIs
- **No API keys** — Ralph Runtime never owns credentials

### Dry-Run Behaviour

When in dry-run mode:
1. `ExecutionAdapter.execute()` returns SKIPPED immediately — no subprocess
2. `IterationRunner.run_iteration()` returns `passed=False` with clear reason
3. `RunExecutor.run_next_task()` still creates checkpoints and context snapshots
4. All pipeline code is exercised except the actual subprocess call

### Safety Properties

- `ExecutionConfig.allow_real_execution` must be explicitly set to `True`
- `ExecutionRequest.mode` must be `REAL` (not `DRY_RUN`)
- Command must be in `command_allowlist` (default: `["fcc-claude", "claude"]`)
- `subprocess.run` uses `shell=False` — no shell injection
- Output is truncated to `max_output_chars`
- Timeout raises `TimeoutExpired` → `ExecutionStatus.TIMED_OUT`
- `FileNotFoundError` caught and returned as structured failure

---

## Phase 4 — Persistence and Context Layer

### What Phase 4 Adds

| Module | File | Status |
|---|---|---|
| Workspace Store | `core/ralph/workspace.py` | ✅ Safe filesystem I/O with path traversal protection and deterministic JSON |
| Task Library | `core/ralph/task_library.py` | ✅ YAML frontmatter + markdown task persistence |
| Task Groups | `core/ralph/task_groups.py` | ✅ Ordered task grouping with JSON persistence |
| Context Builder | `core/ralph/context_builder.py` | ✅ Git-aware context snapshot builder (read-only, timeout=10s) |
| Checkpoint Store | `core/ralph/checkpoint.py` | ✅ Resumable run state with iteration tracking |
| Memory Store | `core/ralph/memory.py` | ✅ Four-level memory (working/episodic/semantic/procedural) |
| Agent Profiles | `core/ralph/agent_profiles.py` | ✅ 8 FCC-native profiles, abstract model roles |
| Run Lifecycle | `core/ralph/run_lifecycle.py` | ✅ Orchestration skeleton — no execution |

### Architecture Integration

```
                        Ralph Runtime (core/ralph/) Phase 4

  ┌─────────────────────────────────────────────────────────────────┐
  │                        RunLifecycle                              │
  │  create_run → prepare_run → approve_task → mark_running → result │
  │                                                                   │
  │  ┌──────────┐  ┌──────────────┐  ┌──────────┐  ┌────────────┐  │
  │  │ Workspace │  │ TaskLibrary  │  │ TaskGroup│  │ Context    │  │
  │  │ Store     │  │ .md files    │  │ Store    │  │ Builder    │  │
  │  │ JSON I/O  │  │ YAML fm      │  │ JSON     │  │ Git snap   │  │
  │  └──────────┘  └──────────────┘  └──────────┘  └────────────┘  │
  │                                                                   │
  │  ┌──────────┐  ┌──────────────┐  ┌──────────────────────────┐   │
  │  │Checkpoint│  │ MemoryStore  │  │ AgentProfileRegistry     │   │
  │  │ Store    │  │ 4-level      │  │ 8 profiles, model roles │   │
  │  │ Resume   │  │ keyword srch │  │ no .github dependency   │   │
  │  └──────────┘  └──────────────┘  └──────────────────────────┘   │
  │                                                                   │
  │  Shared: RalphWorkspace paths at .fcc-ralph/{tasks,runs,...}    │
  └─────────────────────────────────────────────────────────────────┘
```

### Safety Properties

- **Workspace**: path traversal prevention on all user-supplied paths; deterministic JSON (stable diffs)
- **Task Library**: no execution — pure I/O with YAML parsing; `TaskParseError` on malformed frontmatter
- **Context Builder**: read-only git commands only; 10-second timeout; graceful non-git fallback (empty strings)
- **Checkpoint Store**: no mutation of existing checkpoints — always creates new; sorted by iteration_number
- **Memory Store**: level validation (4 valid levels); importance range 0–100; `MemoryRecordNotFoundError` on missing update
- **Run Lifecycle**: explicitly does NOT execute verification, launch Claude Code, or call providers; status progression enforced via RunStatus enum
- **No provider imports**: all Phase 4 modules are `core/ralph/`-internal — no imports from `providers/`, `api/`, or external packages beyond stdlib. PyYAML
  dependency removed in Phase 4.5.

---

## Phase 4.5 — Persistence Layer Audit & Hardening

### What Phase 4.5 Fixed

| Issue | Module | Detail |
|---|---|---|
| PyYAML dependency not declared | `task_library.py` | Created `core/ralph/_frontmatter.py` — internal replacement, no external dep |
| Path traversal string-prefix check | `workspace.py` | `Path.relative_to()` blocks sibling-prefix attacks like `.fcc-ralph-evil/` |
| RunLifecycle stub creation | `run_lifecycle.py` | Existence validation before status transitions; raises `RunLifecycleError` |
| Python 2 except syntax (3 locations) | `context_builder.py`, `memory.py` | `except (Exc1, Exc2):` tuple form |
| Frontmatter quoting on hyphens | `_frontmatter.py` | Only quote strings with `:`, `#`, or leading `*` |

### Test Growth

299 tests total (+8 from Phase 4). All checks passing: ruff, ty, pytest, smoke collect.

### Architecture Note

`_frontmatter.py` is a `core/ralph/`-internal utility module with no external dependencies. It is not intended to replace general YAML parsing — it handles only
the subset needed for task-file frontmatter (scalars, lists, nested dicts).

---

## Phase 3.5 — Stabilization Audit

### What Was Fixed

| Issue | Module | Detail |
|---|---|---|
| Global counter | `planner.py` | Moved to instance level with per-call reset |
| Duplicate entries | `run_table.py` | Guard in `add_entry` |
| Bare pytest commands | `smoke_adapter.py` | `uv run pytest` with `--collect-only` |
| Missing targets | `smoke_adapter.py` | Added `telegram`, `discord` |
| Syntax error | `planner.py` | `def self._next_task_id` → `def _next_task_id` |
| Skipped verification | quality_gate + critic | Edge-case regression tests |

### Test Growth

217 tests total (+15 from Phase 3). All checks passing: ruff, ty, pytest, smoke collect.

---

## Phase 3 — Verification Quality Gate Layer

### What Phase 3 Adds

| Module | File | Status |
|---|---|---|
| VerificationRunner | `core/ralph/verification_runner.py` | ✅ Safe command execution with timeout, truncation, prefix allowlist |
| FCCSmokeAdapter | `core/ralph/smoke_adapter.py` | ✅ Maps smoke targets to pytest commands |
| CriticEngine | `core/ralph/critic.py` | ✅ Deterministic review of verification + scoring |
| ArbiterEngine | `core/ralph/arbiter.py` | ✅ Rule-based dispute resolution |
| QualityGate | `core/ralph/quality_gate.py` | ✅ Orchestrates plan→runner→scoring→critic→arbiter |

### Architecture Integration

```
┌─────────────────────────────────────────────────────────────┐
│                  QualityGate (Phase 3)                       │
│                                                             │
│  RalphTask → build_verification_plan → VerificationRunner   │
│       ↓                                                     │
│  ScoreCard ← _compute_score_from_verification               │
│       ↓                                                     │
│  CriticEngine.review_verification + review_scoring           │
│       ↓                                                     │
│  LoopGuard.evaluate                                         │
│       ↓                                                     │
│  ArbiterEngine.decide → QualityGateResult                    │
└─────────────────────────────────────────────────────────────┘
```

### Safety Properties

- VerificationRunner: execution disabled by default; shlex.split; prefix allowlist; timeout; output truncation
- CriticEngine: no LLM calls, no subprocesses — pure heuristic/arithmetic
- ArbiterEngine: 9-rule priority system, no random/ML/network
- QualityGate: composes existing modules without adding new capabilities

---

## Phase 2 — Model Role Router & Task Planner

### What Phase 2 Adds

| Module | File | Status |
|---|---|---|
| ModelRoleRouter | `core/ralph/model_router.py` | ✅ Resolves `ModelRole` → FCC provider/model |
| TaskPlanner | `core/ralph/planner.py` | ✅ Heuristic goal → spec → RalphTasks |

### Architecture Integration

```
┌─────────────────────────────────────────────────────────────┐
│                    Ralph Runtime (core/ralph/)               │
│                                                             │
│  ┌──────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │  Models   │  │ ModelRouter   │  │ TaskPlanner          │  │
│  │  Roles    │  │ (Phase 2)    │  │ (Phase 2)            │  │
│  └──────────┘  └──────┬───────┘  └──────────┬───────────┘  │
│                       │                      │              │
│                       │  Settings.resolve    │  Goal + spec │
│                       │  _model/tier         │  → RalphTasks│
│                       ▼                      ▼              │
│              ┌──────────────────────────────────┐           │
│              │     FCC Settings (config/)        │           │
│              │     resolve_model / parse_*       │           │
│              └──────────────────────────────────┘           │
└─────────────────────────────────────────────────────────────┘
```

### Why Phase 2 Still Does Not Call Providers

- `ModelRoleRouter` resolves model intent using `Settings` methods only — no provider imports, no network, no credentials
- `TaskPlanner` is purely heuristic — keyword matching, string concatenation, dataclass construction
- Both are safe to import and test without any FCC infrastructure running

### Why Phase 2 Still Does Not Launch Claude Code

Claude Code launch belongs in the execution layer (Phase 4+). Phase 2 builds the planning and routing foundation that tells future phases *which* model to use
and *what* tasks to execute.

### Updated Phase Roadmap

```
Phase 1 [DONE]      Core models, roles, run table, scoring, verification plans, loop guard
                        ↓
Phase 2 [DONE]      Model role router, task planner foundation
                        ↓
Phase 3 [DONE]      Verification runner, smoke adapter, critic/arbiter, quality gate
                        ↓
Phase 3.5 [DONE]    Stabilization audit — bugs fixed, hardened, test coverage +15
                        ↓
Phase 4 [DONE]      Task library, context builder, memory store, agent profiles, run lifecycle
                        ↓
Phase 4.5 [DONE]    Persistence layer audit — PyYAML removed, path traversal hardened,
                    RunLifecycle validation, 8 new tests, 299 passing
                        ↓
Phase 5 [DONE]      First execution layer — dry-run execution models, prompt builder,
                    Claude Code adapter, iteration runner, run executor
                        ↓
Phase 5.5 [DONE]    Execution safety audit — approval gate, command fallback, dry-run semantics
                        ↓
Phase 5.6 [DONE]    Execution lifecycle — IterationRunnerConfig, allowlist, config validation
                        ↓
Phase 6             Full Ralph Loop with Claude Code via FCC proxy
                        ↓
Phase 7             Playwright KPI verifier, browser-based acceptance testing
```
