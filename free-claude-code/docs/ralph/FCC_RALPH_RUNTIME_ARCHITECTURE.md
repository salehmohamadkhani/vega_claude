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
│  │  │ Policy / KPI  │  │ Decisions  │  │ Critic (Ph3+)      │   │  │
│  │  │ Quality Gate  │  └────────────┘  │ Arbiter (Ph3+)      │   │  │
│  │  └──────────────┘                   └────────────────────┘   │  │
│  │                                                               │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌────────────────────┐  │  │
│  │  │ Execution    │  │ Real Pilot   │  │ Loop Runner        │  │  │
│  │  │ Guard        │  │ (Phase 8)    │  │ (Phase 7.1)        │  │  │
│  │  └──────────────┘  └──────────────┘  └────────────────────┘  │  │
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
Phase 6 [DONE]      CLI surface for Ralph Runtime — fcc-ralph plan/review/approve/run/status/report
                        ↓
Phase 6.1 [DONE]    CLI integration hardening — ``run`` delegates to ``RunExecutor``,
                    Policy A enforced, JSON output validated, 12 new tests
                        ↓
Phase 7 [SKIPPED]    Ralph Admin UI was deferred; focus shifted to CLI
                        ↓
Phase 7.1 [DONE]    CLI-driven Ralph loop — multi-iteration retry/debug/escalate,
                    loop policy, fcc-ralph run --loop, status/report loop awareness,
                    Policy A (contiguous approved prefix), JSON output hardening
                        ↓
Phase 8 [DONE]      Controlled real execution pilot through fcc-ralph:
                    - ExecutionGuard verifies safety (no system roots, dirty git, repo root)
                    - RealPilot creates throwaway workspace outside repo
                    - fcc-ralph run --pilot — dry-run by default, --real requires --allow-real-execution
                    - Exit codes: 0 success, 4 approval-required, 5 unsafe-real
                    - 65 new tests: guard (26), pilot (14), CLI pilot (11), misc coverage
                        ↓
Phase 9 [DONE]      Verification & KPI expansion: verification policy layer,
                    KPIEvaluator with 6 types, quality gate KPI integration,
                    CLI --verify/--kpi/--smoke-target flags, smoke adapter
                    expansion (ralph targets), 62 passing policy/KPI/smoke tests
                        ↓
Phase 9.15A [DONE]  Agent Council V2 Taxonomy & Research Corpus Plan:
                    SEPCC operator transition, 56-agent taxonomy across
                    17 layers, artifact contracts (33 artifacts defined),
                    Research Corpus bootstrap plan (40-50 repos).
                    No source changes — design docs only.
                        ↓
Phase 9.15B [DONE]  Research Corpus Bootstrap: 42 repos cloned (6.4GB),
                    42 YAML cards, 42 Markdown notes, 5 index files,
                    153 patterns catalogued across 18 categories.
                        ↓
Phase 9.15C [DONE]  Research Corpus Quality Audit: validated all 42 cards
                    (0 errors), all 5 indexes (consistent), all 42 repos
                    (healthy), coverage gaps documented (Security critical),
                    corpus rated USABLE for Phase 9.16.
                        ↓
Phase 9.15D [DONE]  Security Corpus Expansion: 7 security repos added
                    (Semgrep, Gitleaks, Checkov, Nuclei, Grype, Syft,
                    OWASP ZAP). Layer 12 upgraded to Strong. 49 repos,
                    181 patterns. Phase 9.16 now safe to start.
                        ↓
Phase 9.16A [DONE]  Agent Council V2 Core Foundation: models, registry (17 agents),
                    dependency graph, artifact contracts (23), activation planner
                    (8 project types), research map, evidence model. 142 tests.
                    Core foundation complete — no LLM calls, no network access.
Phase 9.16B [DONE]  Agent Council V2 Agent Specialization: expanded 17→56 agents
                    from full taxonomy (AGENT_COUNCIL_V2_TAXONOMY.md), 33 artifact
                    contracts, 8 project-type plans, grouping methods, artifact
                    chain validation. 196 tests. No cycles.
                        ↓
