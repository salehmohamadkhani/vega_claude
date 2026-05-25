#!/usr/bin/env bash
# Pre-tool hook for Ralph Mode
# This hook runs BEFORE Copilot executes a tool
#
# Environment variables available:
#   RALPH_TOOL_NAME - Name of the tool being executed
#   RALPH_TOOL_ARGS - Arguments passed to the tool

# Example: Log tool usage
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Tool: $RALPH_TOOL_NAME" >> .ralph-mode/tools.log

# Example: Block dangerous commands
# case "$RALPH_TOOL_NAME" in
#   rm|rmdir)
#     echo "Blocked dangerous command: $RALPH_TOOL_NAME"
#     exit 1
#     ;;
# esac

exit 0
