# Contributing to Copilot Ralph Mode

Thank you for your interest in contributing! 🎉

## How to Contribute

### Reporting Bugs

1. Check if the bug has already been reported in [Issues](https://github.com/YOUR_USERNAME/copilot-ralph-mode/issues)
2. If not, create a new issue with:
   - A clear title and description
   - Steps to reproduce
   - Expected vs actual behavior
   - Your environment (OS, bash version, etc.)

### Suggesting Features

1. Open an issue with the `enhancement` label
2. Describe the feature and its use case
3. Explain how it fits with the Ralph philosophy

### Pull Requests

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Make your changes
4. Run tests: `bash tests/test-ralph-mode.sh`
5. Commit with clear messages: `git commit -m 'Add amazing feature'`
6. Push: `git push origin feature/amazing-feature`
7. Open a Pull Request

### Code Style

- Use `shellcheck` for bash scripts
- Follow existing patterns in the codebase
- Add tests for new functionality
- Update documentation as needed
- Follow the task standard in [docs/EXECUTION_GUIDE.md](docs/EXECUTION_GUIDE.md) when adding or editing tasks

### Testing

Run the comprehensive test suite before submitting:

```bash
# Using pytest (recommended)
pytest tests/ -v                    # Run all 799 tests
pytest tests/ -v --timeout=30       # With timeout protection
pytest tests/ -v -k "test_batch"    # Run specific test pattern

# Using Make
make test           # Run all tests
make test-cov       # Run with coverage report
make lint           # Check code quality

# Quick test during development
pytest tests/test_ralph_mode.py -v  # Core tests only

# Platform-specific
pytest tests/test_cross_platform.py -v  # Cross-platform compatibility
```

### Test Coverage Requirements

- All new features must include tests
- Bug fixes must include regression tests
- Tests must pass on all platforms (Ubuntu, macOS, Windows)
- Tests must pass on Python 3.9, 3.10, 3.11, and 3.12
- Aim for high test coverage (current: 799 passing tests)

### Test Structure

| Test Suite | Purpose |
|------------|---------|
| `test_ralph_mode.py` | Core functionality |
| `test_ralph_mode_integration.py` | Integration scenarios |
| `test_ralph_mode_iteration_deep.py` | Deep iteration edge cases |
| `test_ralph_mode_stress_concurrency.py` | Stress and concurrency |
| `test_ralph_mode_edge_cases.py` | Edge case coverage |
| `test_ralph_mode_feature_advanced.py` | Advanced features |
| `test_e2e_workflows.py` | End-to-end workflows |
| `test_enterprise_scenarios.py` | Enterprise use cases |
| `test_cross_platform.py` | Platform compatibility |

### Code Quality

```bash
# Linting
make lint           # Run all linters
flake8 .            # Python linting
shellcheck *.sh     # Shell script linting

# Formatting
make format         # Auto-format code
black .             # Format Python
isort .             # Sort imports

# Type checking
mypy ralph_mode/    # Static type analysis
```

## Philosophy

Remember the core Ralph principles:

1. **Iteration > Perfection** - Small improvements are welcome
2. **Failures Are Data** - Bugs help us improve
3. **Persistence Wins** - Keep iterating on your PR if needed

## Questions?

Feel free to open an issue for any questions!