Phase 10   [DEFERRED] Future: Playwright KPI verifier, browser-based
                    acceptance testing, async loop, admin UI
```

## Phase 8 — Controlled Real Execution Pilot

### What Phase 8 Adds

| Module | File | Status |
|---|---|---|
| Execution Guard | `core/ralph/execution_guard.py` | System root/home root/forbidden path detection, dirty git detection, allowed/forbidden file enforcement |
| Real Pilot | `core/ralph/real_pilot.py` | Isolated throwaway workspace creation, pilot task setup, structured pilot results |
| Guard Tests | `tests/core/ralph/test_execution_guard.py` | 26 tests — system root, guard check, git detection, changed file validation |
| Pilot Tests | `tests/core/ralph/test_real_pilot.py` | 14 tests — basic pilot, config, mocked execution |
| CLI Pilot Tests | `tests/core/ralph/test_cli_real_pilot.py` | 11 tests — pilot commands, safety flags, approval gates, JSON output |
| CLI Integration | `core/ralph/cli.py` | `--pilot`, `--pilot-workspace`, `--allow-dirty-git`, `--allow-repo-root-execution` flags |

### Safety Architecture

```
fcc-ralph run --pilot --real --allow-real-execution
        │
        ▼
  RealPilot.run()
        │
        ├─ 1. Resolve pilot workspace path (temp or user-provided)
        ├─ 2. Create pilot workspace (mkdir + init)
        ├─ 3. Run ExecutionGuard
        │       ├─ Path exists?
        │       ├─ System root / home root?
        │       ├─ Forbidden path?
        │       ├─ Git repo root? (--allow-repo-root-execution)
        │       └─ Dirty git? (--allow-dirty-git)
        ├─ 4. Create pilot file (README.md)
        ├─ 5. Create approved pilot task
        ├─ 6. Run through RalphLoopRunner
        └─ 7. Detect changed files
```

### Guard Properties

| Check | Default | Override |
|---|---|---|
| System root | Block | — |
| Home root | Block | — |
| Forbidden paths (C:\\Windows, Program Files, etc.) | Block | — |
| Git repo root | Block | `--allow-repo-root-execution` |
| Dirty git | Block | `--allow-dirty-git` |
| Temp path | Allow | — |
| User-provided workspace outside repo | Allow | — |

### Test Growth

537 tests total (+65 from Phase 7.1). All checks passing.

### Test Growth

537 tests total (+65 from Phase 7.1). After Phase 8.5 lint cleanup: 536.

---

## Phase 9 — Verification & KPI Expansion

### What Phase 9 Adds

| Module | File | Status |
|---|---|---|
| Verification Policy | `core/ralph/verification_policy.py` | Command risk classification (SAFE/REVIEW/BLOCKED), destructive/network/git-write/install/shell blocking, tool whitelist (pytest, py_compile, ruff, ty), `classify_command()`, `validate_commands()` |
| KPI Model | `core/ralph/kpi.py` | `KPIType` (BOOLEAN/COUNT/THRESHOLD/TEXT_MATCH/FILE_EXISTS/COMMAND_EXIT_ZERO), `KPIEvaluator` with per-type evaluation, workspace-scoped file access with path escape detection |
| Quality Gate KPI | `core/ralph/quality_gate.py` | `kpi_results` in `QualityGateResult`, `_build_kpis_from_task()` helper, required KPI failures override arbiter to RETRY |
| Prompt Builder KPI | `core/ralph/prompt_builder.py` | Enhanced KPI checklist with evidence instruction, anti-hallucination reinforcement |
| CLI Verification | `core/ralph/cli.py` | `--verify`, `--smoke-target TARGET`, `--kpi TEXT` flags on `run`; verification/KPI/smoke blocks in JSON output and reports |
| Smoke Adapter | `core/ralph/smoke_adapter.py` | New targets: `ralph`, `core-ralph`, `smoke-collect`, `api-prereq`, `admin-routes`, `provider-registry` |

### Verification Policy Architecture

```
VerificationPolicy
  ─ Toggle flags: allow_pytest, allow_ruff, allow_ty, block_shell, block_network, block_destructive_commands, max_timeout_seconds=120
  ─ classify_command(cmd) → VerificationPolicyDecision(command, risk, allowed, reason, normalized_command)
  ─ validate_commands(cmds) → list[VerificationPolicyDecision]

