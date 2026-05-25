#!/usr/bin/env bash
# Completion hook for Ralph Mode
# This hook runs when a task is completed (completion promise detected)
#
# Environment variables available:
#   RALPH_ITERATION - Final iteration number
#   RALPH_TASK_ID - Completed task ID
#   RALPH_MODE - "single" or "batch"
#   RALPH_PROMISE - The completion promise that was detected

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# Log completion
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Task completed at iteration $RALPH_ITERATION" >> .ralph-mode/hooks.log

# ── Generate task summary ──
{
    echo "## Task Completed"
    echo "- **Task ID**: ${RALPH_TASK_ID:-unknown}"
    echo "- **Iterations**: $RALPH_ITERATION"
    echo "- **Completed at**: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "- **Promise**: $RALPH_PROMISE"
    echo ""
    echo "### Files Changed"
    git diff --stat HEAD~1 2>/dev/null || echo "  (no git history)"
    echo ""
    echo "### Memory Bank Stats"
    python3 "$SCRIPT_DIR/ralph_mode.py" memory stats 2>/dev/null || echo "  (unavailable)"
} > .ralph-mode/task-summary.md 2>/dev/null

# ── Final security scan ──
python3 "$SCRIPT_DIR/ralph_mode.py" scan --quiet 2>/dev/null || true

# ── Promote key learnings to long-term memory ──
python3 "$SCRIPT_DIR/ralph_mode.py" memory promote 2>/dev/null || true

exit 0
