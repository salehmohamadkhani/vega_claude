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

*Last updated: 2026-05-28 — Phase 8 complete (real execution pilot)*


---

## Phase 5.5 — Execution Safety Audit & Approval-Gate Hardening

### Bug Fixed: RunExecutor Auto-Approval

`RunExecutor._find_next_task()` treated PENDING tasks as runnable, and `run_next_task()` auto-approved them before execution. This violated the product flow:

```
goal → questions → task list → human review/approval → execution
```

**Fix**: Added `RunExecutorConfig(auto_approve_pending_tasks=False)`. PENDING tasks are now skipped by default. Only APPROVED tasks execute unless auto-approval is explicitly enabled.

### Hardening

| Area | Change |
|---|---|
| Command fallback | `ClaudeCodeCommandBuilder.build_command()` requires `allow_fallback=True` for echo fallback; raises `CommandBuilderError` otherwise |
| Dry-run semantics | Iteration checkpoint records `execution_skipped=True`; uses enum comparison (not string) |
| Prompt safety | Added scoped-change, forbidden-files, and changed-files report instructions |
| Config | `ExecutionConfig(allow_test_fallback=False)` — echo fallback opt-in |

### Tests Added (19)

| File | Tests |
|---|---|
| `test_run_executor.py` | 10 — approval gate, pending/approved selection, auto-approve config, blocked results |
| `test_iteration_runner.py` | 3 — dry-run failure reason, skipped execution, checkpoint metadata |
| `test_claude_execution.py` | 5 — no-CLI failure, echo fallback disabled, dry-run skips I/O |
| `test_prompt_builder.py` | 3 — scoped changes, forbidden files, changed files instructions |
| `test_execution.py` | 1 — `allow_test_fallback` default |

### Check Results

364 tests, ruff clean, ty clean.

### Updated Mapping Table

| Ralph Concept | FCC-Native Target | Status | Phase |
|---|---|---|---|
| Execution approval gate | `core/ralph/run_executor.py` — `RunExecutorConfig` | (hardened) | 5.5 |
| Command fallback safety | `core/ralph/claude_execution.py` — `CommandBuilderError` | (hardened) | 5.5 |
| Prompt safety instructions | `core/ralph/prompt_builder.py` | (hardened) | 5.5 |

---

## Phase 5.6 — Execution Lifecycle Hardening Before CLI

### Six Risks Fixed

| # | Risk | Fix |
|---|---|---|
| 1 | `max_iterations_per_task` not enforced | Per-task iteration counter in `run_until_blocked()`, checked before each iteration |
| 2 | `stop_on_debug`/`stop_on_escalate`/RETRY unhandled | Structured arbiter action handling: `debug_required`, `escalation_required`, `retry_required` result fields |
| 3 | `IterationRunner` hardcodes `DRY_RUN` | `IterationRunnerConfig(execution_mode=ExecutionMode.DRY_RUN)` — configurable |
| 4 | Echo fallback + real execution unsafe | `validate_for_execution()` raises `ExecutionConfigError` when both enabled |
| 5 | Command allowlist weak for Windows | `_is_command_allowed` accepts `list[str]` (no quoting), `.exe` variants added to allowlist |
| 6 | Approval order policy implicit | Policy A documented and enforced: first PENDING blocks all later tasks |

### Tests Added (22)

| File | Tests |
|---|---|
| `test_run_executor.py` | 10 — debug/escalate/retry/stop handling, Policy A, blocked_task_id, max_tasks |
| `test_iteration_runner.py` | 8 — IterationRunnerConfig, dry-run/real modes, checkpoint enrichment |
| `test_claude_execution.py` | 10 — allowlist basename/prefix/Windows/Unix/empty, config validation rejection |
| `test_execution.py` | 4 — validate_for_execution() passes/blocks, validate_for_test_fallback() passes/blocks |

### Check Results

391 tests, all clean.

### Updated Mapping Table

| Ralph Concept | FCC-Native Target | Status | Phase |
|---|---|---|---|
| Execution mode config | `core/ralph/iteration_runner.py` — `IterationRunnerConfig` | (hardened) | 5.6 |
| Config validation | `core/ralph/execution.py` — `ExecutionConfigError` | (hardened) | 5.6 |
| Command allowlist | `core/ralph/claude_execution.py` — `_is_command_allowed` | (hardened) | 5.6 |
| Arbiter action handling | `core/ralph/run_executor.py` | (hardened) | 5.6 |

---

