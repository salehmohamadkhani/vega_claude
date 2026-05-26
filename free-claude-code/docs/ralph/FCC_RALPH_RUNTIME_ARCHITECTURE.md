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
Phase 1 [NOW]      Core models, roles, run table, scoring, verification plans, loop guard
                        ↓
Phase 2            Task planner, model role router, context builder, task library
                        ↓
Phase 3            Critic/arbiter, verifier command runner, memory store
                        ↓
Phase 4            Admin UI for Ralph Runtime, KPI dashboard
                        ↓
Phase 5            Playwright KPI verifier, browser-based acceptance testing
                        ↓
Phase 6            Full Ralph Loop with Claude Code via FCC proxy
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

## What Remains for Phase 2+

| Capability | Phase | Dependencies |
|---|---|---|
| `TaskLibrary` — Markdown task file loading | 2 | `core/ralph/models.py` |
| `ContextBuilder` — Git-aware task context | 2 | `core/ralph/models.py` |
| `ModelRoleRouter` — Maps AgentRole → FCC provider/model | 2 | `core/ralph/roles.py`, FCC `config/settings.py` |
| `TaskPlanner` — Breaks goal into tasks | 2 | `core/ralph/models.py`, `core/ralph/roles.py` |
| `DirectModelAdapter` — LLM calls for planning (no Claude Code) | 2 | `core/ralph/model_router.py`, FCC `providers/` |
| `CommandRunner` — Executes verification commands | 3 | `core/ralph/verification.py` |
| `Critic` — Reviews task output | 3 | `core/ralph/roles.py`, `core/ralph/scoring.py` |
| `Arbiter` — Resolves Doer↔Critic disputes | 3 | `core/ralph/roles.py`, `core/ralph/scoring.py` |
| `MemoryStore` — Persistent task memory | 3 | FCC `~/.fcc/` config path |
| Admin UI — Ralph tab in FCC admin | 4 | FCC `api/admin_routes.py` |
| Full Ralph Loop — Async Claude Code loop | 5 | `core/ralph/loop_guard.py`, FCC `cli/manager.py` |
| Playwright KPI Verifier | 5 | Playwright, FCC smoke tests |
| Agent profiles | 3 | `core/ralph/roles.py` |

---

*Last updated: 2026-05-26 — Phase 2 baseline*

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
Phase 3             Verification runner, FCC smoke adapter, critic/arbiter skeleton, task library
                        ↓
Phase 4             Admin UI for Ralph Runtime, KPI dashboard
                        ↓
Phase 5             Full Ralph Loop with Claude Code via FCC proxy
                        ↓
Phase 6             Playwright KPI verifier, browser-based acceptance testing
```
