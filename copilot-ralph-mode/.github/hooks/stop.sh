#!/bin/bash

# Ralph Mode Stop Hook
# Intercepts exit attempts when Ralph Mode is active
# Feeds the same prompt back to continue the iteration loop
#
# This hook enables "internal loop" mode where the AI tries to exit
# but the hook blocks it and feeds the prompt again.

set -euo pipefail

# Check if ralph-mode is active
RALPH_STATE_FILE=".ralph-mode/state.json"

if [[ ! -f "$RALPH_STATE_FILE" ]]; then
    # No active loop - allow exit
    exit 0
fi

# Parse JSON state file
if command -v jq &>/dev/null; then
    ITERATION=$(jq -r '.iteration // 1' "$RALPH_STATE_FILE")
    MAX_ITERATIONS=$(jq -r '.max_iterations // 0' "$RALPH_STATE_FILE")
    COMPLETION_PROMISE=$(jq -r '.completion_promise // null' "$RALPH_STATE_FILE")
    ACTIVE=$(jq -r '.active // true' "$RALPH_STATE_FILE")
elif command -v python3 &>/dev/null; then
    ITERATION=$(python3 -c "import json; d=json.load(open('$RALPH_STATE_FILE')); print(d.get('iteration', 1))")
    MAX_ITERATIONS=$(python3 -c "import json; d=json.load(open('$RALPH_STATE_FILE')); print(d.get('max_iterations', 0))")
    COMPLETION_PROMISE=$(python3 -c "import json; d=json.load(open('$RALPH_STATE_FILE')); print(d.get('completion_promise', 'null') or 'null')")
    ACTIVE=$(python3 -c "import json; d=json.load(open('$RALPH_STATE_FILE')); print(str(d.get('active', True)).lower())")
else
    echo "⚠️  Ralph Mode: Neither jq nor python3 available" >&2
    exit 0
fi

# Check if loop is inactive
if [[ "$ACTIVE" == "false" ]]; then
    exit 0
fi

# Validate numeric fields
if [[ ! "$ITERATION" =~ ^[0-9]+$ ]] || [[ ! "$MAX_ITERATIONS" =~ ^[0-9]+$ ]]; then
    echo "⚠️  Ralph Mode: State file corrupted" >&2
    exit 0
fi

# Check if max iterations reached
if [[ $MAX_ITERATIONS -gt 0 ]] && [[ $ITERATION -ge $MAX_ITERATIONS ]]; then
    echo "🛑 Ralph Mode: Max iterations ($MAX_ITERATIONS) reached."
    exit 0
fi

# Read prompt file
PROMPT_FILE=".ralph-mode/prompt.md"
if [[ ! -f "$PROMPT_FILE" ]]; then
    exit 0
fi

PROMPT_TEXT=$(cat "$PROMPT_FILE")
if [[ -z "$PROMPT_TEXT" ]]; then
    exit 0
fi

# Increment iteration
NEXT_ITERATION=$((ITERATION + 1))

# Update state file
if command -v jq &>/dev/null; then
    jq --arg iter "$NEXT_ITERATION" '.iteration = ($iter | tonumber)' "$RALPH_STATE_FILE" > "${RALPH_STATE_FILE}.tmp"
    mv "${RALPH_STATE_FILE}.tmp" "$RALPH_STATE_FILE"
elif command -v python3 &>/dev/null; then
    python3 -c "
import json
with open('$RALPH_STATE_FILE', 'r') as f:
    d = json.load(f)
d['iteration'] = $NEXT_ITERATION
with open('$RALPH_STATE_FILE', 'w') as f:
    json.dump(d, f, indent=2)
"
fi

# Log iteration
if [[ -f ".ralph-mode/history.jsonl" ]]; then
    echo "{\"event\":\"iteration\",\"iteration\":$NEXT_ITERATION,\"timestamp\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}" >> ".ralph-mode/history.jsonl"
fi

# Build system message
if [[ "$COMPLETION_PROMISE" != "null" ]] && [[ -n "$COMPLETION_PROMISE" ]]; then
    SYSTEM_MSG="🔄 Ralph iteration $NEXT_ITERATION | To complete: <promise>$COMPLETION_PROMISE</promise>"
else
    SYSTEM_MSG="🔄 Ralph iteration $NEXT_ITERATION"
fi

# Output JSON to block exit and feed prompt back (Copilot CLI hook format)
if command -v jq &>/dev/null; then
    jq -n \
        --arg prompt "$PROMPT_TEXT" \
        --arg msg "$SYSTEM_MSG" \
        '{
            "decision": "block",
            "reason": $prompt,
            "systemMessage": $msg
        }'
else
    echo "{\"decision\":\"block\",\"reason\":\"Continue working on the task\",\"systemMessage\":\"$SYSTEM_MSG\"}"
fi

exit 0
