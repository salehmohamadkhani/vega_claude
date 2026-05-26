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
Phase 4             Task library, context builder, memory store, agent profiles
                        ↓
Phase 5             Admin UI for Ralph Runtime, KPI dashboard
                        ↓
Phase 6             Full Ralph Loop with Claude Code via FCC proxy
                        ↓
Phase 7             Playwright KPI verifier, browser-based acceptance testing
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

## What Remains for Phase 4+

| Capability | Phase | Dependencies |
|---|---|---|
| `TaskLibrary` — Markdown task file loading | 4 | `core/ralph/models.py` |
| `ContextBuilder` — Git-aware task context | 4 | `core/ralph/models.py` |
| `MemoryStore` — Persistent task memory | 4 | FCC `~/.fcc/` config path |
| Agent profiles | 4 | `core/ralph/roles.py` |
| Admin UI — Ralph tab in FCC admin | 5 | FCC `api/admin_routes.py` |
| Full Ralph Loop — Async Claude Code loop | 6 | `core/ralph/loop_guard.py`, FCC `cli/manager.py` |
| Playwright KPI Verifier | 7 | Playwright, FCC smoke tests |

---

*Last updated: 2026-05-26 — Phase 3.5 baseline*

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

Claude Code launch belongs in the execution layer (Phase 4+). Phase 2 builds the planning and routing foundation that tells future phases *which* model to use and *what* tasks to execute.

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
Phase 4             Task library, context builder, memory store, agent profiles
                        ↓
Phase 5             Admin UI for Ralph Runtime, KPI dashboard
                        ↓
Phase 6             Full Ralph Loop with Claude Code via FCC proxy
                        ↓
Phase 7             Playwright KPI verifier, browser-based acceptance testing
```
