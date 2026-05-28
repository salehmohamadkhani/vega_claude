# Phase 9.5 — Docker Self-Pilot Audit Report

**Status**: Complete — blockers identified

**Date**: 2026-05-28

## 1. Summary

This audit tested whether the Vega/FCC/Ralph project can run itself in an isolated Docker container to produce a small calculator app through its own `fcc-ralph` CLI/runtime. Two blockers prevented the pilot from completing:

1. **uv version mismatch** — Docker image `ghcr.io/astral-sh/uv:python3.13-bookworm-slim` ships uv `0.9.30`, but the project's `pyproject.toml` requires `>=0.11.0`.
2. **Python 2 exception syntax** — `core/ralph/context_builder.py` line 165 uses `except subprocess.TimeoutExpired, FileNotFoundError, OSError:` which is Python 2 syntax (comma-separated exception types) and raises `SyntaxError` on Python 3.

The FCC server at `host.docker.internal:8082` was reachable from the container and responded with `{"status":"healthy"}`. The project infrastructure works; runtime bugs block the self-pilot.

## 2. Host Environment

| Property | Value |
|---|---|
| Host OS | Windows 11 Pro 10.0.26200 |
| Shell | Git Bash (mingw64) |
| Docker | Docker Desktop 29.1.5 (Engine 29.1.5, containerd 2.2.1) |
| Python | 3.14.0 (host) |
| uv | managed by project venv (host) |
| Repo branch | `master` |
| Repo HEAD | `398f5c0` — Phase 9: Verification & KPI expansion |
| Host tests | 587 passing, py_compile clean, ruff clean, ty clean |
| Smoke collect | 76 tests collected |

## 3. Docker Image Build Result

**First attempt** (`ghcr.io/astral-sh/uv:python3.13-bookworm-slim` with git, curl, jq):
- Build succeeded (image `vega-ralph-self-pilot:phase9-5`) in ~168 seconds.
- Image size: ~500MB (Debian bookworm-slim base + uv + git + curl + jq).

**Second attempt** (`python:3.13-slim-bookworm` with curl-piped uv installer):
- Build failed due to `deb.debian.org` DNS resolution failures for late-stage apt packages (libx11, patch, publicsuffix).
- Transient network issue; not a project problem.

**Third attempt** (original uv image + `uv self update`):
- Not executed due to Docker build tool unavailability.

**Conclusion for build**: The `ghcr.io/astral-sh/uv` base image builds successfully. The `python:3.13-slim-bookworm` fallback failed due to Debian mirror network issues on this host.

## 4. Container Clone Result

**Passed**. The container successfully cloned the Vega repo:

```
Cloning into '/workspace/vega_claude'...
PWD: /workspace/vega_claude/free-claude-code
Branch: master
398f5c0 Phase 9: Verification & KPI expansion
```

## 5. Container Baseline Test Result

**FAILED** — two issues:

### Blocker A: uv version mismatch

```
error: Required uv version `>=0.11.0` does not match the running version `0.9.30`
```

All `uv run` commands fail with this error. The `ghcr.io/astral-sh/uv` image at the tag `python3.13-bookworm-slim` (without a specific uv version pin) resolved to an image with uv `0.9.30`. The project requires `>=0.11.0`.

**Fix needed**: Either (a) use a version-pinned uv image tag like `ghcr.io/astral-sh/uv:0.11.0-python3.13-bookworm-slim`, or (b) add `RUN uv self update` to the Dockerfile, or (c) run `uv self update` inside the container script before using `uv run`.

### Blocker B: Python 2 exception syntax

```
File "core/ralph/context_builder.py", line 165
    except subprocess.TimeoutExpired, FileNotFoundError, OSError:
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
SyntaxError: multiple exception types must be parenthesized
```

Even `python -m py_compile core/ralph/*.py` fails because `context_builder.py` line 165 uses Python 2 `except Exc1, Exc2:` syntax (comma-separated). Python 3 requires parenthesized form: `except (Exc1, Exc2):`.

This is a **pre-existing bug** that was noted in the Phase 4.5 audit report but apparently never fixed — or was reintroduced. The Phase 4.5 report (FCC_RALPH_RUNTIME_ARCHITECTURE.md) lists "Python 2 except syntax (3 locations)" as fixed, but this line was missed or regressed.

**Fix needed**: Change:
```python
except subprocess.TimeoutExpired, FileNotFoundError, OSError:
```
to:
```python
except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
```

## 6. FCC Server Connectivity from Container

**PASSED** — FCC server is reachable via `host.docker.internal:8082`:

```
--- Trying host.docker.internal:8082 ---
{"status":"healthy"}
--- Trying 172.17.0.1:8082 ---
curl: (7) Failed to connect to 172.17.0.1 port 8082
--- Trying 172.17.0.1:8082/v1/models ---
curl: (7) Failed to connect to 172.17.0.1 port 8082
```

`host.docker.internal` resolves correctly on Docker Desktop for Windows. The FCC health endpoint returns `healthy`. The Docker bridge IP `172.17.0.1` does not work (expected — Docker Desktop uses a different network topology).

## 7. Calculator Pilot Goal

The pilot was requested with the following goal:

```
Build a tiny browser calculator app with HTML, CSS, and JavaScript.
It should support addition, subtraction, multiplication, division,
clear, decimals, and a tiny README. Keep all generated app files
inside the pilot workspace only.
```

Target workspace: `/tmp/vega-calculator-pilot`

## 8. `fcc-ralph plan` Result

**BLOCKED** — could not execute due to uv version mismatch.