Whitelist (SAFE):
  - python -m py_compile
  - python -m pytest / uv run pytest
  - uv run ruff check / ruff check
  - uv run ty check / ty check
  - git status/diff/log/show/branch/ls-files
  - uv run pytest --collect-only (smoke)

Blocklist (BLOCKED):
  - Destructive: rm, rmdir, del, format, shutdown, dd, mkfs
  - Network: curl, wget, fetch, Invoke-WebRequest
  - Git write: push, pull, merge, rebase, reset, clean, cherry-pick, revert
  - Shells: sh, bash, zsh, powershell, pwsh, cmd
  - Package managers: npm, pip, cargo, go
  - Arbitrary code: python -c, python -i

Fallback (REVIEW):  Unknown tools → not allowed, requires human review
```

### Safety Flow

```
Policy check takes precedence over prefix-based allowlist:

Command → classify_command()
  ├─ BLOCKED → SKIPPED (structured result with policy_decision metadata)
  ├─ REVIEW  → SKIPPED (requires human review)
  └─ SAFE    → prefix check → execute
                    │
              timeout clamped to policy.max_timeout_seconds
```

### KPI Evaluation Architecture

```
KPIEvaluator
  ─ evaluate(kpi) → KPIResult(kpi_id, status, passed, reason, observed_value, metadata)
  ─ evaluate_all(kpis) → list[KPIResult]
  ─ kpis_all_passed(results) → bool

Per-type evaluators:
  BOOLEAN           → target True/False comparison
  COUNT             → observed_value >= threshold
  THRESHOLD         → target >= threshold
  TEXT_MATCH        → text found in file at file_path
  FILE_EXISTS       → file_path exists in workspace
  COMMAND_EXIT_ZERO → command runs via VerificationRunner, exit code 0 = pass

Safety:
  - _resolve_safe() blocks paths escaping workspace_root
  - COMMAND_EXIT_ZERO passes through VerificationPolicy first
  - Policy-blocked commands → KPIStatus.SKIPPED
```

### Quality Gate KPI Integration

```
QualityGate.evaluate(task):
  1. Build verification plan
  2. Run verification commands
  3. Build KPIs from task.kpis (list[str] → BOOLEAN KPIs, target=True, required=True)
  4. Evaluate KPIs via KPIEvaluator
  5. Compute ScoreCard (includes kpi_score field)
  6. Run critic, loop guard, arbiter
  7. If required KPIs fail → override arbiter decision to RETRY
```

### CLI Integration

```
fcc-ralph run [--verify] [--smoot-target TARGET ...] [--kpi "KPI text" ...]

JSON output:
  {
    "verification": {
      "policy_results": [...],
      "kpi_results": [...],
      "smoke_results": {...}
    },
    "task_results": {...}
  }

Text output:
  Verification & KPIs:
    Commands: 3  |  KPIs: 2  |  Smoke targets: 1
