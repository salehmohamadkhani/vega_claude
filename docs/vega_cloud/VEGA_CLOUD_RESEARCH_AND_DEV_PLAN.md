# Vega Cloud Research-Driven Development Plan

**Status:** Active  
**Generated:** 2026-06-01  
**Phase:** U9-LITE  
**Branch:** `ralph-r1-temp`  
**Mode:** SEPCC Direct (no fan-out required)

---

## 1. Current Vega Cloud State

### Repository Structure

| Layer | Path | Description |
|-------|------|-------------|
| Product | `/opt/vega-cloud/vega_claude/free-claude-code/` | Multi-provider LLM proxy (464 `.py` files) |
| Agent Runtime | `vega_agents/` | Token-aware agent selection + execution planning (4 modules) |
| Docs/Ralph | `docs/ralph/` | Phase reports, ledgers, protocols (20 files) |
| Scripts | `scripts/` | Ralph loop guards, project snapshot |
| Tests | `tests/ralph/` | Agent runtime, executor, ledger, snapshot, pipeline contracts |

### Vega Agent Runtime (U6-U8)

Three layers built so far:

1. **Registry** (`vega_agents/registry.py`) — Defines 6 built-in agent roles: `codebase_auditor`, `implementation_planner`, `test_planner`, `guardrail_reviewer`, `research_scanner`, `security_reviewer`
2. **Selector** (`vega_agents/selector.py`) — Classifies tasks via `TaskProfile`, decides `direct` vs `fanout_proposed` mode, caps fan-out at 3 agents
3. **Executor** (`vega_agents/executor.py`) — Builds `AgentExecutionPlan` with per-step LLM cost estimates and approval gates

**Missing:** Actual task runner to execute a plan. The executor builds plans but nothing runs them.

### Test Coverage

- `test_vega_agent_runtime.py` — 20 tests covering registry + selector
- `test_vega_agent_executor.py` — 22 tests covering plan building and fan-out gate
- All tests are stdlib-only, no product imports, no network, no env reads

---

## 2. Research Repos Available

| Repo | Path | Relevance |
|------|------|-----------|
| **microsoft-autogen** | `research/repos/microsoft-autogen/` | Multi-agent orchestration — useful for agent-to-agent communication patterns |
| **continuedev-continue** | `research/repos/continuedev-continue/` | VS Code AI coding assistant — useful for task execution and tool-use patterns |
| **cline-cline** | `research/repos/cline-cline/` | VS Code AI agent — useful for agent lifecycle and task tracking |
| **langchain-ai-langchain** | `research/repos/langchain-ai-langchain/` | General LLM framework — useful for agent tool-use patterns |
| **getsentry-sentry** | `research/repos/getsentry-sentry/` | Error monitoring at scale — useful for agent error handling |
| **docker-compose** | `research/repos/docker-compose/` | Go project, lower relevance for Python agent work |

### Research Use Protocol (Token-Conscious)

| Rule | Detail |
|------|--------|
| **Only read when needed** | Do not pre-load research. Read specific files when implementing a feature that maps to a known pattern. |
| **Read a file at a time** | Never `find` + `grep` entire repos. Read one file, extract the pattern, close it. |
| **Pattern extraction pattern** | Read a research file → extract 5-20 lines of relevant pattern → note the file path → close. |
| **No research for tests** | Writing tests for the agent runtime never requires external research. |
| **Research only for new agent features** | Only open research repos when adding a new agent capability that maps to: autogen (multi-agent), continue (tool-use), cline (lifecycle), langchain (tool patterns). |
| **Research is read-only** | Never modify research repo files. |
| **Per-task research budget** | Max 1 research file read per task. If knowledge isn't in the first file, work from first principles. |

---

## 3. Agent System Status

### What Exists

```
vega_agents/
  __init__.py      — Public API exports
  registry.py      — AgentRole dataclass + registry
  selector.py      — TaskProfile + escalation logic
  executor.py      — AgentExecutionPlan builder
```

### What's Missing

| Gap | Impact | Priority |
|-----|--------|----------|
| CLI task runner | No way to invoke agent plans from command line | **HIGH** |
| Agent report format | No standard output format for completed agent tasks | MEDIUM |
| Research scanner impl | research_scanner role exists but has no code to invoke | LOW (no LLM call context yet) |
| Guardrail reviewer impl | guardrail_reviewer role exists but has no static check code | LOW |
| Pipeline integration | No bridge between Ralph pipeline and agent runtime | MEDIUM |

### Current Agent Flow (Designed, Not Implemented)