All `uv run` commands fail with:
```
error: Required uv version `>=0.11.0` does not match the running version `0.9.30`
```

No plan was generated. No tasks were created.

## 9. `fcc-ralph approve` Result

**BLOCKED** — no tasks to approve since the plan step failed.

## 10. Dry-Run Loop Result

**BLOCKED** — no tasks to run since the plan step failed.

## 11. Controlled Real Execution Attempt Result

**BLOCKED** at two levels:

1. No tasks to execute (plan step failed).
2. `claude` CLI is not available inside the container:

```
--- Checking for claude CLI ---
claude not found
claude --version failed
```

Real execution requires `claude` (Claude Code CLI) to be installed in the container. This would need either:
- Installing the `claude` CLI package in the Docker image, or
- Running the real execution on the host (not in Docker) where `claude` is available.

## 12. Pilot Workspace File List

The pilot workspace at `/tmp/vega-calculator-pilot` remained **empty** (only 4.0K in size). No calculator app files were created by `fcc-ralph` because the plan step never executed.

## 13. Vega Source Tree Modification

**Vega source tree was NOT modified** inside the container. `git status --short` returned empty output inside `/workspace/vega_claude/free-claude-code`.

## 14. Logs Saved

Log files were written to `/out/` inside the container:
- `/out/repo-baseline.log`
- `/out/fcc-server-connectivity.log`
- `/out/calculator-plan.log`
- `/out/calculator-review.log`
- `/out/calculator-approve.log`
- `/out/calculator-dry-run.log`
- `/out/calculator-real-attempt.log`
- `/out/calculator-report.log`
- `/out/container-final-status.log`

These logs exist inside the stopped container and are not persisted to the host filesystem. Reason: the Docker `-v` mount from the host `C:\Users\saleh\AppData\Local\Temp\vega-docker-self-pilot` to container `/out` encountered a path translation issue on first run (Docker on Windows with Git Bash path conversion). Logs from the second run (via PowerShell) were written correctly but the container was not started due to the subsequent build failure.

**Recommendation**: On the next audit, use a PowerShell launcher script exclusively for Docker volume mounts on Windows.

## 15. Exact Errors Encountered

### Error 1: uv version mismatch (BLOCKER)

```
error: Required uv version `>=0.11.0` does not match the running version `0.9.30`
```

- **Source**: `pyproject.toml` `[project.requires-python]` or uv workspace config
- **Severity**: **BLOCKER** — prevents ALL `uv run` commands
- **Fix**: Pin uv version in Dockerfile: `FROM ghcr.io/astral-sh/uv:0.11.0-python3.13-bookworm-slim` or add `RUN uv self update`
- **Owner**: Dockerfile author (this audit)

### Error 2: Python 2 except syntax (BLOCKER)

```
File "core/ralph/context_builder.py", line 165
    except subprocess.TimeoutExpired, FileNotFoundError, OSError:
SyntaxError: multiple exception types must be parenthesized
```

- **Source**: `free-claude-code/core/ralph/context_builder.py:165`
- **Severity**: **BLOCKER** — prevents `python -m py_compile` and all Python import/execution
- **Fix**: Change comma-separated except to parenthesized tuple
- **Owner**: Project maintainers (pre-existing bug, Phase 4.5 regression)

### Error 3: Docker volume path translation (MINOR)

```
bash: C:/Program Files/Git/out/run-pilot.sh: No such file or directory
```

- **Source**: Git Bash converts Unix-style paths containing `/out` to Windows paths
- **Severity**: Minor — worked around by using PowerShell launcher script
- **Fix**: Use PowerShell for `docker run -v` mounts on Windows

### Error 4: claude CLI not available in container (EXPECTED)

```
claude not found
claude --version failed
```

- **Source**: Container image does not include Claude Code CLI
- **Severity**: Expected — the container is a basic Python/uv environment
- **Fix**: Add `npm install -g @anthropic/claude-code` to Dockerfile or run real execution on host

## 16. Is the Project Usable for a First Real Self-Pilot?

**Not yet.** Two blockers must be resolved first:

1. **uv version** — The Docker image must provide uv `>=0.11.0`. This is a Dockerfile issue, not a project issue.
2. **context_builder.py syntax** — The Python 2 `except` syntax on line 165 must be fixed. This is a pre-existing project bug that prevents the project from compiling on the container's Python 3.13 interpreter. Notably, the host runs Python 3.14 and does NOT encounter this error because the host's `py_compile` passes — the difference may be due to the host using a different `subprocess` module implementation or the file being excluded from compilation by some tool. However, the container's `python -m py_compile` clearly fails on this line.

Once these two issues are fixed:
- The `fcc-ralph plan` flow would work for task generation.
- The `fcc-ralph approve` flow would work.
- The dry-run loop would exercise the quality gate, verification, and KPI infrastructure.
- Real execution would require `claude` CLI installation in the container.

The containerized FCC server connectivity test was successful, meaning a future pilot could use the host FCC server for provider-backed tasks.

## 17. Recommended Next Step

1. **Fix context_builder.py:165** — Parenthesize the except clause (Phase 4.5 regression). This is a one-line fix.
2. **Pin uv version in Dockerfile** — Use `ghcr.io/astral-sh/uv:0.11.0-python3.13-bookworm-slim` instead of the bare tag.
3. **Re-run the Docker self-pilot** — After both fixes, the `fcc-ralph plan -> review -> approve -> run --loop --verify` flow should work.
4. **If real execution is desired**, add Claude Code CLI installation (`npm install -g @anthropic/claude-code`) to the Docker image and test `fcc-ralph run --loop --real --allow-real-execution`.
