# Phase 9.8 — Persistent Docker VegaClaw Runtime Lab

## 1. Summary

A persistent Docker runtime lab was created for VegaClaw at
`C:\vega-claw-docker-lab` with the persistent container `vegaclaw-lab`.
The container was built from a lean `python:3.13-slim-bookworm` base image
with uv, git, curl, jq, and procps. The VegaClaw repository was cloned,
baseline tests were run (585 passed, 2 pre-existing Windows-only failures),
and a calculator self-pilot was executed in dry-run mode via `fcc-ralph`.

## 2. Why persistent Docker lab was created

The persistent lab provides a clean, isolated, and reproducible Linux runtime
environment for running VegaClaw's `fcc-ralph` tool. It avoids polluting the
host Windows system with Python virtual environments and guarantees consistent
behavior across runs. The container is long-lived (`restart: unless-stopped`)
so that state and caches are preserved between sessions.

## 3. DeepSeek/API configuration method

API configuration is injected via a local-only Docker env file:

- File: `C:\vega-claw-docker-lab\.env.local`
- Provider: `deepseek`
- Model: `deepseek/deepseek-v4-pro`
- Auth token: `freecc` (internal FCC auth)
- Port: `8082` (inside container), mapped to host port `8092`

The env file is mounted into the container via `docker-compose.yml`
`env_file` directive. It is never committed to any Git repository.

## 4. Env file path

```
C:\vega-claw-docker-lab\.env.local
```

## 5. Docker container name and status

| Property | Value |
|---|---|
| Container name | `vegaclaw-lab` |
| Image | `vega-claw-docker-lab-vegaclaw-lab` |
| Status | `Up` (running) |
| Created | 2026-05-29T09:55:26 UTC |
| Host port mapping | `0.0.0.0:8092 -> 8082/tcp` |
| Restart policy | `unless-stopped` |
| Removed after run | **No** — container is persistent |

## 6. Docker image build result

The Dockerfile was built in two attempts. The first included `nodejs` and
`npm` packages which triggered an enormous Debian dependency chain (hundreds
of packages, mostly Node.js build tooling). The second attempt removed those
packages, resulting in a lean image with only the essentials:

- Python 3.13-slim-bookworm (base)
- git, curl, ca-certificates, jq, procps
- uv 0.11.17 (from ghcr.io/astral-sh/uv:latest)

Build completed successfully in approximately 6 minutes (mostly apt download
time on the Debian repository).

## 7. Bootstrap result

The bootstrap script:

1. Cloned the VegaClaw repository from
   `https://github.com/salehmohamadkhani/vega_claude.git` (branch `master`)
2. Ran `uv sync` — 76 packages installed, virtual environment created
3. Ran `python -m py_compile` — all modules compiled
4. Ran `uv run ty check core/ralph` — **all checks passed**
5. Ran `uv run pytest tests/core/ralph -q` — **585 passed, 2 failed**
6. Ran `uv run fcc-ralph --help` — **CLI help printed successfully**

