#!/usr/bin/env bash
# U13-DOCKER-LITE — Run Vega Agent Tests in Isolated Docker Sandbox
#
# Usage: bash scripts/run_agent_tests_in_docker.sh
#
# Properties:
# - Container is disposable (--rm)
# - No privileged mode
# - No mounted env files
# - No network runtime dependency
# - Build from Dockerfile.test at project root

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

IMAGE_NAME="vega-agent-test-sandbox:u13"
CONTAINER_TESTS=(
    "tests/ralph/test_vega_agent_runtime.py"
    "tests/ralph/test_vega_agent_executor.py"
    "tests/ralph/test_vega_agent_runner_cli.py"
    "tests/ralph/test_vega_agent_blueprints.py"
)

echo "=== U13-DOCKER-LITE: Building test image ==="
cd "$PROJECT_ROOT"
docker build -f Dockerfile.test -t "$IMAGE_NAME" .

echo ""
echo "=== U13-DOCKER-LITE: Running agent tests ==="
docker run --rm \
    --name vega-agent-test-runner \
    "$IMAGE_NAME" \
    python3 -m pytest -q "${CONTAINER_TESTS[@]}"

echo ""
echo "=== U13-DOCKER-LITE: All tests completed ==="
