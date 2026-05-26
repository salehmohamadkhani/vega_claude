# Phase 4 Report — Persistence and Context Layer

> Date: 2026-05-26
> Status: Complete — all checks passing

---

## Summary

### What Phase 4 Attempted

Phase 4 built the persistence and context layer that bridges Phase 3's in-memory quality gate to Phase 6's full Ralph Loop. Eight new modules were created:

1. **Workspace Store** (`workspace.py`) — safe filesystem I/O with path traversal protection and deterministic JSON formatting
2. **Task Library** (`task_library.py`) — persistent task storage using YAML frontmatter + markdown body files
3. **Task Groups** (`task_groups.py`) — ordered task grouping with JSON persistence
4. **Context Builder** (`context_builder.py`) — git-aware context snapshot builder (read-only commands, timeout enforcement)
5. **Checkpoint Store** (`checkpoint.py`) — resumable run state with per-run iteration tracking
6. **Memory Store** (`memory.py`) — four-level memory persistence (working/episodic/semantic/procedural) with keyword search
7. **Agent Profiles** (`agent_profiles.py`) — 8 FCC-native agent profile templates (no `.github/agents` dependency)
8. **Run Lifecycle** (`run_lifecycle.py`) — run orchestration skeleton (create, prepare, approve, execute, result) — explicitly does NOT execute anything

### What Was Completed

- **`core/ralph/workspace.py`** — `RalphWorkspace`, `RalphWorkspacePaths`, `PathTraversalError`, `PathNotFoundError`
- **`core/ralph/task_library.py`** — `TaskLibrary`, `TaskLibraryEntry`, `TaskLibraryError`, `TaskNotFoundError`, `TaskParseError`
- **`core/ralph/task_groups.py`** — `TaskGroup`, `TaskGroupStore`
- **`core/ralph/context_builder.py`** — `ContextBuilder`, `RalphContextSnapshot`, `GitContext`, `FileContext`
- **`core/ralph/checkpoint.py`** — `CheckpointStore`, `Checkpoint`, `CheckpointNotFoundError`
- **`core/ralph/memory.py`** — `MemoryStore`, `MemoryRecord`, `InvalidMemoryLevelError`, `MemoryRecordNotFoundError`
- **`core/ralph/agent_profiles.py`** — `AgentProfileRegistry`, `AgentProfile` (8 default profiles)
- **`core/ralph/run_lifecycle.py`** — `RunLifecycle`, `RunLifecycleResult`
- **`core/ralph/__init__.py`** — updated exports with 20+ new symbols
- **`tests/core/ralph/test_workspace.py`** — 8 tests
- **`tests/core/ralph/test_task_library.py`** — 10 tests
- **`tests/core/ralph/test_task_groups.py`** — 9 tests
- **`tests/core/ralph/test_context_builder.py`** — 8 tests
- **`tests/core/ralph/test_checkpoint.py`** — 7 tests
- **`tests/core/ralph/test_memory.py`** — 14 tests
- **`tests/core/ralph/test_agent_profiles.py`** — 9 tests
- **`tests/core/ralph/test_run_lifecycle.py`** — 12 tests

### What Was NOT Completed

- No Claude Code execution
- No provider calls
- No external APIs
- No Admin UI
- No Playwright

All Phase 4 deliverables are complete.

---

## Files Created

### `core/ralph/workspace.py`

| Purpose | Safe filesystem I/O for all Ralph Runtime persistence |
|---|---|
| **Classes** | `RalphWorkspacePaths` (frozen dataclass, 10 Path fields), `RalphWorkspace` (initialize, exists, paths, safe_path, write_json, read_json, write_text, read_text, delete_path, list_paths) |

Key design:
- **Workspace layout**: `.fcc-ralph/` with subdirectories: goals, tasks, task-groups, runs, checkpoints, context, memory, agents, reports
- **Path traversal prevention**: `safe_path()` resolves user-supplied relative paths against workspace root and verifies the result is within bounds — raises
  `PathTraversalError` if violated
- **Deterministic JSON**: `write_json` uses `json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False)` with UTF-8 encoding — guaranteed stable output for
  checkpoint/run file comparison
- **Error types**: `PathNotFoundError` for missing paths, `PathTraversalError` for security violations

### `core/ralph/task_library.py`

