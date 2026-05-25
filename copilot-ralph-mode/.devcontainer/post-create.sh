#!/bin/bash
# =============================================================================
# Post-Create Script - Runs once when the container is created
# =============================================================================

set -e

echo "🔄 Setting up Copilot Ralph Mode development environment..."

# -----------------------------------------------------------------------------
# Install Python dependencies
# -----------------------------------------------------------------------------
echo "📦 Installing Python dependencies..."
pip install --upgrade pip setuptools wheel
pip install -r requirements-dev.txt
pip install -e . 2>/dev/null || pip install -e ".[dev]" 2>/dev/null || true

# -----------------------------------------------------------------------------
# Set up Git
# -----------------------------------------------------------------------------
echo "🔧 Configuring Git..."

# Safe directory for mounted workspace
git config --global --add safe.directory /workspace

# Useful aliases
git config --global alias.co checkout
git config --global alias.br branch
git config --global alias.ci commit
git config --global alias.st status
git config --global alias.lg "log --oneline --graph --all"

# Default branch
git config --global init.defaultBranch main

# -----------------------------------------------------------------------------
# Set up Zsh
# -----------------------------------------------------------------------------
echo "🐚 Configuring Zsh..."

# Create zsh history directory
mkdir -p ~/.zsh_history_dir

# Add custom aliases and functions to .zshrc
cat >> ~/.zshrc << 'EOF'

# =============================================================================
# Ralph Mode Development Aliases
# =============================================================================

# Ralph Mode shortcuts
alias ralph='python ralph_mode.py'
alias ralph-enable='python ralph_mode.py enable'
alias ralph-disable='python ralph_mode.py disable'
alias ralph-status='python ralph_mode.py status'
alias ralph-iterate='python ralph_mode.py iterate'
alias ralph-loop='./ralph-loop.sh run'

# Testing shortcuts
alias test='pytest tests/ -v'
alias test-fast='pytest tests/ -v -x --tb=short'
alias test-cov='pytest tests/ -v --cov=ralph_mode --cov-report=term-missing'
alias test-watch='pytest tests/ -v --watch'

# Linting shortcuts
alias lint='flake8 ralph_mode.py && black --check ralph_mode.py && isort --check-only ralph_mode.py'
alias format='black ralph_mode.py && isort ralph_mode.py'
alias typecheck='mypy ralph_mode.py'

# Git shortcuts
alias gs='git status'
alias gc='git commit'
alias gp='git push'
alias gl='git lg'

# Python
alias py='python'
alias ipy='ipython'

# General
alias ll='ls -la'
alias cls='clear'

# =============================================================================
# Ralph Mode Functions
# =============================================================================

# Quick start a Ralph loop with a task
ralph-quick() {
    if [ -z "$1" ]; then
        echo "Usage: ralph-quick 'Your task description'"
        return 1
    fi
    python ralph_mode.py enable "$1" --max-iterations 20 --completion-promise "DONE"
    echo "✅ Ralph Mode enabled! Run 'ralph-loop' to start."
}

# Run tests and show summary
test-summary() {
    pytest tests/ -v --tb=no | tail -20
}

# =============================================================================
EOF

# -----------------------------------------------------------------------------
# Set up pre-commit hooks (optional)
# -----------------------------------------------------------------------------
if command -v pre-commit &> /dev/null; then
    echo "🪝 Setting up pre-commit hooks..."
    pre-commit install 2>/dev/null || true
fi

# -----------------------------------------------------------------------------
# Verify installation
# -----------------------------------------------------------------------------
echo ""
echo "✅ Verifying installation..."
python -c "import ralph_mode; print(f'  Ralph Mode version: {ralph_mode.__version__ if hasattr(ralph_mode, \"__version__\") else \"dev\"}')"
echo "  Python: $(python --version)"
echo "  Pytest: $(pytest --version 2>/dev/null | head -1)"
echo "  Git: $(git --version)"

# -----------------------------------------------------------------------------
# Run initial tests
# -----------------------------------------------------------------------------
echo ""
echo "🧪 Running quick test..."
pytest tests/test_ralph_mode.py -v -x --tb=short -q 2>/dev/null || echo "  (Tests will run when source is available)"

# -----------------------------------------------------------------------------
# Done!
# -----------------------------------------------------------------------------
echo ""
echo "╔═══════════════════════════════════════════════════════════════════════╗"
echo "║                                                                       ║"
echo "║   🎉 Dev Container Ready!                                             ║"
echo "║                                                                       ║"
echo "║   Quick commands:                                                     ║"
echo "║     ralph-quick 'Your task'  - Start a Ralph loop                     ║"
echo "║     test                     - Run all tests                          ║"
echo "║     lint                     - Check code quality                     ║"
echo "║     format                   - Auto-format code                       ║"
echo "║                                                                       ║"
echo "╚═══════════════════════════════════════════════════════════════════════╝"
echo ""
