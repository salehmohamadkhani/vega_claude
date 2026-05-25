# 📘 Ralph Mode Execution Guide

This guide standardizes Ralph Mode execution, effective task design, and prevents read-only behavior.

---

## Part 1: Execution Principles

1. **Always run from project root** - Never cd into subdirectories
2. **Dedicated terminal for loop** - Don't run other commands in the same terminal
3. **Real file changes required** - Every iteration must produce visible diffs
4. **Tasks must be measurable and scoped** - Vague tasks lead to read-only behavior

---

## Part 2: Standard Task Template (Required for Code Changes)

```markdown
---
id: TASK-001
title: Descriptive title
tags: [tag1, tag2]
model: gpt-5.2-codex
max_iterations: 10
completion_promise: TASK_DONE
---

# Task Title

## Objective
One sentence describing the exact change to make.

## Scope

- **ONLY modify:** `path/to/specific/file.ts` (max 1-2 files)
- **DO NOT read:** Any other files or directories
- **DO NOT touch:** [forbidden paths]

## Pre-work

1. Confirm the target file exists and is writable
2. Identify the exact lines/locations to change
3. Confirm no other files are required

## Changes Required (Mandatory & Measurable)

1. **Add constant X** to line Y in `file.ts`
2. **Change type of Z** from `string` to `number`
3. [Each change must have exact element name and expected result]

## Acceptance Criteria

- [ ] At least one real change in allowed files
- [ ] Changes visible in `git diff`
- [ ] If no change needed, task MUST fail (not DONE)

## Verification

```bash
# Specific check command
grep "NEW_CONSTANT" path/to/file.ts
```

## Completion

Only when ALL items are done:
```
<promise>TASK_DONE</promise>
```

## Notes

- Do NOT read any other files
- If new file needed, task must explicitly allow it
```

---

## Part 3: Common Problem - Read-Only Behavior

### Symptoms
- Model only runs `grep`, `cat`, `find`
- No actual file modifications
- Loop exits with DONE but no changes

### Causes
1. **Vague tasks** - "Fix all RTL issues" is too broad
2. **Change already exists** - Model verifies instead of modifying
3. **No explicit modification instruction** - Task asks to "check" not "change"

### Permanent Solutions

1. **One file, one change** - Task must specify exactly which file and what change
2. **Add "DO NOT read other files"** - Prevents scanning behavior
3. **Use imperative language** - "Add constant X" not "Ensure constant X exists"
4. **Require visible diff** - Task fails if no `git diff` output

---

## Part 4: Docker Execution Flow

```bash
# 1. Start Docker Desktop

# 2. Run container with volume mount
docker run -it --name ralph-ubuntu \
  -v /path/to/target/project:/workspace \
  -v /path/to/ralph-mode:/ralph-mode \
  ubuntu:22.04 bash

# 3. Inside container - Install dependencies
apt update && apt install -y python3 python3-pip python3-venv git curl

# 4. Create venv (required for PEP 668)
cd /ralph-mode
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt  # if exists

# 5. Copy tasks to ralph-mode
cp /workspace/my-tasks/*.md /ralph-mode/tasks/

# 6. For batch mode - use tasks-file JSON (required)
cat > /tmp/tasks.json << 'EOF'
[
  {"prompt": "tasks/task1.md"},
  {"prompt": "tasks/task2.md"}
]
EOF

# 7. Initialize and run
cd /workspace  # Run from target project root!
python3 /ralph-mode/ralph_mode.py batch-init --tasks-file /tmp/tasks.json
/ralph-mode/ralph-loop.sh run
```

---

## Part 4.1: Task Library Groups (Non-JSON)

If you use task files and groups in `tasks/_groups/`, load them directly:

```bash
# Run from target project root
python3 /ralph-mode/ralph_mode.py run --group rtl
/ralph-mode/ralph-loop.sh run
```

---

## Part 5: Pre-Execution Checklist

- [ ] Copilot account active with sufficient quota
- [ ] Running from project root (not ralph-mode folder)
- [ ] Copilot CLI authenticated (`copilot login` if needed)
- [ ] `GITHUB_TOKEN` unset unless you explicitly want it used by Copilot CLI
- [ ] Tasks are scoped and specific
- [ ] Loop terminal is dedicated (no other commands)
- [ ] Target files exist and are writable
- [ ] Git initialized (for diff verification)
- [ ] Optional: verification commands are present in task `## Verification`

---

## Part 6: Quick Debugging

