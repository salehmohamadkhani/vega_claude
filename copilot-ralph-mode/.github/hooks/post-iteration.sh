#!/usr/bin/env bash
# Post-iteration hook for Ralph Mode
# This hook runs AFTER each Copilot CLI iteration completes
#
# Environment variables available:
#   RALPH_ITERATION - Current iteration number
#   RALPH_MAX_ITERATIONS - Maximum iterations allowed
#   RALPH_TASK_ID - Current task ID (in batch mode)
#   RALPH_MODE - "single" or "batch"
#   RALPH_EXIT_CODE - Exit code from Copilot CLI

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# Log iteration completion
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Completed iteration $RALPH_ITERATION (exit: $RALPH_EXIT_CODE)" >> .ralph-mode/hooks.log

# ── Security scan on changed files (non-blocking) ──
CHANGED_FILES=$(git diff --name-only HEAD 2>/dev/null | grep -v '.ralph-mode/' || true)
if [[ -n "$CHANGED_FILES" ]]; then
    python3 "$SCRIPT_DIR/ralph_mode.py" scan --changed-only --quiet 2>/dev/null || true
fi

# ── Extract episodic memory from iteration output ──
if [[ -f ".ralph-mode/output.txt" ]]; then
    python3 "$SCRIPT_DIR/ralph_mode.py" memory extract 2>/dev/null || true
fi

exit 0
