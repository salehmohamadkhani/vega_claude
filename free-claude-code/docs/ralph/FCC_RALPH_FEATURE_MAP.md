# FCC ↔ Ralph Feature Map

> Phase 1 reference: what FCC already does, what Ralph did externally, and what we rebuild natively.

---

## FCC Capabilities We Reuse

| Capability | FCC Module | How Ralph Runtime Will Use It |
|---|---|---|
| Provider API routing | `providers/registry.py` | Future: ModelRoleRouter resolves AgentRole → FCC provider/model |
| Model config & env vars | `config/settings.py` | Future: read `RALPH_*` settings, model overrides |
| Claude Code proxy | `api/services.py` | Future: Ralph Loop feeds prompts through FCC proxy, not Copilot CLI |
| CLI session management | `cli/manager.py` | Future: Ralph Loop uses `CLISessionManager` for Claude Code sessions |
| Admin UI | `api/admin_routes.py` | Phase 2+: Admin tab for run table, scoring, verification |
| Messaging (Discord/Telegram) | `messaging/handler.py` | Phase 3+: AgentTable results optionally feed back to chat |
| Smoke tests | `smoke/` | KPI verification targets for RalphTask |
| Product tests | `tests/` | Unit + integration tests for Ralph Runtime components |
| Logging/tracing | `core/trace.py`, `loguru` | Replace `print()` with structured logging |
| Rate limiting | `core/rate_limit.py` | Future: loop guard respects provider rate limits |

## Ralph Capabilities We Rebuild Natively

| Ralph Concept | Original Ralph File | FCC-Native Target | Phase |
|---|---|---|---|
| State machine (enable/disable/iterate) | `ralph_mode/state.py` | `core/ralph/models.py` + `core/ralph/loop_guard.py` | 1 |
| Agent roles (Doer/Critic/Arbiter) | `ralph_mode/agent_table/roles.py` | `core/ralph/roles.py` | 1 |
| Run table / Table of Runes | `ralph_mode/agent_table/table.py` | `core/ralph/run_table.py` | 1 |
| Scoring / trust scoring | `ralph_mode/agent_table/scoring.py` | `core/ralph/scoring.py` | 1 |
| Verification commands | `ralph_mode/verification.py` | `core/ralph/verification.py` | 1 |
| Completion promise / loop guard | `ralph_mode/state.py` (check_completion) | `core/ralph/loop_guard.py` | 1 |
| Task library | `ralph_mode/tasks.py` | Phase 2: `core/ralph/task_library.py` | 2 |
| Context manager | `ralph_mode/context.py` | Phase 2: `core/ralph/context_builder.py` | 2 |
| Model role routing | (implicit in Ralph) | Phase 2: `core/ralph/model_router.py` | 2 |
| Task planner | (prompt-based in Ralph) | Phase 2: `core/ralph/planner.py` | 2 |
| Memory store | `ralph_mode/memory.py` | Phase 2+: `core/ralph/memory.py` | 3 |
| Critic/arbiter negotiation | `ralph_mode/agent_table/` | Phase 3+: `core/ralph/critic.py`, `core/ralph/arbiter.py` | 3 |
| Auto-agents | `ralph_mode/state.py` (auto_agents) | Phase 3+: `core/ralph/agent_registry.py` | 3 |
| Agent profiles | `.github/agents/` | Phase 3+: `core/ralph/profiles/` CLI config | 3 |

## Ralph Capabilities We Will NOT Copy

| Ralph Feature | Reason |
|---|---|
| GitHub Copilot CLI dependency | FCC owns Claude Code. Never use Copilot CLI. |
| Shell loop (ralph-loop.sh) | Replace with async Python loop using FCC's `CLISessionManager` |
| `.github/agents/` dir convention | Keep agent profiles in FCC config, not GitHub-specific paths |
| `.github/skills/` | GitHub-specific. FCC will not use skills. |
| Hooks system | FCC manages its own lifecycle via FastAPI lifespan |
| MCP server integration | Not needed. FCC is the proxy layer. |
| `colorama` / ANSI color constants | Use `loguru` formatting or rich in admin UI |
| `argparse` CLI (30+ commands) | Replace with a few focused `fcc-ralph` subcommands |
| Copilot `-p` flag integration | Ralph fed prompts via `copilot -p "...".` FCC feeds through its own API. |

## Mapping Table: Ralph Concept → FCC-Native Implementation

| Ralph Concept | FCC-Native Target | Status in Phase 1 |
|---|---|---|
| `RalphMode` class | `core/ralph/models.py` — `RalphRun`, `RalphTask` | ✅ Dataclasses defined |
| `AgentRole` enum | `core/ralph/roles.py` — `AgentRole`, `ModelRole` | ✅ Enums defined |
| `AgentTable` orchestrator | `core/ralph/run_table.py` — `RunTable` | ✅ In-memory run table |
| Trust scoring | `core/ralph/scoring.py` — `ScoreCard` | ✅ Deterministic scoring |
| Verification markdown parsing | `core/ralph/verification.py` — `VerificationPlan` | ✅ Plan modeling only |
| Completion promise check | `core/ralph/loop_guard.py` — `LoopGuard` | ✅ Deterministic loop guard |
| `TaskLibrary` | — | Phase 2 |
| `ContextManager` | — | Phase 2 |
| `MemoryStore` | — | Phase 3 |
| Agent profiles | — | Phase 3 |
| Auto-agents | — | Phase 3 |

## Testing / KPI Strategy

| Test Layer | Tool | What It Covers |
|---|---|---|
| Unit tests (Phase 1) | `pytest` | Models, run table, scoring, verification plans, loop guard |
| Integration tests (Phase 2+) | `pytest` + fixtures | Task planner, model router, context builder |
| Smoke tests (Phase 2+) | `pytest smoke/` | Ralph Runtime tasks hitting FCC smoke targets |
| KPI verifier (Phase 3) | Future: `core/ralph/kpi_verifier.py` | Measure pass rates, iteration counts, hallucination rate |
| Playwright / browser (Phase 4) | Future: Playwright | Admin UI for Ralph Runtime |

KPI metrics to track across phases:
- **Task pass rate**: % of tasks passing verification on first attempt
- **Average iterations per task**: loop efficiency
- **Critic override rate**: how often arbiter overrides critic
- **Hallucination incidents**: flagged by scoring
- **Verification command success rate**: reliability of smoke targets

---

*Last updated: 2026-05-25 — Phase 1 baseline*