```

### Test Growth

62 new tests across 5 test files:

| File | Tests | What It Covers |
|---|---|---|
| `tests/core/ralph/test_verification_policy.py` | 22 | SAFE classification (8), BLOCKED classification (13), normalization (3), batch validation (1) |
| `tests/core/ralph/test_kpi.py` | 12 | FILE_EXISTS (4), TEXT_MATCH (4), BOOLEAN (2), THRESHOLD (2), COMMAND_EXIT_ZERO (2), batch (3) |
| `tests/core/ralph/test_quality_gate_kpi.py` | 4 | Required KPI pass, required KPI failure, KPI score in ScoreCard, no-KPI gate |
| `tests/core/ralph/test_smoke_adapter.py` | 6 new | Ralph targets (`is_known`), expanded known targets test |
| `tests/core/ralph/test_cli_verification.py` | 4 | `--verify` accepted, `--smoke-target` accepted, unknown target warning, `--kpi` in JSON |

Total after Phase 9: **598 tests** (+62 from Phase 8).

### Constraint Compliance

All Phase 9 work respects the Phase 8 constraints:
- No Admin UI, no messaging, no provider routing
- No `/v1/messages` modification, no provider implementation changes
- No real execution default (dry-run only)
- No Playwright or browser automation
- No API key ownership inside Ralph Runtime
- Blocked commands produce structured skipped results, never execute

---

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

## What Remains for Phase 9.15+

| Capability | Phase | Dependencies |
|---|---|---|
| Research Corpus Bootstrap | 9.15B | ✅ 42 repos, 42 YAML cards, 42 notes, 5 indexes, 153 patterns |
| Research Corpus Quality Audit | 9.15C | ✅ All cards/indexes/repos validated (0 errors), corpus rated USABLE |
| Security Corpus Expansion | 9.15D | ✅ 7 security repos added, Layer 12 Strong, 49 repos, 181 patterns |
| Agent Council V2 Core Foundation | 9.16A | ✅ Models, registry (17 agents), dependency graph, 23 artifact contracts, activation planner (8 types), research map, evidence model. 142 tests. |
| Agent Council V2 Specialization | 9.16B | ✅ Expanded 17→56 agents, 33 artifact contracts, grouping methods, artifact chain validation, 196 tests, zero cycles. |
| Admin UI — Ralph tab in FCC admin | deferred | FCC `api/admin_routes.py` |
| Full Ralph Loop — Async Claude Code loop | deferred | `core/ralph/run_executor.py`, FCC `cli/manager.py` |
| Playwright KPI Verifier | deferred | Playwright, FCC smoke tests |

---

*Last updated: 2026-05-30 — Phase 9.16B complete (Agent Council V2 Specialization: 56 agents, 33 contracts, 196 tests, 0 cycles)*

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
Phase 5.7 [DONE]    CLI-first audit — roadmap correction, execution contract audit, CLI plan
                        ↓
Phase 6 [DONE]      CLI surface for Ralph Runtime — fcc-ralph plan/review/approve/run/status/report
                        ↓
Phase 6.1 [DONE]    CLI integration hardening — ``run`` delegates to ``RunExecutor``,
                    Policy A enforced, JSON output validated, 12 new tests
                        ↓
Phase 7 [DONE]      CLI-driven Ralph loop — multi-iteration retry/debug/escalate,
                    loop policy, fcc-ralph run --loop, status/report loop awareness
                        ↓
Phase 8 [DONE]      Controlled real execution pilot through fcc-ralph:
                    - still gated, approval-required, no provider ownership
                    - validates fcc-claude integration end-to-end
                        ↓
Phase 9 [DONE]      Verification & KPI expansion:
                    - verification policy layer (SAFE/REVIEW/BLOCKED)
                    - KPIEvaluator with 6 KPI types
                    - quality gate KPI integration
                    - CLI --verify/--kpi/--smoke-target flags
                    - smoke adapter expansion (ralph targets)
                    - 62 passing policy/KPI/smoke tests
                        ↓
Phase 9.15A [DONE]  Agent Council V2 Taxonomy & Research Corpus Plan
                        ↓
Phase 9.15B [DONE]  Research Corpus Bootstrap (42 repos, 5 indexes)
                        ↓
Phase 9.15C [DONE]  Research Corpus Quality Audit (validated, 0 errors)
                        ↓
Phase 9.15D [DONE]  Security Corpus Expansion (7 repos, Layer 12 Strong)
                        ↓
Phase 9.16  [DONE]  Agent Council V2 Implementation (9.16A + 9.16B complete)
                        ↓
Phase 10   [DEFERRED] Playwright KPI verifier, browser-based acceptance
                    testing, async loop, admin UI
```
