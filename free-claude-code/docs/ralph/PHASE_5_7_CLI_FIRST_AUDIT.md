# Phase 5.7 Report — CLI-First Roadmap Correction and Execution Contract Audit

> **Date**: 2026-05-26
> **Status**: Complete — no code changes, all checks clean

## Summary

Phase 5.7 is a documentation and audit phase. It corrects the roadmap to be CLI-first (not Admin UI-first), inspects FCC's CLI registration mechanism, audits execution contracts for CLI safety, and creates a technical plan for Phase 6. No code was written.

## Roadmap Corrections

### Problem

Multiple documents referenced an outdated roadmap where Admin UI was Phase 5/6, before CLI. This conflicted with the direction set in Phase 5.5 and Phase 5.6 (which positioned CLI as Phase 6, Admin UI as Phase 7+).

### Documents Updated

| Document | Correction |
|---|---|
| `FCC_RALPH_RUNTIME_ARCHITECTURE.md` | "What Remains for Phase 6+" table: Admin UI moved to Phase 7, CLI added as Phase 6. Older roadmap updated: Phase 6 = CLI, Phase 7 = Admin UI (post-CLI), Phase 8 = Full Ralph Loop, Phase 9 = Playwright. |
| `FCC_RALPH_FEATURE_MAP.md` | Admin UI capability entries shifted from Phase 6 to Phase 7. Mapping table updated for CLI-first ordering. |
| `PHASE_4_REPORT.md` | "Phase 4 prepares Phase 5 (Admin UI)" changed to "Phase 4 prepares the Ralph Loop (Phase 6+)". |
| `PHASE_4_5_AUDIT_REPORT.md` | "Phase 4.5 hardening makes Phase 5 (Admin UI) safer" changed to "Phase 4.5 hardening makes future UI layers safer (Phase 7+)". |
| `PHASE_1_REPORT.md` | "No Admin UI (Phase 4)" changed to "No Admin UI (Phase 7+)". |
| `PHASE_2_REPORT.md` | "No Admin UI (Phase 4)" changed to "No Admin UI (Phase 7+)". |
| `PHASE_3_REPORT.md` | "No Admin UI (Phase 5)" changed to "No Admin UI (Phase 7+)". |
| `PHASE_3_5_REPORT.md` | "No Admin UI (Phase 5)" changed to "No Admin UI (Phase 7+)". |

### Current Roadmap

```
Phase 5.6 [DONE]    Execution lifecycle — IterationRunnerConfig, allowlist, config validation
                        ↓
Phase 5.7 [DONE]    CLI-first audit — roadmap correction, execution contract audit, CLI plan
                        ↓
Phase 6             CLI surface for Ralph Runtime — fcc-ralph plan/review/approve/run/status/report
                        ↓
Phase 7             Admin UI for Ralph Runtime, KPI dashboard (post-CLI, optional)
                        ↓
Phase 8             Full Ralph Loop with Claude Code via FCC proxy
                        ↓
Phase 9             Playwright KPI verifier, browser-based acceptance testing
```

Admin UI is explicitly postponed to Phase 7 — after CLI is stable. It is marked as optional: the runtime must work through CLI alone.

## FCC CLI Structure

### How FCC Registers Commands

In `pyproject.toml`, CLI entry points are registered under `[project.scripts]`:

```toml
[project.scripts]
fcc-server = "cli.entrypoints:serve"
free-claude-code = "cli.entrypoints:serve"
fcc-init = "cli.entrypoints:init"
fcc-claude = "cli.entrypoints:launch_claude"
```

Each maps a shell command (`fcc-<name>`) to a Python function reference (`module:function`). The hatchling build backend generates console scripts from these during `pip install`.

### CLI Module Structure

| File | Purpose |
|---|---|
| `cli/__init__.py` | Package init |
| `cli/entrypoints.py` | `serve()`, `init()`, `launch_claude()` — the registered CLI commands |
| `cli/manager.py` | CLI session manager |
| `cli/process_registry.py` | PID tracking and cleanup |
| `cli/session.py` | Session management |

### Pattern for `fcc-ralph`

The Phase 6 `fcc-ralph` CLI will follow the same pattern:

1. Create `cli/ralph.py` (or `core/ralph/cli.py`) with subcommand functions
2. Register in `pyproject.toml` as `fcc-ralph = "core.ralph.cli:main"` or `fcc-ralph = "cli.ralph:main"`
3. Use `argparse` or `click`/`typer` for subcommand routing

