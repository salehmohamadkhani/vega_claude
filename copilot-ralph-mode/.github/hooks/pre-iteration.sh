#!/usr/bin/env bash
# Pre-iteration hook for Ralph Mode
# This hook runs BEFORE each Copilot CLI iteration
#
# Environment variables available:
#   RALPH_ITERATION - Current iteration number
#   RALPH_MAX_ITERATIONS - Maximum iterations allowed
#   RALPH_TASK_ID - Current task ID (in batch mode)
#   RALPH_MODE - "single" or "batch"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# Log iteration start
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Starting iteration $RALPH_ITERATION" >> .ralph-mode/hooks.log

# Clear working memory for fresh start each iteration
python3 "$SCRIPT_DIR/ralph_mode.py" memory clear-working 2>/dev/null || true

# Log memory bank stats for debugging
python3 "$SCRIPT_DIR/ralph_mode.py" memory stats 2>/dev/null >> .ralph-mode/hooks.log || true

# Return 0 to continue, non-zero to abort
exit 0