## Phase 5 — First Execution Layer

### What Phase 5 Adds

| Module | File | Purpose |
|---|---|---|
| Execution Models | `core/ralph/execution.py` | `ExecutionMode`, `ExecutionStatus`, `ExecutionRequest`, `ExecutionResult`, `ExecutionConfig` — the execution safety layer |
| Prompt Builder | `core/ralph/prompt_builder.py` | `TaskPromptBuilder` — structured 12-section prompts from `RalphTask`, context, verification plan, and memory |
| Claude Code Adapter | `core/ralph/claude_execution.py` | `ClaudeCodeCommandBuilder` (resolves fcc-claude > claude > echo fallback) + `ClaudeCodeExecutionAdapter` (dry-run by default, allowlist enforcement, no shell=True) |
| Iteration Runner | `core/ralph/iteration_runner.py` | `IterationRunner.run_iteration()` — 8-step pipeline: prompt → execution → context → quality gate → checkpoint → table update |
| Run Executor | `core/ralph/run_executor.py` | `RunExecutor.run_until_blocked()` — selects next PENDING/APPROVED task, runs one iteration, respects LoopGuard/Arbiter decisions |

### Execution Safety Design

| Property | Mechanism |
|---|---|
| Default dry-run | `ExecutionConfig(dry_run=True, allow_real_execution=False)` |
| No provider calls | Ralph Runtime never calls providers or owns API keys |
| No shell=True | All subprocess calls use explicit argv lists |
| Command allowlist | Basename matching against `command_allowlist` |
| Output truncation | `max_output_chars` bounds stdout/stderr capture |
| Timeout enforcement | Per-command timeout via `subprocess.run(timeout=...)` |
| Deterministic prompts | `TaskPromptBuilder.build_task_prompt()` — no randomness, no model calls |

### Test Coverage

| File | Tests | What It Covers |
|---|---|---|
| `tests/core/ralph/test_execution.py` | 10 | Defaults, serialization, skipped factory, config |
| `tests/core/ralph/test_prompt_builder.py` | 11 | All 12 sections, anti-hallucination, determinism |
| `tests/core/ralph/test_claude_execution.py` | 10 | Dry-run, allowlist, timeout, cwd, output truncation, no shell=True |
| `tests/core/ralph/test_iteration_runner.py` | 8 | Pipeline ordering, dry-run safety, checkpoint, table update |
| `tests/core/ralph/test_run_executor.py` | 7 | Task selection, approval, ordering, dry-run safety |

### Updated Mapping Table

| Ralph Concept | FCC-Native Target | Status | Phase |
|---|---|---|---|
| Execution models | `core/ralph/execution.py` | ✅ | 5 |
| Prompt builder | `core/ralph/prompt_builder.py` | ✅ | 5 |
| Claude Code execution | `core/ralph/claude_execution.py` | ✅ | 5 |
| Iteration runner | `core/ralph/iteration_runner.py` | ✅ | 5 |
| Run executor | `core/ralph/run_executor.py` | ✅ | 5 |

---

## Phase 4.5 — Persistence Layer Audit & Hardening

### What Phase 4.5 Fixed

| Issue | Module | Fix |
|---|---|---|
| PyYAML dependency not in `pyproject.toml` | `task_library.py` | Created `core/ralph/_frontmatter.py` — internal serializer/parser |
| Path traversal used string-prefix check | `workspace.py` | Replaced with `Path.relative_to()` — blocks sibling-prefix attacks |
| RunLifecycle created stubs for nonexistent tasks | `run_lifecycle.py` | Added existence validation with `RunLifecycleError` |
| Python 2 comma-syntax in 3 `except` clauses | `context_builder.py`, `memory.py` | Parenthesized tuple form |
| Spurious frontmatter quoting on hyphens | `_frontmatter.py` | Removed `-` from quoting triggers |

### Tests Added (8)

| File | Tests Added |
|---|---|
| `test_workspace.py` | 4 — traversal safety (sibling-prefix, deep, internal, subdir) |
| `test_checkpoint.py` | 1 — from_run_state round-trip with all fields |
| `test_run_lifecycle.py` | 2 — nonexistent task error cases |
| `test_memory.py` | 1 — importance range validation |

### Check Results

299 tests passed, ruff clean, ty clean, smoke collect 76.

### Updated Mapping Table