```
User Input → TaskProfile → select_agents_for_task() → AgentExecutionPlan
                                                           ↓
                                              approve? → build_execution_plan()
                                                           ↓
                                              [no runner yet — missing]
```

---

## 4. Five Practical Next Development Tasks

### Task A: Agent CLI Runner

**What:** A Python CLI script at `scripts/vega_agent_runner.py` that accepts a task description, builds a `TaskProfile`, calls `build_execution_plan()`, displays the summary, and either runs the steps in direct mode or prompts for fan-out approval.

**Value:** HIGH — unlocks the entire agent runtime by providing the actual execution pathway. Gives us a concrete tool to test with.

**Risk:** LOW — no network, no LLM calls. Pure Python CLI built on existing modules. No new dependencies.

**Files likely touched:**
- `scripts/vega_agent_runner.py` (new) — main CLI
- `vega_agents/__init__.py` (maybe) — if new exports needed
- `tests/ralph/test_vega_agent_runner.py` (new) — CLI tests

**Tests needed:** CLI argument parsing, profile building, plan display, approval flow.

**Fan-out needed?** No — SEPCC direct only. Writing a CLI script is low-risk file creation.

---

### Task B: Agent Report Format

**What:** Define a standard `AgentTaskReport` dataclass in `vega_agents/` that captures what an agent step did: files read, files written, decisions made, errors encountered, duration. Add a formatter for terminal output.

**Value:** MEDIUM — needed before any real agent execution can produce useful output. Low complexity.

**Risk:** LOW — pure data definition with no execution.

**Files likely touched:**
- `vega_agents/report.py` (new) — report dataclass + formatters
- `tests/ralph/test_vega_agent_report.py` (new)

**Tests needed:** Dataclass contract, format output, edge cases (empty report, error report).

**Fan-out needed?** No.

---

### Task C: Task Profile Builder from CLI Input

**What:** A helper function `build_profile_from_args()` that parses CLI flags into a `TaskProfile` — detecting auth, secrets, deployment keywords, counting files, etc. Makes Task A more useful.

**Value:** MEDIUM — makes the CLI runner practical. Needed by Task A but can be done separately.

**Risk:** LOW — pure parsing/classification logic.

**Files likely touched:**
- `vega_agents/profile_builder.py` (new)
- `tests/ralph/test_profile_builder.py` (new)

**Tests needed:** Keyword detection, flag parsing, edge cases.

**Fan-out needed?** No.

---

### Task D: Guardrail Reviewer — Static File Checker

**What:** Implement the `guardrail_reviewer` agent's static analysis: check that touched files are in allowed paths, contain no secrets/env patterns, and respect the no-touch port rule. Returns violations as structured findings.

**Value:** MEDIUM — adds real agent functionality without LLM calls. Useful safety layer.

**Risk:** LOW — pure Python static analysis. No network, no LLM.

**Files likely touched:**
- `vega_agents/guardrails.py` (new) — static check functions
- `tests/ralph/test_vega_guardrails.py` (new)

**Tests needed:** Path allowlist check, secret pattern detection, port rule check, edge cases.

**Fan-out needed?** No.

---

### Task E: Integration Smoke Test for Agent Runtime

**What:** An end-to-end test at `tests/ralph/test_agent_integration.py` that creates various `TaskProfile` objects, runs through the full registry → selector → executor chain, and verifies the output invariants. No network or LLM — pure logic integration.

**Value:** MEDIUM — validates all three layers work together before we add CLI. Catches interface mismatches.

**Risk:** LOW — tests only, no new code.

**Files likely touched:**
- `tests/ralph/test_agent_integration.py` (new)

**Tests needed:** Direct flow, fan-out flow, all escalation criteria.

**Fan-out needed?** No.

---

## 5. Selected Next Task

**Task A: Agent CLI Runner (`scripts/vega_agent_runner.py`)**

Rationale:
- It's the direct next step after U8's execution plan builder
- Unlocks the entire agent runtime by providing an execution pathway
- Low risk (pure Python, no network, no LLM)
- Creates the highest value for ongoing development
- Can be tested without external dependencies

Implementation sketch:
```python
# scripts/vega_agent_runner.py
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("task", help="Task description")
    parser.add_argument("--files", nargs="*", help="Touched files")
    parser.add_argument("--auth", action="store_true")
    parser.add_argument("--secrets", action="store_true")
    parser.add_argument("--network", action="store_true")
    # ... build TaskProfile → build_execution_plan → display summary
```

VEGA_CLOUD_RESEARCH_DEV_READY
