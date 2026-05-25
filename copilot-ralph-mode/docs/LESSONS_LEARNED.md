# 🧭 Ralph Mode — Real‑World Lessons Learned

This document captures practical learnings from a full, end‑to‑end run on a real open‑source project.

---

## Environment & CLI Setup

- **Copilot CLI install may fail due to permissions** when npm tries to write to `/usr/local`. Use a user‑writable prefix:
  - `npm config set prefix "$HOME/.local"`
  - `NPM_CONFIG_PREFIX="$HOME/.local" npm install -g @github/copilot`
- **Prefer the `copilot` command** (not `gh copilot`) for Ralph loops to avoid download prompts.
- **Avoid `GITHUB_TOKEN` for Copilot CLI** unless you explicitly want token auth — it can cause 401s. Unset it for CLI usage:
  - `unset GITHUB_TOKEN`
- **Avoid interactive prompts** in loop terminals; they can block the run and break automation.

---

## Task Design Reliability

- **If a change already exists, tasks must fail** (by design). Create tasks that *must* change a file.
- **Keep scope strict**: only 1–2 files, explicit “ONLY modify” paths, and “DO NOT read” boundaries.
- **Verification commands should be deterministic** and directly prove the required change.

---

## Loop Execution Discipline

- **Run from project root** and keep a **dedicated terminal** for the loop.
- **Ensure `.ralph-mode/` exists** in the target project; missing directories can break loop logging.
- **Use batch mode with a tasks.json** when running grouped tasks.
- **No-change iterations now fail** (read-only behavior). Set `RALPH_SKIP_CHANGE_CHECK=1` to bypass when verifying-only.

---

## Contribution Hygiene (PRs)

- **Use neutral branch names** (avoid tool names in branch names if requested by maintainers).
- **Standard PR body sections** improve readability:
  - Summary
  - Changes
  - Notes (and Testing if run)
- **Permissions on public repos vary**: labels/review requests may be denied for forks.

---

## Practical Signals of Success

- **Visible diffs** after each task.
- **Clear, minimal PRs** with focused changes.
- **Owner‑friendly summaries** that highlight reliability/safety fixes and avoid noisy logs.

---

## Bug Fixes & Improvements (February 2026)

### Core Bug Fixes

- **Promise detection whitespace tolerance**: The loop runner now properly detects completion promises with leading/trailing whitespace or newlines (e.g., `\n<promise>DONE</promise>\n`).
- **Batch completion crash fix**: CLI no longer crashes when completing the final task in batch mode. The `complete()` method now gracefully handles the expected ValueError when advancing past the last task.
- **Task ID matching priority**: `get_task()` now prioritizes exact ID matches over partial title matches, preventing wrong task selection when IDs are similar.
- **File handle leak**: State management now properly closes file handles after reading, preventing resource exhaustion in long-running loops.
- **Shell quoting bugs**: Loop scripts now properly quote variables to handle file paths with spaces and special characters.

### Testing Maturity

- **799 tests passing**: Comprehensive test coverage with zero failures and zero skips across all platforms.
- **Deep iteration testing**: New test suite validates complex iteration scenarios including state persistence, batch advancement, and recovery.
- **Stress & concurrency**: New tests validate behavior under concurrent access, rapid iterations, and state corruption scenarios.
- **Enterprise scenarios**: Real-world integration tests for task libraries, E2E workflows, and production use cases.
- **Cross-platform reliability**: All Windows-specific tests now run correctly without conditional skips.

### Key Insights

- **TaskLibrary API consistency**: Internal task dictionaries use `"prompt"` field, not `"content"`. Tests must match this contract.
- **Batch mode edge cases**: The final task in a batch raises ValueError when trying to advance—this is expected behavior and should be caught.
- **Promise detection robustness**: Always use Python regex with multiline support for reliable promise detection across different AI output formats.
- **Test isolation**: E2E and enterprise tests should create isolated temporary directories to avoid interfering with actual project state.

### Development Practices

- **Test before commit**: Run full test suite (`pytest tests/ -v`) before pushing changes. All 799 tests must pass.
- **Platform testing**: Use GitHub Actions matrix to validate on Ubuntu, macOS, and Windows with Python 3.9-3.12.
- **Edge case coverage**: Property-based testing with Hypothesis helps discover edge cases in string handling, state management, and task matching.
- **Regression prevention**: When fixing bugs, add tests that would have caught the bug to prevent regression.
