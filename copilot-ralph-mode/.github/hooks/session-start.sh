#!/bin/bash

# Ralph Mode Session Start Hook
# Displays Ralph Mode status when a new Copilot CLI session starts

set -euo pipefail

RALPH_STATE_FILE=".ralph-mode/state.json"

if [[ ! -f "$RALPH_STATE_FILE" ]]; then
    exit 0
fi

# Parse state
if command -v jq &>/dev/null; then
    ITERATION=$(jq -r '.iteration // 1' "$RALPH_STATE_FILE")
    MAX_ITERATIONS=$(jq -r '.max_iterations // 0' "$RALPH_STATE_FILE")
    COMPLETION_PROMISE=$(jq -r '.completion_promise // null' "$RALPH_STATE_FILE")
    MODE=$(jq -r '.mode // "single"' "$RALPH_STATE_FILE")
elif command -v python3 &>/dev/null; then
    ITERATION=$(python3 -c "import json; d=json.load(open('$RALPH_STATE_FILE')); print(d.get('iteration', 1))")
    MAX_ITERATIONS=$(python3 -c "import json; d=json.load(open('$RALPH_STATE_FILE')); print(d.get('max_iterations', 0))")
    COMPLETION_PROMISE=$(python3 -c "import json; d=json.load(open('$RALPH_STATE_FILE')); print(d.get('completion_promise', 'null') or 'null')")
    MODE=$(python3 -c "import json; d=json.load(open('$RALPH_STATE_FILE')); print(d.get('mode', 'single'))")
else
    exit 0
fi

# Display status
cat <<EOF

═══════════════════════════════════════════════════════════════
🔄 Ralph Mode Active
═══════════════════════════════════════════════════════════════

Iteration: $ITERATION
EOF

if [[ "$MAX_ITERATIONS" -gt 0 ]]; then
    echo "Max Iterations: $MAX_ITERATIONS"
else
    echo "Max Iterations: unlimited"
fi

if [[ "$COMPLETION_PROMISE" != "null" ]] && [[ -n "$COMPLETION_PROMISE" ]]; then
    echo "Completion Promise: \"$COMPLETION_PROMISE\""
    echo ""
    echo "To complete: output <promise>$COMPLETION_PROMISE</promise>"
else
    echo "Completion Promise: none"
fi

echo "Mode: $MODE"
echo ""
echo "Task: .ralph-mode/prompt.md"
echo "═══════════════════════════════════════════════════════════════"
echo ""

exit 0