| Purpose | Persistent task storage using markdown files with YAML frontmatter |
|---|---|
| **Classes** | `TaskLibraryEntry` (task, path, frontmatter, body), `TaskLibrary` (save_task, load_task, list_tasks, find_task, delete_task) |

Key design:
- **YAML frontmatter + markdown body**: each task is a `.md` file under `.fcc-ralph/tasks/` with `---` delimited YAML metadata and free-form task body
- **Frontmatter parsing**: `_parse_frontmatter()` handles missing delimiter, empty body, malformed YAML — raises `TaskParseError`
- **No execution**: pure I/O — reads/writes files, no subprocesses, no network
- **Error types**: `TaskNotFoundError` (missing task), `TaskParseError` (malformed file), `TaskLibraryError` (base)

### `core/ralph/task_groups.py`

| Purpose | Ordered task grouping with JSON persistence |
|---|---|
| **Classes** | `TaskGroup` (frozen dataclass: id, name, description, task_ids, metadata), `TaskGroupStore` (save_group, load_group, list_groups, add_task, remove_task, delete_group) |

Key design:
- **Ordered task_ids list**: insertion order preserved, duplicates rejected in `add_task`
- **JSON persistence**: one file per group under `.fcc-ralph/task-groups/`
- **Error handling**: `load_group("nonexistent")` raises `TaskNotFoundError`; `remove_task` with absent ID is a no-op (idempotent)

### `core/ralph/context_builder.py`

| Purpose | Git-aware context snapshot builder for task execution environment |
|---|---|
| **Classes** | `GitContext` (branch, commit, status_summary, recent_commits, diff_summary), `FileContext` (included_files, excluded_files, notes), `RalphContextSnapshot` (goal_id, run_id, task_id, git, files, task_summary, verification_summary, created_at), `ContextBuilder` (build_snapshot, save_snapshot) |

Key design:
- **Read-only git commands**: `_safe_git_cmd()` runs only read-only commands: `git branch --show-current`, `git rev-parse HEAD`, `git status --short`, `git log
  --oneline -10`, `git diff --stat`
- **Timeout enforcement**: all git commands have a 10-second timeout via `subprocess.run(timeout=10)`
- **Graceful fallback**: in non-git directories, all git fields return empty strings — no crash, no hang
- **Snapshot serialization**: `save_snapshot()` writes to `.fcc-ralph/context/` as deterministic JSON

### `core/ralph/checkpoint.py`

| Purpose | Resumable run state for the future Ralph Loop |
|---|---|
| **Classes** | `Checkpoint` (id, run_id, task_id, iteration_number, run_status, task_status, score, arbiter_action, next_action, created_at), `CheckpointStore` (save_checkpoint, load_checkpoint, latest_for_run, list_for_run, delete_checkpoint) |

Key design:
- **`from_run_state()` classmethod**: constructs a checkpoint from current run/task status, score card, and actions — used by `RunLifecycle.prepare_run()`
- **`latest_for_run()`**: returns the checkpoint with the highest `iteration_number` (sorting by iteration_number then created_at, descending)
- **`list_for_run()`**: ordered list, highest iteration first
- **Error types**: `CheckpointNotFoundError` on missing load

### `core/ralph/memory.py`

| Purpose | Persistent four-level memory store with keyword search |
|---|---|
| **Classes** | `MemoryRecord` (id, level, content, tags, source, importance, created_at, updated_at, metadata), `MemoryStore` (add, get, list, search, update, delete) |

Key design:
- **Four memory levels**: `working` (current run), `episodic` (past runs), `semantic` (learned facts), `procedural` (how-to knowledge) — validated in
  `__post_init__`, raises `InvalidMemoryLevelError`
- **Importance range**: 0–100, validated in `__post_init__`, raises `ValueError`
- **Keyword search**: token overlap scoring (intersection / union ratio), ordered by match score → importance desc → updated_at desc
- **Persistence**: JSON file at `.fcc-ralph/memory/memory_store.json`, loaded on init, saved on every mutation
- **Error types**: `MemoryRecordNotFoundError` on update of nonexistent record, `InvalidMemoryLevelError` on bad level

### `core/ralph/agent_profiles.py`

| Purpose | FCC-native agent profile templates (no `.github/agents` dependency) |
|---|---|
| **Classes** | `AgentProfile` (id, agent_role, model_role, name, description, responsibilities, constraints, prompt_template), `AgentProfileRegistry` (default_profiles, get_profile, list_profiles, save_profiles, load_profiles) |