| Problem | Solution |
|---------|----------|
| Only read/grep, no changes | Make task more specific, add "ONLY modify" |
| batch-init error | Use `--tasks-file` (tasks-dir not supported) |
| Quota error | Copilot needs subscription/charge |
| 401 / Failed to list models | Run `copilot login` and unset `GITHUB_TOKEN` |
| Loop exits immediately | Check `completion_promise` format |
| No diff after completion | Task was already satisfied, redesign it |
| Permission denied | Check file ownership in Docker |
| Verification fails | Run `./ralph-loop.sh verify` to isolate and debug |
| Iteration fails with "No file changes detected" | Make task more specific or set `RALPH_SKIP_CHANGE_CHECK=1` to bypass |

---

## Part 7: Task Design Anti-Patterns

### ❌ Bad Task
```markdown
Fix all RTL issues in the codebase.
```

### ✅ Good Task
```markdown
## Scope
- ONLY modify: `src/components/Button.tsx`
- DO NOT read: Any other files

## Changes Required
1. Line 15: Change `ml-4` to `ms-4`
2. Line 23: Change `text-left` to `text-start`

## Acceptance Criteria
- File must have exactly 2 lines changed
- `git diff` shows modifications
```

---

## Part 8: Verification Commands

```bash
# Check if ralph-mode is active
python3 ralph_mode.py status

# View current prompt
python3 ralph_mode.py prompt

# Check iteration history
python3 ralph_mode.py history

# Verify changes were made
git diff
git diff --stat

# Count modified files
git diff --name-only | wc -l
```

---

## Part 9: Real-World Lessons (Quick Reference)

- **Copilot CLI install**: use a user-writable prefix to avoid EACCES
  - `npm config set prefix "$HOME/.local"`
  - `NPM_CONFIG_PREFIX="$HOME/.local" npm install -g @github/copilot`
- **Loop terminal**: avoid interactive prompts; they break unattended runs
- **Batch mode**: always provide `tasks.json` for grouped tasks
- **Target repo**: ensure `.ralph-mode/` exists before running the loop
- **PR hygiene**: keep branch names neutral and use standard PR sections

Full notes: [docs/LESSONS_LEARNED.md](docs/LESSONS_LEARNED.md)

---

## Part 10: Security Scanning (CodeQL Integration)

Ralph Mode includes optional security scanning via CodeQL or grep-based fallback.

### Quick usage

```bash
# Auto-detect language, scan entire project
python3 ralph_mode.py scan

# Scan only changed files, quiet mode
python3 ralph_mode.py scan --changed-only --quiet

# Explicit language
python3 ralph_mode.py scan --language python
```

### Integration options

| Method | How to enable | Blocking? |
|--------|---------------|-----------|
| CLI on-demand | `ralph_mode.py scan` | No |
| Post-iteration hook | Set `RALPH_CODEQL_SCAN=1` | No |
| Security agent | `@security scan the project` | No |

### How it works

1. **Language detection** — auto-detects from `package.json`, `go.mod`, `pyproject.toml`, etc.
2. **CodeQL path** — if `codeql` is on PATH: creates database → runs security suite → outputs SARIF
3. **Grep fallback** — if no CodeQL: pattern-matches common vulnerabilities (eval, exec, innerHTML, etc.)
4. **Memory** — saves results to Ralph memory bank as episodic memories
5. **Non-blocking** — never fails the iteration; always returns 0 unless critical errors found

---

## Part 11: Recent Reliability Improvements (February 2026)

Ralph Mode has received significant stability and reliability improvements:

### Core Fixes

- **✅ Promise Detection**: Now handles completion promises with any amount of whitespace or newlines
- **✅ Batch Completion**: Fixed crash when completing the final task in batch mode
- **✅ Task Matching**: Exact ID matches now take priority over fuzzy title matches
- **✅ File Handle Leaks**: State management properly closes all files after reading
- **✅ Shell Quoting**: Loop scripts handle paths with spaces and special characters correctly

### Testing Improvements

- **799 passing tests** across 9 comprehensive test suites
- **0 failures, 0 skips** on all platforms (Ubuntu, macOS, Windows)
- New test suites added:
  - `test_ralph_mode_iteration_deep.py` - Complex iteration scenarios
  - `test_ralph_mode_stress_concurrency.py` - Stress and concurrency
  - `test_ralph_mode_edge_cases.py` - Edge case coverage
  - `test_ralph_mode_feature_advanced.py` - Advanced features
  - `test_e2e_workflows.py` - Full workflow validation
  - `test_enterprise_scenarios.py` - Production scenarios

### What This Means

- **More reliable loops**: Fewer unexpected failures during long-running tasks
- **Better batch mode**: Smoother transitions between tasks without crashes
- **Accurate task selection**: Less chance of running the wrong task
- **Resource efficient**: No file descriptor exhaustion in long loops
- **Cross-platform consistency**: Works correctly on Windows, macOS, and Linux

### Verification

```bash
# Run the full test suite to verify all improvements
pytest tests/ -v

# Expected output: 799 passed in ~2 minutes
```