The 2 test failures are pre-existing Windows-specific path tests
(`test_drive_root_is_system_root`, `test_system_root_blocked`) that fail on
Linux because they test `C:\` drive root resolution. They are not real bugs.

## 8. Baseline test results inside container

| Test suite | Result |
|---|---|
| `py_compile` | **PASS** |
| `ty check core/ralph` | **All checks passed** |
| `pytest tests/core/ralph` | 585 passed, 2 Windows-specific failures |
| `fcc-ralph --help` | **Works** |

## 9. Calculator self-pilot plan/review/approve/status result

### Plan

The planner generated 4 tasks with 5 KPIs:

| Task ID | Title | Role |
|---|---|---|
| TASK-001-context-map | Architecture and context mapping | architect |
| TASK-002-implementation | Implementation | doer |
| TASK-003-verification | Verification and testing | verifier |
| TASK-004-docs-report | Documentation and report | summarizer |

KPIs:
- Calculator can add two numbers correctly
- Calculator can subtract two numbers correctly
- Calculator can multiply two numbers correctly
- Calculator can divide two numbers correctly
- All generated files stay inside the pilot workspace

### Review

All 4 tasks were reviewed with acceptance criteria, verification commands, and
KPI checks attached. Output was valid JSON.

### Approve

All 4 tasks approved in a single `approve --all` command.

### Status

Workspace reports: 4 tasks, all approved, 8 profiles loaded, 1 checkpoint
created, no runs previously completed.

## 10. Dry-run loop result

The dry-run loop ran 1 iteration of TASK-001-context-map (architecture
mapping). The critic/arbiter determined the task needed debugging (expected
behavior in dry-run mode — no real execution was performed). The loop stopped
with `debug_required: true`.

This is the correct behavior: in dry-run mode, the runtime simulates
execution but cannot produce real artifacts, so the critic correctly marks
the task as needing debug.

## 11. Report result

The `fcc-ralph report` command generated a report file at:

```
/tmp/vega-calculator-pilot/.fcc-ralph/reports/report-00dab7c8.md
```

The report summarizes: 4 tasks total, 3 approved, 1 needs-fix, 2 checkpoints.

## 12. Real execution availability

The `claude` CLI is not available inside the container (`which claude` returns
empty). Real execution mode (`--mode real`) requires the Claude CLI or another
execution backend to be installed inside the container, which is not configured
in this phase.

**Blocker:** Real execution is not available inside the container because:
- No `claude` CLI is installed in the Docker image
- Real execution was intentionally not attempted in this phase

## 13. Pilot workspace file list

All generated files remained inside `/tmp/vega-calculator-pilot/`:

```
/tmp/vega-calculator-pilot/.fcc-ralph/checkpoints/
/tmp/vega-calculator-pilot/.fcc-ralph/context/
/tmp/vega-calculator-pilot/.fcc-ralph/goals/
/tmp/vega-calculator-pilot/.fcc-ralph/memory/
/tmp/vega-calculator-pilot/.fcc-ralph/reports/
/tmp/vega-calculator-pilot/.fcc-ralph/runs/
/tmp/vega-calculator-pilot/.fcc-ralph/tasks/
```

All files are FCC-Ralph internal metadata (checkpoints, goals, memory, runs,
tasks). No actual calculator HTML/CSS/JS files were created because the
dry-run loop stopped at the architecture task.

## 14. VegaClaw repo cleanliness inside container

The VegaClaw repository inside the container is **clean** — `git status
--short` returns empty output. No files were modified or created in the
workspace repo by the self-pilot.

## 15. Logs location

Host-side logs (Docker volume mounted at `./logs:/logs`):

```
C:\vega-claw-docker-lab\logs\bootstrap.log              (5,659 bytes)
C:\vega-claw-docker-lab\logs\calculator-self-pilot.log  (5,778 bytes)
```

Both logs were captured by `tee` inside the container and persist on the host
via the Docker volume mount.

## 16. Container kept alive

Yes — the container `vegaclaw-lab` is still running with `restart:
unless-stopped`. It has not been removed and will persist for future sessions.

## 17. Remaining blockers

1. **Real execution unavailable** — No `claude` CLI inside container.
   Installing the Claude CLI or configuring an alternative execution backend
   is needed for `--mode real` to work.

2. **2 pre-existing test failures** — `test_drive_root_is_system_root` and
   `test_system_root_blocked` fail on Linux. These are Windows-only tests
   that should be conditionally skipped on non-Windows platforms. They do
   not affect VegaClaw's core functionality.

3. **Dry-run loop stops at debug** — The critic/arbiter correctly rejects
   dry-run execution because no real artifacts are produced. This is expected
   behavior until `--mode real` is available.

## 18. Recommended next step

- Install the `claude` CLI inside the Docker image for `--mode real` support
- Alternatively, configure DeepSeek provider routing to skip the Claude CLI
  requirement and attempt a real execution run inside the container
- Optionally mark the 2 Windows-only tests to skip on Linux
- Consider reducing `--max-iterations` or adjusting the critic threshold
  to allow dry-run loops to complete without debug intervention

## Files

| File | Path |
|---|---|
| Dockerfile | `C:\vega-claw-docker-lab\Dockerfile` |
| docker-compose.yml | `C:\vega-claw-docker-lab\docker-compose.yml` |
| bootstrap.sh | `C:\vega-claw-docker-lab\bootstrap.sh` |
| Self-pilot script | `C:\vega-claw-docker-lab\run-calculator-self-pilot.sh` |
| Env file | `C:\vega-claw-docker-lab\.env.local` |
| Bootstrap log | `C:\vega-claw-docker-lab\logs\bootstrap.log` |
| Self-pilot log | `C:\vega-claw-docker-lab\logs\calculator-self-pilot.log` |