## Execution Contract Audit — CLI Safety

Each safety property was verified against the current codebase.

| Property | Status | Verified By |
|---|---|---|
| Default dry-run | ✅ | `ExecutionConfig(dry_run=True, allow_real_execution=False)` |
| Real execution requires explicit opt-in | ✅ | Two-level gate: `IterationRunnerConfig(execution_mode=...)` + `ExecutionConfig(allow_real_execution=True)` |
| PENDING tasks blocked by default | ✅ | `RunExecutorConfig(auto_approve_pending_tasks=False)` |
| Only APPROVED tasks run | ✅ | `_find_next_task()` only returns PENDING/APPROVED; PENDING blocked by approval gate |
| RETRY/DEBUG/ESCALATE states structured | ✅ | `RunExecutorResult` with `retry_required`, `debug_required`, `escalation_required` |
| No provider/API key ownership | ✅ | Zero imports of `anthropic`, `openai`, `requests`, `httpx` in `core/ralph/` |
| No `/v1/messages` modifications | ✅ | Ralph Runtime never imports or references API routes |
| No `shell=True` | ✅ | All subprocess calls use `shell=False` (verified by grep) |
| Command allowlist enforced | ✅ | `_is_command_allowed()` with basename matching, `.exe` variants |
| Output truncation | ✅ | `max_output_chars` caps stdout/stderr |
| Timeout enforcement | ✅ | `subprocess.run(timeout=...)` |
| Checkpoint isolation | ✅ | All state under `.fcc-ralph/` with path traversal protection |

**Conclusion: The Ralph execution contracts are safe for CLI exposure.** No additional hardening is needed before Phase 6.

## Tests Run

```
$ uv run pytest tests/core/ralph -q           → 391 passed
$ uv run ruff check core/ralph tests/core/ralph → All checks passed
$ python -m py_compile core/ralph/*.py         → All compile OK
```

## Safety Grep Results

```
$ grep -R "shell=True" core/ralph tests/core/ralph
  → Only in docstrings (intentional "Never uses shell=True")

$ grep -R "requests\|httpx\|aiohttp\|socket\|providers\|ANTHROPIC_API_KEY\|OPENAI_API_KEY\|COPILOT\|copilot" core/ralph tests/core/ralph
  → No matches

$ grep -R "Phase 6.*Admin UI\|Phase 6.*dashboard\|next phase.*Admin UI" docs/ralph
  → No matches (confirming roadmap is clean)
```

## Phase 6 CLI Safety

**Yes, Phase 6 CLI is safe to start.** The execution contracts are fully hardened:

- `fcc-ralph run` will invoke `RunExecutor` with safe defaults (dry-run)
- `fcc-ralph approve` will call `RunLifecycle.approve_task()`
- `fcc-ralph review` will display pending tasks
- Real execution requires deliberate opt-in by the user
- All arbiter actions (RETRY/DEBUG/ESCALATE/STOP) produce structured results the CLI can display
- No provider keys, no API routes, no shell injection risks

See `PHASE_6_CLI_PLAN.md` for the full technical plan.

## Files Changed

| File | Change |
|---|---|
| `docs/ralph/PHASE_5_7_CLI_FIRST_AUDIT.md` | Created — this report |
| `docs/ralph/PHASE_6_CLI_PLAN.md` | Created — Phase 6 CLI technical plan |
| `docs/ralph/FCC_RALPH_RUNTIME_ARCHITECTURE.md` | Roadmap corrected to CLI-first, "What Remains" table updated |
| `docs/ralph/FCC_RALPH_FEATURE_MAP.md` | Capability phases updated for CLI-first ordering |
| `docs/ralph/PHASE_4_REPORT.md` | Admin UI → Phase 7+ references |
| `docs/ralph/PHASE_4_5_AUDIT_REPORT.md` | Admin UI → Phase 7+ references |
| `docs/ralph/PHASE_1_REPORT.md` | Admin UI → Phase 7+ references |
| `docs/ralph/PHASE_2_REPORT.md` | Admin UI → Phase 7+ references |
| `docs/ralph/PHASE_3_REPORT.md` | Admin UI → Phase 7+ references |
| `docs/ralph/PHASE_3_5_REPORT.md` | Admin UI → Phase 7+ references |

## Commit

```
e5fab2f Phase 5.6: Execution lifecycle hardening before CLI
e5fab2f..<new> Phase 5.7: Realign Ralph roadmap around CLI before UI
```
