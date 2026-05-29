# Phase 9.6 — Docker Self-Pilot Repair Report

## Summary

Repaired and re-ran the Docker-based calculator self-pilot flow for the VegaClaw
persistent lab environment after two blocking issues emerged during the initial
Phase 9.5 run.

## Issues Found and Fixed

### Issue 1 — Python 2-style exception syntax (3 files)

Three runtime modules used `except SomeError, e:` (Python 2 syntax) instead of
`except SomeError as e:` (Python 3 syntax). This caused `SyntaxError` on Python
3.13 inside the Docker container.

**Files fixed:**

| File | Line | Fix |
|---|---|---|
| `core/ralph/context_builder.py` | 227 | `except Exception, e:` → `except Exception as e:` |
| `core/ralph/memory.py` | 257 | `except Exception, e:` → `except Exception as e:` |
| `core/ralph/task_library.py` | 244 | `except FileNotFoundError, e:` → `except FileNotFoundError as e:` |

### Issue 2 — Docker uv version mismatch

The Dockerfile used `uv` from PyPI which lagged behind the version expected by
the project's `uv.lock`. Fixed by switching to the official astral-sh `uv`
Docker image layer:

```dockerfile
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
```

This ensured uv >= 0.11.0 was available inside the container, matching the
project lock file requirements.

## Docker Build Result

- Docker build completed successfully.
- Container `vegaclaw-lab` started and remained running.

## Container Bootstrap Result

- Repository cloned successfully inside container.
- `py_compile` passed for all core modules.
- `uv run ruff check` passed.
- `uv run pytest tests/core/ralph` passed (587 tests).
- `uv run fcc-ralph --help` printed CLI help successfully.

## Calculator Self-Pilot Flow

The calculator self-pilot was run in dry-run mode inside the Docker container:

| Step | Result |
|---|---|
| `plan` | Passed — task plan generated for calculator app with 4 KPIs |
| `review` | Passed — tasks reviewed successfully |
| `approve --all` | Passed — all pending tasks approved |
| `status` | Passed — workspace status reported correctly |
| `run --loop --verify --max-iterations 2` | Needed re-run due to `--json` placement issue |
| `report` | Passed — run report generated |

The `--json` flag placement caused the loop runner to treat subsequent arguments
incorrectly on first attempt. Re-running with correct flag ordering resolved the
issue.

## Remaining Observations

- Dry-run mode is confirmed working inside the persistent container.
- All generated files stayed within the pilot workspace (no repo contamination).
- Real execution (`--mode real`) was not attempted in this phase.
- API key was present and verified via env file injection.

## Logs

All logs are captured at:

```
C:\vega-claw-docker-lab\logs\bootstrap.log
C:\vega-claw-docker-lab\logs\calculator-self-pilot.log
```

## Next Step

Proceed with the Phase 9.8 persistent Docker lab setup at the canonical
VegaClaw path `C:\Users\saleh\Projects\free-claude-code`.
