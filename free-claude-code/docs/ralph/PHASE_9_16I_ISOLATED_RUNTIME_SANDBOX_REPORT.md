# Phase 9.16I — Isolated Runtime Sandbox for Real VegaClaw Backtests

**Date:** 2026-05-30
**Status:** COMPLETE
**Operator:** SPC (Ralph Runtime)
**Predecessor:** Phase 9.16H (Evidence-Gated Runtime Backtest, `4a7057c`)
**Successor:** Phase 9.16J (TBD)

---

## 1. Why Phase 9.16I Exists

Before this phase, all Agent Council tests used deterministic fixtures and in-memory mocks. No test created real files outside the source tree. This phase creates the sandbox infrastructure needed for future phases to run real project-generation backtests safely, without polluting the VegaClaw source tree.

The sandbox ensures:
- Generated files live outside `/opt/vega-cloud/vega_claude/free-claude-code`
- Every run has a timestamped isolated directory
- Forbidden runtime artifacts are detected and rejected
- Artifacts can be collected and validated deterministically
- Evidence gates can inspect real sandbox output

## 2. Current SPC/VegaClaw Route

- **SPC**: Healthy on `127.0.0.1:18083`
- **Port 8082**: Untouched
- **VegaClaw**: `4a7057c` at HEAD, `HEAD == origin/master`

## 3. Docker Availability Result

```
Docker version 29.1.3, build 29.1.3-0ubuntu3~22.04.2
```

**Docker is available.** Designed for Docker-first mode with host-native fallback.

## 4. Chosen Sandbox Mode

**Docker-first with host-native fallback.**

- `resolve_sandbox_root()` checks `/opt/vega-cloud/sandboxes` (intended) then `/tmp/vega-sandboxes` (fallback).
- Actual sandbox root used: `/tmp/vega-sandboxes` (SPC operator lacks write access to `/opt/vega-cloud` which is owned by `vegaops`).
- Recommended: grant SPC write access to `/opt/vega-cloud/sandboxes` in a future infrastructure task.

## 5. Sandbox Root Structure

```
/tmp/vega-sandboxes/           ← active root (host-native)
  runs/                        ← timestamped run directories
    vegaclaw-backtest-20260530-153544/
      manifest.json
      output.md                ← fixture output
  templates/                   ← reusable project templates
  logs/                        ← sandbox run logs
  reports/                     ← generated reports
  trash/                       ← cleaned-up runs (moved, not deleted)
```

### Intended root (Docker-first, requires permissions):

```
/opt/vega-cloud/sandboxes/     ← intended root
  runs/
  templates/
  logs/
  reports/
  trash/
```

## 6. Sandbox Manager Design

### `core/ralph/agent_council/runtime_sandbox.py`

| Function | Purpose |
|---|---|
| `resolve_sandbox_root(requested)` | Return the active sandbox root (intended → fallback) |
| `create_sandbox_run_dir(root, prefix)` | Create a timestamped isolated run directory |
| `write_sandbox_manifest(run_dir, manifest)` | Write manifest.json to run directory |
| `read_sandbox_manifest(run_dir)` | Read manifest.json (None if missing) |
| `collect_sandbox_artifacts(run_dir)` | Walk directory, catalog files, detect forbidden/empty |
| `validate_sandbox_cleanliness(run_dir)` | Check for violations, empty files, unusual extensions |
| `summarize_sandbox_run(run_dir)` | Human-readable multi-line summary |
| `create_backtest_run(project_type, goal, ...)` | One-call: create run dir + manifest |
| `cleanup_sandbox_run(run_dir, move_to_trash)` | Remove or trash a run directory |

### Data Models

- **`SandboxManifest`** — run_id, phase, project_type, project_goal, created_at, operator, sandbox_mode, sandbox_root, allowed_output_paths, forbidden_paths, expected_artifacts, verification_commands, evidence_gate_mode, docker_image, docker_command, notes
- **`SandboxArtifactReport`** — run_dir, run_id, files_found, files_empty, files_large, files_forbidden, extensions_found, total_files, total_size_bytes, manifest_valid, sandbox_clean, violations, warnings

## 7. Manifest Schema

```json
{
  "run_id": "vegaclaw-18f3a2b4c",
  "phase": "9.16i-smoke",
  "project_type": "landing_page",
  "project_goal": "Build a whiteboard landing page",
  "created_at": "2026-05-30T15:35:44.123456+00:00",
  "operator": "SPC",
  "sandbox_mode": "host-native",
  "sandbox_root": "/tmp/vega-sandboxes",
  "allowed_output_paths": ["/tmp/vega-sandboxes/runs/vegaclaw-backtest-20260530-153544"],
  "forbidden_paths": [".fcc/", ".fcc-ralph/", ".claude/", ".env", ...],
  "expected_artifacts": [],
  "verification_commands": [],
  "evidence_gate_mode": "warning"
}
```