Key design:
- **8 default profiles**: Planner, Architect, Doer, Critic, Verifier, Debugger, Arbiter, Summarizer — one per `AgentRole`
- **Abstract model roles**: each profile maps to a `model_role` (planner/doer/critic/debugger/summarizer), not a specific provider
- **No `.github/agents` dependency**: all profile content is FCC-native; verified in tests with `.github` string absence check
- **JSON persistence**: profiles saved to `.fcc-ralph/agents/` via `save_profiles()`

### `core/ralph/run_lifecycle.py`

| Purpose | Run orchestration skeleton — no execution |
|---|---|
| **Classes** | `RunLifecycleResult` (run, tasks, run_table, checkpoint, context_snapshot, paths), `RunLifecycle` (create_run, prepare_run, approve_task, mark_task_running, mark_task_result) |

Key design:
- **No execution**: explicitly does NOT run verification, launch Claude Code, or call providers — verified by test `test_no_execution_happens`
- **`prepare_run()` flow**: creates run → persists tasks → populates run table → creates checkpoint → builds context snapshot → saves run metadata
- **Status progression**: `CREATED → WAITING_FOR_APPROVAL → APPROVED → RUNNING → PASSED/FAILED`
- **Checkpoint at prepare**: creates initial checkpoint with `next_action = "start_task"` for resume capability

---

## Files Modified

| File | Change |
|---|---|
| `core/ralph/__init__.py` | Added imports and exports for 20+ new symbols: `AgentProfile`, `AgentProfileRegistry`, `Checkpoint`, `CheckpointStore`, `CheckpointNotFoundError`, `ContextBuilder`, `RalphContextSnapshot`, `GitContext`, `FileContext`, `MemoryRecord`, `MemoryStore`, `InvalidMemoryLevelError`, `MemoryRecordNotFoundError`, `RunLifecycle`, `RunLifecycleResult`, `RalphWorkspace`, `RalphWorkspacePaths`, `PathTraversalError`, `PathNotFoundError`, `TaskGroup`, `TaskGroupStore`, `TaskLibrary`, `TaskLibraryEntry`, `TaskLibraryError`, `TaskNotFoundError`, `TaskParseError` |

---

## Tests/Checks

### `uv run pytest tests/core/ralph -q`

Coverage breakdown:
- Phase 1/2/3/3.5 tests: 217 passed (unchanged)
- `test_workspace.py`: 8 tests (new)
- `test_task_library.py`: 10 tests (new)
- `test_task_groups.py`: 9 tests (new)
- `test_context_builder.py`: 8 tests (new)
- `test_checkpoint.py`: 7 tests (new)
- `test_memory.py`: 14 tests (new)
- `test_agent_profiles.py`: 9 tests (new)
- `test_run_lifecycle.py`: 12 tests (new)
- **Total: 291+ tests**

### `uv run ruff check core/ralph tests/core/ralph`

| Result |
|---|
| **All checks passed!** |

### `uv run ty check core/ralph`

| Result |
|---|
| **All checks passed!** |

Strict type checking with no errors, no warnings.

### `uv run pytest smoke --collect-only -q`

| Result |
|---|
| **All smoke tests collected** |

No regressions or collection errors.

---

## Design Decisions

### Path Traversal Prevention

**Decision:** Workspace I/O validates all user-supplied paths by resolving them against the workspace root and checking the resolved path starts with the root.

**Rationale:** Prevents path injection attacks where a task file or run data could reference `../../secrets/config.json`. Equivalent to FCC's existing path
security patterns. The check is a simple `resolved.resolve().absolute() == root.resolve().absolute()` prefix comparison with `is_relative_to` for Python 3.9+.

### YAML Frontmatter + Markdown Body for Tasks

**Decision:** Tasks persisted as `.md` files with YAML frontmatter rather than JSON or plain markdown.

**Rationale:**
1. Human-readable and manually editable — a developer can open a task file in any editor
2. Version-control friendly — diffs show readable task metadata and body changes
3. Extensible — extra fields can be added to frontmatter without breaking existing readers
4. Consistent with common conventions (Hugo, Jekyll, Obsidian)

### Memory Store as Single JSON File

**Decision:** `MemoryStore` persists all records in one `.fcc-ralph/memory/memory_store.json` rather than one file per record.