| Ralph Concept | FCC-Native Target | Status | Phase |
|---|---|---|---|
| Workspace store | `core/ralph/workspace.py` | ✅ (hardened) | 4 |
| Task library | `core/ralph/task_library.py` | ✅ (hardened) | 4 |
| Task groups | `core/ralph/task_groups.py` | ✅ | 4 |
| Context builder | `core/ralph/context_builder.py` | ✅ | 4 |
| Checkpoint store | `core/ralph/checkpoint.py` | ✅ | 4 |
| Memory store | `core/ralph/memory.py` | ✅ | 4 |
| Agent profiles | `core/ralph/agent_profiles.py` | ✅ | 4 |
| Run lifecycle | `core/ralph/run_lifecycle.py` | ✅ (hardened) | 4 |
| YAML frontmatter | `core/ralph/_frontmatter.py` | ✅ (NEW — replaced PyYAML) | 4.5 |
| Execution models | `core/ralph/execution.py` | ✅ | 5 |
| Prompt builder | `core/ralph/prompt_builder.py` | ✅ | 5 |
| Claude Code adapter | `core/ralph/claude_execution.py` | ✅ | 5 |
| Iteration runner | `core/ralph/iteration_runner.py` | ✅ | 5 |
| Run executor | `core/ralph/run_executor.py` | ✅ | 5 |
| CLI — fcc-ralph | `core/ralph/cli.py` | ✅ | 6 |
| CLI hardening (RunExecutor delegation) | `core/ralph/cli.py` | ✅ | 6.1 |
| Admin UI | `core/ralph/admin/` | — | 7 |
| Full Ralph Loop | `core/ralph/loop.py` | — | 8 |
| Playwright KPI | `core/ralph/kpi_verifier.py` | — | 9 |

---

## Phase 4 — Persistence and Context Layer

### What Phase 4 Adds

| Module | File | Purpose |
|---|---|---|
| Workspace Store | `core/ralph/workspace.py` | Safe filesystem I/O with path traversal protection and deterministic JSON formatting |
| Task Library | `core/ralph/task_library.py` | Persistent task storage using YAML frontmatter + markdown body files |
| Task Groups | `core/ralph/task_groups.py` | Ordered task grouping with JSON persistence |
| Context Builder | `core/ralph/context_builder.py` | Git-aware context snapshot builder (read-only commands, 10s timeout) |
| Checkpoint Store | `core/ralph/checkpoint.py` | Resumable run state with per-run iteration tracking |
| Memory Store | `core/ralph/memory.py` | Four-level memory persistence (working/episodic/semantic/procedural) with keyword search |
| Agent Profiles | `core/ralph/agent_profiles.py` | 8 FCC-native agent profile templates (no `.github/agents` dependency) |
| Run Lifecycle | `core/ralph/run_lifecycle.py` | Run orchestration skeleton — create, prepare, approve, execute, result (no execution) |

### Updated Mapping Table

| Ralph Concept | FCC-Native Target | Status | Phase |
|---|---|---|---|
| Agent/Model roles | `core/ralph/roles.py` | ✅ | 1 |
| Run table | `core/ralph/run_table.py` | ✅ (hardened) | 1 |
| Scoring | `core/ralph/scoring.py` | ✅ | 1 |
| Verification plans | `core/ralph/verification.py` | ✅ | 1 |
| Loop guard | `core/ralph/loop_guard.py` | ✅ | 1 |
| Model role routing | `core/ralph/model_router.py` | ✅ | 2 |
| Task planner | `core/ralph/planner.py` | ✅ (fixed) | 2 |
| Verification runner | `core/ralph/verification_runner.py` | ✅ | 3 |
| Smoke adapter | `core/ralph/smoke_adapter.py` | ✅ (hardened) | 3 |
| Critic/arbiter | `core/ralph/critic.py`, `arbiter.py` | ✅ (hardened) | 3 |
| Quality gate | `core/ralph/quality_gate.py` | ✅ (hardened) | 3 |
| Workspace store | `core/ralph/workspace.py` | ✅ | 4 |
| Task library | `core/ralph/task_library.py` | ✅ | 4 |
| Task groups | `core/ralph/task_groups.py` | ✅ | 4 |
| Context builder | `core/ralph/context_builder.py` | ✅ | 4 |
| Checkpoint store | `core/ralph/checkpoint.py` | ✅ | 4 |
| Memory store | `core/ralph/memory.py` | ✅ | 4 |
| Agent profiles | `core/ralph/agent_profiles.py` | ✅ | 4 |
| Run lifecycle | `core/ralph/run_lifecycle.py` | ✅ | 4 |
| CLI — fcc-ralph | `core/ralph/cli.py` | ✅ | 6 |
| CLI hardening (RunExecutor delegation) | `core/ralph/cli.py` | ✅ | 6.1 |
| Admin UI | `core/ralph/admin/` | — | 7 |
| Full Ralph Loop | `core/ralph/loop.py` | — | 8 |
| Playwright KPI | `core/ralph/kpi_verifier.py` | — | 9 |

