# Ralph Runtime — FCC-Native Core

## What This Is

The Ralph Runtime is FCC's native implementation of iterative AI agent
orchestration. It manages task planning, run tracking, multi-agent roles,
quality scoring, verification plans, and loop guard logic — all without
direct provider access or subprocess execution.

## Separation of Concerns

| Owned By | Concerns |
|---|---|
| **FCC Platform** | Providers, API keys, model routing, Claude Code proxy, CLI, Admin UI, messaging, rate limiting, tracing |
| **Ralph Runtime** | Task planning, run table, agent roles, scoring, verification plans, loop guard, critic/arbiter, debugging workflows |

The Ralph Runtime never calls providers directly, never launches
Claude Code, and never reads FCC credentials.

## Phase 1 Status

Phase 1 establishes the foundation:
- Domain models (`ProjectGoal`, `RalphTask`, `RalphRun`)
- Agent and model roles (`AgentRole`, `ModelRole`)
- Run table (`RunTable`, `RunTableEntry`)
- Deterministic scoring (`ScoreCard`)
- Verification planning (`VerificationPlan`, `VerificationResult`)
- Loop guard (`LoopGuard`, `LoopGuardDecision`)

**Not yet implemented** (Phase 2+):
- Task planner
- ModelRoleRouter (maps roles to FCC providers)
- Verification command execution
- Critic/arbiter agents
- Memory store
- Admin UI
- Ralph Loop with Claude Code via FCC proxy

## Usage

```python
from core.ralph import (
    AgentRole, RalphTask, RalphRun,
    RunTable, RunTableEntry,
    ScoreCard, build_verification_plan_for_task,
    LoopGuard, LoopAction,
)
```

All models are deterministic dataclasses. No network calls. No subprocesses.

---

*See `docs/ralph/` for full architecture documentation.*