## 8. Artifact Collection Rules

`collect_sandbox_artifacts()` walks the run directory and:
- Lists all files found (excluding `manifest.json`)
- Detects empty files (size == 0 bytes)
- Detects forbidden paths matching any of 11 patterns
- Tracks file extensions with counts
- Computes total size in bytes
- Returns violations and warnings as sorted lists

## 9. Forbidden Path Rules

11 forbidden patterns (same as evidence gate `runtime_artifact_exclusion_gate`):
`.fcc/`, `.fcc-ralph/`, `.claude/`, `.env`, `.git-credentials`, `secrets`, `credentials`, `raw_research_repos`, `/opt/vega-cloud/research/repos`, `server_tracker`, `logs/`

These are checked in both `collect_sandbox_artifacts()` and `_extract_staged_violations()` in the runtime gate enforcer.

## 10. Evidence Gate Integration Point

Sandbox artifacts can feed into evidence gates via:
1. `collect_sandbox_artifacts()` provides `files_found` → can be used as `changed_files` in task result
2. `validate_sandbox_cleanliness()` detects forbidden paths → mapped to `runtime_artifact_exclusion_gate`
3. `enforce_runtime_evidence_gates()` accepts task result dicts with `changed_files` → extracts evidence bindings → runs all 12 gates

## 11. CLI Integration Status

### IMPLEMENTED: `fcc-ralph sandbox-smoke`

```bash
fcc-ralph sandbox-smoke --project-type landing_page --goal "Build a whiteboard landing page"
fcc-ralph sandbox-smoke --project-type full_stack_app --goal "Build a CRM" --strict --json
```

Behavior:
- Creates a timestamped sandbox run directory
- Writes manifest.json
- Creates a deterministic fixture output file (`output.md`)
- Runs artifact collection and cleanliness validation
- Runs evidence gates against the fixture
- Prints summary (or JSON)
- Exits non-zero if sandbox is dirty or gates block approval

## 12. Tests Added

| Test File | Tests | Coverage |
|---|---|---|
| `tests/core/ralph/test_agent_council_runtime_sandbox.py` | 33 | Directory creation, manifest write/read, artifact collection, forbidden path detection (7 patterns), cleanliness validation, summary, backtest convenience, evidence gate integration, cleanup, no-network |

## 13. What Is Intentionally Not Implemented Yet

- **Docker container mode** — Docker is available but not yet used. The `runtime_sandbox.py` supports a `docker_image` field in the manifest but doesn't execute containers. Phase 9.16J+ will add Docker execution.
- **Real project generation inside sandbox** — The sandbox-smoke command writes a static fixture, not a real generated project. Phase 9.16J will add real generation.
- **Multi-file project scaffolding** — Single-file output only.
- **Write access to `/opt/vega-cloud/sandboxes`** — SPC operator lacks write permissions on the intended root.

## 14. Remaining Risks

| Risk | Severity | Mitigation |
|---|---|---|
| Sandbox in /tmp may be cleaned on reboot | Low | Docker-first mode will use persistent storage; /tmp is fallback |
| No Docker execution yet | Low | Infrastructure ready; Phase 9.16J will add it |
| `/opt/vega-cloud/sandboxes` permissions | Medium | Documented; requires `vegaops` to grant SPC write access |

## 15. Whether Phase 9.16J Is Safe to Start

**Yes — Phase 9.16J (real mini-project sandbox backtest) is safe to start.**

- All 710 council/gate/sandbox/backtest tests pass.
- 1281/1284 full Ralph suite pass (3 pre-existing).
- Sandbox infrastructure is operational.
- CLI `sandbox-smoke` command works end-to-end.
- Docker is available for future container mode.

---

## Phase Roadmap

| Phase | Status | Description |
|---|---|---|
| 9.16A | DONE | Agent Council V2 Core Foundation |
| 9.16B | DONE | Specialized Agent Registry Expansion |
| 9.16C | DONE | Council Plan Generator Integration |
| 9.16D | DONE | Council Plan Task Planning Injection |
| 9.16E | DONE | Agent Council Evidence Gates & Readiness Checks |
| 9.16F | DONE | Runtime Evidence Enforcement & Task Result Binding |
| 9.16G | DONE | CLI Flags & Runtime Loop Wiring for Agent Council Gates |
| 9.16H | DONE | Evidence-Gated Runtime Backtest |
| **9.16I** | **DONE** | **Isolated Runtime Sandbox for Real VegaClaw Backtests** |
| 9.16J | NEXT | TBD |
| 10 | DEFERRED | TBD |