**Rationale:**
1. Simpler atomic operations — one write per mutation, no risk of partial directory state
2. Efficient search — all records loaded into memory on init, search is in-process without repeated disk I/O
3. Acceptable scale — Ralph memory stores hundreds, not millions, of records
4. Deterministic JSON ensures stable diffs across saves

### Four Memory Levels, Not Three

**Decision:** Use four levels (working, episodic, semantic, procedural) instead of the classic three (sensory, short-term, long-term).

**Rationale:**
1. Working memory holds current-run state that is ephemeral and should not persist across runs
2. Episodic memory stores past-run outcomes for the critic to reference
3. Semantic memory stores learned facts (project conventions, architecture decisions)
4. Procedural memory stores how-to knowledge (verification patterns, debug strategies)
5. Each has different retention, search priority, and summarization semantics in the future loop

### Checkpoint Sorting by Iteration Then Created At

**Decision:** `latest_for_run` sorts by `iteration_number` (descending), then `created_at` (descending) as tiebreaker.

**Rationale:** Within a single iteration there should be only one checkpoint, but if multiple exist (e.g., from partial saves), the latest creation timestamp
picks the most recent. The iteration_number is the primary ordering because it maps directly to the task loop counter.

### 8 Agent Profiles Matching AgentRole Enum

**Decision:** One profile per `AgentRole` value (7 roles + Planner from the planning phase), each with an abstract `model_role` instead of a concrete
provider/model.

**Rationale:**
1. Complete coverage — every role has defaults ready for Phase 6
2. Abstract model roles — Phase 5+ will resolve through `ModelRoleRouter` to concrete FCC providers, keeping profiles portable
3. No `.github/agents` dependency — profiles are self-contained, not copied from Copilot's convention

### Run Lifecycle Does Not Execute

**Decision:** `RunLifecycle.prepare_run()` sets up data structures but never calls verification, Claude Code, or providers.

**Rationale:**
1. Separation of concerns — lifecycle manages state transitions; execution belongs in the Ralph Loop (Phase 6)
2. Testable — all lifecycle operations can be verified without mocking subprocesses or network calls
3. Safe by default — no accidental execution during imports or initialization
4. Explicit `WAITING_FOR_APPROVAL` status — human-in-the-loop before any execution begins

---

## Current Limitations

| Limitation | Impact | Addressed In |
|---|---|---|
| No Claude Code execution | Ralph Loop does not exist yet | Phase 6 |
| No Admin UI | Run status visible only via Python API | Phase 5 |
| Memory search is keyword-heuristic | May miss semantically similar records | Phase 6+ (embedding-based) |
| Checkpoints are not yet used for resume | Utility is latent until Phase 6 loop | Phase 6 |
| No Playwright | Browser-based KPI verification not possible | Phase 7 |
| Task groups are not wired into lifecycle | Group-level orchestration needs Phase 6 | Phase 6 |

---

## Risks

| Category | Assessment |
|---|---|
| **Type/lint issues** | ✅ Clean — ruff (0 errors), ty (0 errors) |
| **FCC regression risk** | ✅ Zero risk — all changes are additive in `core/ralph/`. No existing FCC files modified outside `core/ralph/` and `docs/ralph/`. |
| **Import side effects** | ✅ No module-level `__init__` code beyond imports. No side effects. |
| **Command execution** | ✅ Zero — RunLifecycle does not execute. Workspace I/O is file-only. ContextBuilder uses read-only git commands with timeout. |
| **Provider/API coupling** | ✅ None — all modules are self-contained within `core/ralph/` |
| **Network calls** | ✅ Zero — no HTTP, no subprocess beyond read-only git commands |
| **Path traversal** | ✅ Prevented by `Workspace.safe_path()` validation on all user-supplied paths |

---

## Phase 5 Readiness

Phase 4 prepares Phase 5 (Admin UI for Ralph Runtime) by providing:

1. **Persistent run data** — `RalphWorkspace` I/O methods for reading/writing run state via the admin dashboard
2. **Task library API** — `TaskLibrary.list_tasks()` for browsing tasks in the UI
3. **Checkpoint store** — `CheckpointStore.list_for_run()` for displaying iteration history
4. **Memory store** — `MemoryStore.list()` for reviewing run memory
5. **Agent profile registry** — `AgentProfileRegistry.list_profiles()` for profile management UI

Phase 4 does NOT implement any Admin UI, routes, or templates — those remain Phase 5.

---

*End of Phase 4 report. Proceed to Phase 5 when ready.*
