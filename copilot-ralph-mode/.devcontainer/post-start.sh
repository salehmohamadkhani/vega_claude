#!/bin/bash
# =============================================================================
# Post-Start Script - Runs every time the container starts
# =============================================================================

set -e

echo "🚀 Starting Copilot Ralph Mode dev environment..."

# Ensure we're in the workspace
cd /workspace

# Check if Ralph Mode is active
if [ -f ".ralph-mode/state.json" ]; then
    echo ""
    echo "╔═══════════════════════════════════════════════════════════════════════╗"
    echo "║   ⚠️  Ralph Mode is ACTIVE!                                           ║"
    echo "╚═══════════════════════════════════════════════════════════════════════╝"
    python ralph_mode.py status 2>/dev/null || true
    echo ""
fi

# Show workspace info
echo ""
echo "📁 Workspace: /workspace"
echo "🐍 Python: $(python --version 2>&1)"
echo "📦 Packages: $(pip list 2>/dev/null | wc -l) installed"
echo ""

# Git status if in a repo
if [ -d ".git" ]; then
    echo "📊 Git Status:"
    git status --short 2>/dev/null | head -5
    BRANCH=$(git branch --show-current 2>/dev/null)
    echo "   Branch: ${BRANCH:-detached}"
    echo ""
fi

echo "✅ Ready! Type 'ralph --help' to get started."
