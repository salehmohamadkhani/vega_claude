# Changelog

All notable changes to Ralph Mode will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.1.0] - 2026-02-10

### Fixed

#### Core Bug Fixes
- **Promise detection with whitespace tolerance** - Loop runner now properly detects completion promises with leading/trailing whitespace or newlines (e.g., `\n<promise>DONE</promise>\n`)
- **CLI crash on final batch task** - Fixed crash when completing the last task in batch mode. The `complete()` method now gracefully handles the expected ValueError when advancing past the final task
- **Task ID matching priority** - `get_task()` now prioritizes exact ID matches over partial title matches, preventing wrong task selection when IDs are similar
- **File handle leak in state management** - State management now properly closes file handles after reading, preventing resource exhaustion in long-running loops
- **Shell quoting bugs** - Loop scripts now properly quote variables to handle file paths with spaces and special characters

#### Test Suite Fixes
- Fixed Windows/platform-specific test skips in `test_cross_platform.py`
- Fixed TaskLibrary field name mismatches (`content` → `prompt`) in E2E and enterprise tests
- Fixed TaskLibrary path references in integration tests
- All 799 tests now pass with 0 failures and 0 skips across all platforms

### Added

#### New Test Suites
- **`test_ralph_mode_iteration_deep.py`** - 8 comprehensive tests for deep iteration scenarios including:
  - State persistence across iterations
  - Batch task advancement
  - Iteration history tracking
  - Max iteration limits
  - Recovery after disable
- **`test_ralph_mode_stress_concurrency.py`** - 4 tests for stress and concurrency scenarios:
  - Concurrent status reads during iterations
  - Recovery after mid-task restart
  - Batch completion after restart
  - State corruption recovery
- **`test_ralph_mode_edge_cases.py`** - Comprehensive edge case coverage (50+ tests)
- **`test_ralph_mode_feature_advanced.py`** - Advanced feature validation (30+ tests)

#### Enhanced Test Coverage
- Total test count: **799 tests** (up from 154)
- All tests passing on Ubuntu, macOS, and Windows
- Python 3.9, 3.10, 3.11, and 3.12 compatibility validated
- Property-based testing with Hypothesis for edge case discovery
- E2E workflow tests with real TaskLibrary integration
- Enterprise scenario tests for production use cases

### Changed

- Improved test isolation in E2E and enterprise tests
- Enhanced error messages for task matching failures
- Better handling of batch mode edge cases
- More robust promise detection using Python regex with multiline support

### Documentation

- Updated README.md with recent bug fixes and improvements section
- Updated LESSONS_LEARNED.md with February 2026 bug fixes and insights
- Updated EXECUTION_GUIDE.md with reliability improvements documentation
- Added comprehensive CHANGELOG.md for version tracking

## [1.0.0] - Previous Release

Initial stable release of Ralph Mode with core functionality:
- Single task mode
- Batch mode with JSON task files
- Task library with groups
- Custom agents and skills
- Hooks system
- Network resilience
- MCP server integration
- Cross-platform support (Windows, macOS, Linux)
- Dev container support
- 154 initial tests

---

[Unreleased]: https://github.com/sepehrbayat/copilot-ralph-mode/compare/v1.1.0...HEAD
[1.1.0]: https://github.com/sepehrbayat/copilot-ralph-mode/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/sepehrbayat/copilot-ralph-mode/releases/tag/v1.0.0