---

## Phase 3.5 — Stabilization Audit

### What Phase 3.5 Fixed

| Issue | Module | Fix |
|---|---|---|
| Global counter broke determinism | `planner.py` | Moved to instance-level counter with per-call reset |
| Duplicate task IDs inflated completion | `run_table.py` | Existence check before appending to run entry list |
| Bare `pytest` not `uv run pytest` | `smoke_adapter.py` | All commands prefixed with `uv run` |
| `telegram`/`discord` targets missing | `smoke_adapter.py` | Added to known targets |
| Empty targets returned no command | `smoke_adapter.py` | Returns collect-only fallback |
| `def self._next_task_id` syntax error | `planner.py` | Fixed stray `self.` prefix |

### Regression Tests Added (15)

| Area | Tests |
|---|---|
| Planner determinism | Cross-instance IDs, plan pipeline stability, ID format |
| RunTable duplicates | Dedup, update behavior, completion accuracy |
| Critic edge cases | Skipped verification, hallucination risk blocking |
| QualityGate edge cases | Skipped feedback, hallucination blocking, loop guard override |
| Arbiter edge cases | Loop guard overrides critic approval |
| SmokeAdapter | Features inventory sync, uv run pytest prefix, collect-only |

### No Architecture Drift

All `core/ralph/` imports remain relative and within-module. No imports from
`providers/`, Admin UI, or Claude Code modules.

### Updated Mapping Table

| Ralph Concept | FCC-Native Target | Status | Phase |
|---|---|---|---|
| Agent/Model roles | `core/ralph/roles.py` | ✅ | 1 |
| Run table | `core/ralph/run_table.py` | ✅ (hardened) | 1 |
| Scoring | `core/ralph/scoring.py` | ✅ | 1 |
| Verification plans | `core/ralph/verification.py` | ✅ | 1 |
| Loop guard | `core/ralph/loop_guard.py` | ✅ | 1 |
| Model role routing | `core/ralph/model_router.py` | ✅ | 2 |
| Task planner | `core/ralph/planner.py` | ✅ (fixed) | 2 |
| Verification runner | `core/ralph/verification_runner.py` | ✅ | 3 |
| Smoke adapter | `core/ralph/smoke_adapter.py` | ✅ (hardened) | 3 |
| Critic/arbiter | `core/ralph/critic.py`, `arbiter.py` | ✅ (hardened) | 3 |
| Quality gate | `core/ralph/quality_gate.py` | ✅ (hardened) | 3 |
| Task library | `core/ralph/task_library.py` | — | 4 |
| Context builder | `core/ralph/context_builder.py` | — | 4 |
| Memory store | `core/ralph/memory.py` | — | 4 |
| Agent profiles | `core/ralph/profiles/` | — | 4 |
| Full Ralph Loop | `core/ralph/loop.py` | — | 8 |

---

## Phase 3 — Verification Quality Gate Layer

### What Phase 3 Adds

| Module | File | Purpose |
|---|---|---|
| VerificationRunner | `core/ralph/verification_runner.py` | Safe, bounded command execution for verification plans |
| FCCSmokeAdapter | `core/ralph/smoke_adapter.py` | Maps smoke target labels to FCC-compatible pytest commands |
| CriticEngine | `core/ralph/critic.py` | Deterministic review of verification results, scoring, and acceptance criteria |
| ArbiterEngine | `core/ralph/arbiter.py` | Rule-based dispute resolution (approve/retry/debug/escalate/stop) |
| QualityGate | `core/ralph/quality_gate.py` | Orchestrates plan→runner→scoring→critic→loop guard→arbiter |

### VerificationRunner

Executes verification commands with strict safety controls:

- **Disabled by default** — `allow_command_execution=False`
- **shlex.split** — explicit argv parsing, no `shell=True`
- **Allowed prefix matching** — only commands matching registered prefixes execute
- **Timeout enforcement** — configurable per-command timeout
- **Output truncation** — bounded stdout/stderr capture
- **Structured results** — `CommandExecutionResult` with status, exit code, duration, output

