# U13-DOCKER-LITE — Docker Test Sandbox Report

## Docker Availability

| Check | Result |
|-------|--------|
| Docker installed | yes |
| Docker version | 29.1.3 |
| Docker daemon reachable | yes (socket exists) |
| Docker socket permission | granted — `spcops` in `docker` group |
| Passwordless sudo | not available |
| Docker test run | ✅ PASSED — 107/107 tests passing |
| Dockerfile fixes applied | `pip install` direct (no uv sync fallback), `scripts/` copied into image |

## Files Created

| File | Purpose |
|------|---------|
| `Dockerfile.test` | Python 3.14-slim base image, copies vega_agents + tests, no secrets, no env files |
| `scripts/run_agent_tests_in_docker.sh` | Builds image, runs 4 test files in disposable container |
| `tests/ralph/test_docker_agent_sandbox_contract.py` | Contract tests verifying isolation rules |
| `docs/vega_cloud/U13_DOCKER_TEST_SANDBOX_REPORT.md` | This report |

## Tests Selected

The following agent-related test files are run inside the sandbox:

1. `tests/ralph/test_vega_agent_runtime.py` — registry, selector, escalation
2. `tests/ralph/test_vega_agent_executor.py` — execution plans, fan-out gate
3. `tests/ralph/test_vega_agent_runner_cli.py` — CLI parsing, profile building
4. `tests/ralph/test_vega_agent_blueprints.py` — catalog, search, approval gating

These tests are all stdlib-only — no product imports, no network, no env reads.

## Isolation Rules

The sandbox enforces:

| Rule | Enforcement |
|------|-------------|
| No privileged mode | Contract test verifies `--privileged` is absent from runner script |
| No env file mounting | Contract test verifies `/opt/vega-cloud/env` is absent from runner script |
| No .env copies | Contract test verifies `.env` is absent from Dockerfile |
| Container is disposable | Runner script uses `--rm` |
| No network runtime dependency | Tests are stdlib-only; no network access required |
| No secrets | Dockerfile intentionally omits env file copies |

## Risks

| Risk | Status |
|------|--------|
| **Python 3.14 slim image**: Python 3.14 is under rapid development; the image must be kept current. | Active |
| **pip install reliability**: Direct `pip install pytest pytest-asyncio` — no uv sync fallback needed. | ✅ Stable |
| **Docker daemon dependency**: Build and run require a running Docker daemon on the host. | Active |
| **No service integration tests**: These are unit/contract tests only. Integration tests requiring running services are not covered. | Active |

## How to Run

```bash
# Build image and run tests
bash scripts/run_agent_tests_in_docker.sh

# Or build separately then run
docker build -f Dockerfile.test -t vega-agent-test-sandbox:u13 .
docker run --rm vega-agent-test-sandbox:u13

# Run contract tests
uv run pytest tests/ralph/test_docker_agent_sandbox_contract.py -q
```

## Blocker (Resolved)

| Issue | Detail |
|-------|--------|
| Docker socket permission | `spcops` user was not in the `docker` group. |
| Resolution | `sudo usermod -aG docker spcops` applied by sysadmin. Verified with `sg docker` to work around session-level group cache. |

## Final Marker

U13_DOCKER_SANDBOX_READY — ✅ All 107 tests passed (2026-06-01)
