#!/usr/bin/env bash
#
# on-network-wait.sh - Hook called during network wait
#
# Called periodically while waiting for network reconnection.
# Use this to perform custom actions like notifications.
#
# Environment variables available:
#   RALPH_ITERATION      - Current iteration number
#   RALPH_MAX_ITERATIONS - Maximum iterations allowed
#   RALPH_TASK_ID        - Current task ID (batch mode)
#   RALPH_MODE           - "single" or "batch"
#
# Examples:
#   - Send notification to Slack/Discord
#   - Log to external monitoring
#   - Trigger backup processes

# Example: Log wait event
# echo "[$(date)] Network wait at iteration $RALPH_ITERATION" >> .ralph-mode/network.log

# Example: Desktop notification (macOS)
# osascript -e 'display notification "Waiting for network..." with title "Ralph Mode"'

# Example: Desktop notification (Linux with notify-send)
# notify-send "Ralph Mode" "Waiting for network reconnection..."

# Example: Send to webhook
# curl -s -X POST "https://your-webhook.url" \
#   -H "Content-Type: application/json" \
#   -d '{"text":"Ralph Mode waiting for network at iteration '"$RALPH_ITERATION"'"}' \
#   2>/dev/null || true

exit 0