### FCCSmokeAdapter

Maps Ralph smoke targets to FCC smoke commands. Known targets: `providers`, `api`, `cli`, `clients`, `nvidia_nim_cli`, `openrouter_free_cli`, `config`,
`messaging`, `tools`, `voice`, `rate_limit`, `auth`, `extensibility`, `lmstudio`, `llamacpp`, `ollama`.

### CriticEngine & ArbiterEngine

Both are deterministic (no LLM calls):

- **CriticEngine** — reviews verification command pass/fail counts, smoke target results, acceptance criteria (keyword heuristics), ScoreCard results, and
  estimates confidence
- **ArbiterEngine** — 9-rule priority system: loop guard overrides → critic approval check → low-confidence debug → rejection limits → retry escalation →
  fallback retry

### QualityGate

The orchestrator that ties Phase 3 together:

```
RalphTask → VerificationPlan → VerificationRunner → ScoreCard
    → CriticReview → LoopGuard → Arbiter → QualityGateResult
```

---

## Phase 2 — Model Role Router & Task Planner

### What Phase 2 Adds

| Module | File | Purpose |
|---|---|---|
| ModelRoleRouter | `core/ralph/model_router.py` | Resolves abstract `ModelRole` → FCC provider/model using `Settings` methods |
| TaskPlanner | `core/ralph/planner.py` | Heuristic-based goal → clarifying questions → project spec → RalphTasks |

### ModelRoleRouter

The router maps each `ModelRole` to a Claude-tier hint (`opus`/`sonnet`/`haiku`), then resolves it through FCC's existing `Settings.resolve_model()`,
`Settings.resolve_thinking()`, `parse_provider_type()`, and `parse_model_name()`.

| ModelRole | Default Tier | Thinking |
|---|---|---|
| PLANNER | haiku | No |
| DOER | sonnet | No |
| CRITIC | opus | Yes |
| DEBUGGER | sonnet | No |
| SUMMARIZER | haiku | No |

Safety properties:

- No provider imports — router uses `Settings` static/instance methods, not provider modules
- No network calls — purely local model-string resolution
- No credential reads — `Settings` methods return configured model strings, not API keys
- Deterministic — same policy + settings → same resolution

### TaskPlanner

The planner converts a `ProjectGoal` into:

1. **ClarifyingQuestions** — heuristic-based, keyword-matched questions about scope, APIs, UI, messaging, testing, constraints
2. **ProjectSpec** — structured spec with summary, constraints, KPIs, assumptions, risks, target areas
3. **RalphTasks** — always 4+ tasks: architecture/context → implementation → verification/testing → docs/report

Task generation injects metadata based on goal keywords:

| Keyword Match | Effect |
|---|---|
| api/proxy/provider/model/routing | Adds API smoke targets, provider verification commands |
| admin/ui/browser/dashboard | Adds UI rendering KPI, Admin UI notes |
| messaging/telegram/discord | Adds messaging smoke targets |
| tests/smoke/kpi/coverage | Adds smoke collection to verification commands |

### Updated Mapping Table

| Ralph Concept | FCC-Native Target | Status | Phase |
|---|---|---|---|
| Agent/Model roles | `core/ralph/roles.py` | ✅ | 1 |
| Run table | `core/ralph/run_table.py` | ✅ | 1 |
| Scoring | `core/ralph/scoring.py` | ✅ | 1 |
| Verification plans | `core/ralph/verification.py` | ✅ | 1 |
| Loop guard | `core/ralph/loop_guard.py` | ✅ | 1 |
| **Model role routing** | **`core/ralph/model_router.py`** | **✅** | **2** |
| **Task planner** | **`core/ralph/planner.py`** | **✅** | **2** |
| **Verification runner** | **`core/ralph/verification_runner.py`** | **✅** | **3** |
| **Smoke adapter** | **`core/ralph/smoke_adapter.py`** | **✅** | **3** |
| **Critic/arbiter** | **`core/ralph/critic.py`, `arbiter.py`** | **✅** | **3** |
| **Quality gate** | **`core/ralph/quality_gate.py`** | **✅** | **3** |
| Task library | `core/ralph/task_library.py` | — | 4 |
| Context builder | `core/ralph/context_builder.py` | — | 4 |
| Memory store | `core/ralph/memory.py` | — | 4 |
| Agent profiles | `core/ralph/profiles/` | — | 4 |
| Full Ralph Loop | `core/ralph/loop.py` | — | 8 |
