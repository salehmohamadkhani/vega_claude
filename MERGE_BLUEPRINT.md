# Merge Blueprint: Ralf → Free Claude Code

> Produced: 2026-05-25 | Status: Planning (no files modified)

---

## 1. Integration Points (Re-scan)

Below are every Ralf component and its natural hook into Free Cloud.

| Ralf Component | Free Cloud Connection | How It Plugs In |
|---|---|---|
| **RalphMode state machine** (state.py) | No direct equivalent — Free Cloud has no iterative loop concept | New `plugins/ralph/` subpackage; state machine runs as an optional background process |
| **AgentTable** (agent_table/) | Free Cloud's `ClaudeMessageHandler` processes one message at a time, no multi-agent deliberation | AgentTable becomes an optional processing mode within `ClaudeMessageHandler` — instead of sending to a single Claude CLI, route through Doer/Critic/Arbiter phases |
| **MemoryStore** (memory.py) | Free Cloud has no persistent memory — only `SessionStore` (message trees) and no TF-IDF/category/episodic memory | MemoryStore becomes a standalone service used by both AgentTable and optionally by the API routes |
| **TaskLibrary** (tasks.py) | Free Cloud has no task concept — it just proxies messages | TaskLibrary integrates as a new management endpoint (`/admin/tasks`) and optional processing mode |
| **ContextManager** (context.py) | No equivalent | Standalone utility, used by AgentTable workflow |
| **Scanner** (scanner.py) | No equivalent | New admin endpoint + optional pre-flight check before message processing |
| **Verification** (verification.py) | No equivalent | New admin endpoint, used by TaskLibrary for task verification |
| **CLI loop runner** (ralph-loop.sh) | Free Cloud uses `CLISessionManager` to manage Claude CLI subprocesses | Replace the shell loop with an async Python equivalent that uses `CLISessionManager` internally |
| **Agent profiles** (agent-creator concept) | No equivalent | Stays as `.github/agents/` convention, documented in AGENTS.md |
| **Constants/configuration** | Free Cloud uses `pydantic-settings` with env vars; Ralf uses hardcoded constants and `os.environ` | Migrate Ralf config constants into Free Cloud's `Settings` model |

---

## 2. File-Level Mapping Table

### Ralf Source → Target

#### Core State Machine
| Source File | What It Does | Action | Target Location |
|---|---|---|---|
| `ralph_mode/state.py` | `RalphMode` class: enable/disable/iterate/batch, JSON state, task queue | **Adapt** — strip CLI-specific parts, wrap RalphMode as an async context manager | `plugins/ralph/state.py` |
| `ralph_mode/constants.py` | Version, models, colors, required task sections | **Split** — version/colors stay in Ralf; models/sections move into Free Cloud `Settings` | `plugins/ralph/constants.py` + `config/settings.py` |
| `ralph_mode/helpers.py` | `print_banner`, `_find_git_root`, task validation | **Adapt** — replace `print_banner` with structured logging; keep validators | `plugins/ralph/helpers.py` |
| `ralph_mode/__init__.py` | Public API | **Rewrite** — trim to what plugins/ralph/ exports | `plugins/ralph/__init__.py` |

#### Agent Table (Multi-Agent Deliberation)
| Source File | What It Does | Action | Target Location |
|---|---|---|---|
| `ralph_mode/agent_table/table.py` | `AgentTable` orchestrator | **Adapt** | `plugins/ralph/agent_table/table.py` |
| `ralph_mode/agent_table/fsm.py` | Protocol finite state machine | **Copy** (no changes needed) | `plugins/ralph/agent_table/fsm.py` |
| `ralph_mode/agent_table/models.py` | `AgentMessage`, enums | **Copy** | `plugins/ralph/agent_table/models.py` |
| `ralph_mode/agent_table/roles.py` | Doer/Critic/Arbiter role definitions | **Copy** | `plugins/ralph/agent_table/roles.py` |
| `ralph_mode/agent_table/strategies.py` | Default, strict, lenient, democratic, autocratic | **Copy** | `plugins/ralph/agent_table/strategies.py` |
| `ralph_mode/agent_table/consensus.py` | Voting, quorum, weighted scoring | **Copy** | `plugins/ralph/agent_table/consensus.py` |
| `ralph_mode/agent_table/scoring.py` | Per-agent trust tracking | **Copy** | `plugins/ralph/agent_table/scoring.py` |
| `ralph_mode/agent_table/transcript.py` | JSONL message log with queries | **Copy** | `plugins/ralph/agent_table/transcript.py` |
| `ralph_mode/agent_table/state.py` | Table state persistence | **Copy** | `plugins/ralph/agent_table/state.py` |
| `ralph_mode/agent_table/protocol.py` | Phase transitions, deadlock detection | **Copy** | `plugins/ralph/agent_table/protocol.py` |
| `ralph_mode/agent_table/context.py` | Markdown context builder per agent | **Copy** | `plugins/ralph/agent_table/context.py` |
| `ralph_mode/agent_table/hooks.py` | Event callbacks | **Copy** | `plugins/ralph/agent_table/hooks.py` |
| `ralph_mode/agent_table/validators.py` | Message + state validation | **Copy** | `plugins/ralph/agent_table/validators.py` |
| `ralph_mode/agent_table/interaction.py` | Conversation threads, relationship graph | **Copy** | `plugins/ralph/agent_table/interaction.py` |
| `ralph_mode/agent_table/negotiation.py` | Multi-turn dialogues, counter-proposals | **Copy** | `plugins/ralph/agent_table/negotiation.py` |
| `ralph_mode/agent_table/router.py` | Conditional message routing | **Copy** | `plugins/ralph/agent_table/router.py` |

#### Memory
| Source File | What It Does | Action | Target Location |
|---|---|---|---|
| `ralph_mode/memory.py` | 4-level memory, TF-IDF, decay, promotion (674 lines) | **Adapt** — replace `~/.ralph-memory` with `~/.fcc/ralph-memory`; use structlog instead of print | `plugins/ralph/memory.py` |

#### Context
| Source File | What It Does | Action | Target Location |
|---|---|---|---|
| `ralph_mode/context.py` | Git-aware context builder, progress reports | **Adapt** — make git operations optional (try/except if no git) | `plugins/ralph/context.py` |

#### Task System
| Source File | What It Does | Action | Target Location |
|---|---|---|---|
| `ralph_mode/tasks.py` | TaskLibrary: YAML frontmatter loading, groups, search | **Adapt** — add plugin-compatible init | `plugins/ralph/tasks.py` |

#### Verification
| Source File | What It Does | Action | Target Location |
|---|---|---|---|
| `ralph_mode/verification.py` | Command extraction from markdown, shell execution | **Adapt** — add async version, replace `subprocess.run` with `asyncio.create_subprocess_exec` | `plugins/ralph/verification.py` |

#### Scanner
| Source File | What It Does | Action | Target Location |
|---|---|---|---|
| `ralph_mode/scanner.py` | CodeQL + grep security scanning | **Adapt** — keep, wrap as async with httpx for CodeQL API if available | `plugins/ralph/scanner.py` |

#### CLI / Entry Points
| Source File | What It Does | Action | Target Location |
|---|---|---|---|
| `ralph_mode/cli.py` | 30+ argparse CLI commands | **Copy initially**, then hook into Free Cloud CLI entry points | `plugins/ralph/cli.py` |
| `ralph-loop.sh` | Shell loop runner w/ network resilience | **Rewrite** — replace with async Python using `CLISessionManager` | `plugins/ralph/loop.py` |
| `ralph-mode.py` | Entry script | **Ignore** — Free Cloud uses its own entry points | (deleted) |
| `pyproject.toml` | Project config | **Ignore** — Ralf deps merge into Free Cloud | (absorbed) |
| `README.md` | Docs | **Adapt** — extract relevant parts into plugin README | `plugins/ralph/README.md` |

---

## 3. Target Architecture Comparison

### Current Ralf Structure
```
copilot-ralph-mode/
  ralph_mode/
    __init__.py, cli.py, state.py, memory.py, context.py
    tasks.py, verification.py, scanner.py, helpers.py, constants.py
    agent_table/
      __init__.py, table.py, fsm.py, models.py, roles.py
      strategies.py, consensus.py, scoring.py, transcript.py
      state.py, protocol.py, context.py, hooks.py, validators.py
      interaction.py, negotiation.py, router.py
  ralph-loop.sh, ralph-mode.py
```

### Current Free Cloud Structure
```
free-claude-code/
  server.py, pyproject.toml
  api/          — FastAPI app, routes, services, admin
  cli/          — fcc-server, fcc-init, fcc-claude entrypoints
  config/       — Pydantic Settings, paths, provider catalog
  core/         — anthropic helpers, rate limit, tracing
  messaging/    — Discord/Telegram bots, handlers, sessions
  providers/    — 17 LLM providers + transports
  tests/
```

### Recommended Target Structure (Ralf as Plugin)
```
free-claude-code/
  plugins/
    ralph/          ← NEW: All Ralf code lives here, self-contained
      __init__.py
      cli.py          — Adapted Ralf CLI (registers as fcc-ralph subcommand)
      state.py        — RalphMode state machine (adapted)
      memory.py       — MemoryStore (adapted)
      context.py      — ContextManager (adapted)
      tasks.py        — TaskLibrary (adapted)
      verification.py — Verification commands (adapted)
      scanner.py      — Security scanner (adapted)
      helpers.py
      constants.py
      loop.py         — Async loop runner (replaces ralph-loop.sh)
      agent_table/    — Kept intact (copy)
        ...all files...
      README.md       — Plugin docs
      pyproject.toml  — Plugin-only metadata (deps listed in root)
```

### Integration Pattern
```
Free Cloud Core                Ralph Plugin
─────────────────              ──────────────────────
Settings (config/settings.py)  ← reads → plugins/ralph/constants.py (migrated keys)
ProviderRegistry              ← used by → AgentTable's Doer/Critic/Arbiter (optional)
CLISessionManager             ← used by → ralph/loop.py (loop runner)
ClaudeMessageHandler          ← optionally replaced by → AgentTable for multi-agent mode
Admin routes                  ← extends with → /admin/ralph/* endpoints
CLI entry points              ← extends with → fcc-ralph subcommand
```

---

## 4. Exact Integration Boundaries

### What Ralf Owns (inside `plugins/ralph/`)
- Its own state machine lifecycle (`RalphMode.enable/disable/iterate`)
- Multi-agent deliberation logic (`AgentTable` and submodules)
- Memory system (`MemoryStore`)
- Task definition and loading (`TaskLibrary`)
- Verification command parsing and execution
- Security scanner (CodeQL/grep)
- Agent profiles (`agent-creator`)
- Its own CLI commands (operated via `fcc-ralph`)

### What Free Cloud Owns (unchanged)
- Server lifecycle (`fcc-server`, uvicorn)
- Provider management (`ProviderRegistry`, all 17 providers)
- API routing (`POST /v1/messages`, `GET /health`, etc.)
- Messaging platforms (Discord, Telegram)
- Claude CLI session management (`CLISessionManager`)
- Configuration system (`pydantic-settings`, env files)
- Deployment and process management

### Adapter Interfaces Required
Ralf MUST NOT import Free Cloud internals directly. Instead, Ralf depends on **interfaces** defined in a shared `plugins/ralph/adapters.py` or in `api/`:

| Adapter | What It Abstracts | Why Needed |
|---|---|---|
| `ProviderAdapter` | `ProviderRegistry`, model routing | AgentTable needs LLM calls for agent backends |
| `CLIAdapter` | `CLISessionManager` | Loop runner needs to launch/manage Claude CLI processes |
| `SettingsAdapter` | Free Cloud `Settings` | Ralf needs its config values (max_iterations, etc.) |
| `MessagingAdapter` | `ClaudeMessageHandler` interface | AgentTable results optionally feed back into chat |
| `LoggingAdapter` | `loguru` logger | Ralf's `print` statements → structured logging |

---

## 5. Adapter Layer Design

### 5.1 ProviderAdapter (wraps ProviderRegistry)

```python
# plugins/ralph/adapters.py

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import AsyncIterator, Optional


@dataclass
class LLMResponse:
    content: str
    model: str
    provider: str


class ProviderAdapter(ABC):
    """Abstracts Free Cloud's ProviderRegistry for AgentTable use."""

    @abstractmethod
    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        model: Optional[str] = None,
    ) -> LLMResponse:
        """Send a prompt to an LLM and get a text response.
        
        Used by AgentTable to back Doer/Critic/Arbiter agents.
        """
        ...

    @abstractmethod
    async def stream_generate(
        self,
        system_prompt: str,
        user_prompt: str,
        model: Optional[str] = None,
    ) -> AsyncIterator[str]:
        """Stream tokens from an LLM call."""
        ...
        yield
```

### 5.2 CLIAdapter (wraps CLISessionManager)

```python
class CLIAdapter(ABC):
    """Abstracts Free Cloud's CLISessionManager for the loop runner."""

    @abstractmethod
    async def run_prompt(
        self,
        prompt: str,
        session_id: Optional[str] = None,
        fork: bool = False,
    ) -> AsyncIterator[dict]:
        """Run a prompt through Claude CLI, yielding events."""
        ...

    @abstractmethod
    async def stop_all(self) -> None:
        """Stop all running CLI sessions."""
        ...

    @abstractmethod
    async def cleanup(self) -> None:
        """Release all sessions."""
        ...
```

### 5.3 SettingsAdapter

```python
class SettingsAdapter(ABC):
    """Abstracts access to Ralf-specific config from Free Cloud Settings."""

    @abstractmethod
    def get_max_iterations(self) -> int:
        ...

    @abstractmethod
    def get_completion_promise(self) -> Optional[str]:
        ...

    @abstractmethod
    def get_ralph_model(self) -> str:
        ...

    @abstractmethod
    def get_ralph_enabled(self) -> bool:
        ...

    @abstractmethod
    def get_memory_path(self) -> str:
        ...
```

### 5.4 MessagingAdapter (optional — for AgentTable → Discord/Telegram output)

```python
class MessagingAdapter(ABC):
    """Abstracts sending AgentTable results back to a messaging platform."""

    @abstractmethod
    async def send_message(
        self,
        chat_id: str,
        text: str,
    ) -> None:
        ...

    @abstractmethod
    async def send_status(
        self,
        chat_id: str,
        status: str,
    ) -> None:
        ...
```

### 5.5 Concrete Implementations

Each adapter gets a `FreeCloud{Name}` concrete class inside `plugins/ralph/adapters.py` that imports Free Cloud internals. This keeps the dependency boundary explicit:

```python
# Concrete implementation — imports Free Cloud internals here only
class FreeCloudProviderAdapter(ProviderAdapter):
    def __init__(self, registry: "ProviderRegistry", settings: "Settings"):
        self._registry = registry
        self._settings = settings

    async def generate(self, system_prompt: str, user_prompt: str,
                       model: Optional[str] = None) -> LLMResponse:
        provider_id = self._settings.parse_provider_type(model or self._settings.model)
        provider = self._registry.get(provider_id, self._settings)
        # ... call provider's chat completion ...
```

---

## 6. Phased Implementation Plan

### Phase 0: Foundation (files/dirs, no functional changes)

**Goal:** Create the plugin directory structure and wire it into the build system.

**Files to create:**
- `plugins/__init__.py` — empty, package marker
- `plugins/ralph/__init__.py` — stub, exports nothing yet
- `plugins/ralph/constants.py` — copy from Ralf, strip dependnecy-only items
- `plugins/ralph/adapters.py` — abstract interfaces only (no implementations)

**Files to edit:**
- `pyproject.toml` — add `plugins` to `[tool.hatch.build.targets.wheel.packages]`
- `pyproject.toml` — add `plugins` to `[tool.ruff.lint.isort].known-first-party`

**Risk:** None. Directory-only change.

**Tests:** Verify `from plugins.ralph import ...` works.

---

### Phase 1: Core State Machine + Settings

**Goal:** `RalphMode` class working inside Free Cloud, reading config from `Settings`.

**Files to copy/adapt:**
- `plugins/ralph/state.py` — adapted from `ralph_mode/state.py`
  - Replace `print()` with `logger.info()`
  - Remove `RALPH_DIR` — use `~/.fcc/ralph/` instead
  - Keep `RalphMode` class interface (enable, disable, iterate, etc.)
- `plugins/ralph/helpers.py` — adapted from `ralph_mode/helpers.py`
  - `_find_git_root` → use Free Cloud's existing utilities
  - `_validate_task_prompt` → keep as-is
  - `print_banner` → replace with `logger.info`

**Files to edit:**
- `config/settings.py` — add Ralf-specific fields:
  ```python
  ralph_enabled: bool = Field(default=False, validation_alias="RALPH_ENABLED")
  ralph_max_iterations: int = Field(default=20, validation_alias="RALPH_MAX_ITERATIONS")
  ralph_model: str = Field(default="nvidia_nim/z-ai/glm4.7", validation_alias="RALPH_MODEL")
  ```

**Risk:** Low. New settings don't affect existing functionality.

**Tests:**
- `RalphMode.enable()` creates `~/.fcc/ralph/` directory
- `RalphMode.iterate()` increments counter
- `RalphMode.disable()` cleans up directory
- Settings validators for new `RALPH_*` env vars

---

### Phase 2: Memory System

**Goal:** `MemoryStore` ready for use by AgentTable and scripts.

**Files to copy/adapt:**
- `plugins/ralph/memory.py` — from `ralph_mode/memory.py`
  - Change default path from `~/.ralph-memory` to `~/.fcc/ralph/memory/`
  - Replace `print()` with `loguru` logger calls
  - Expose `MemoryStore` as the primary class

**Risk:** Low-medium. Memory store has TF-IDF and JSON persistence — nothing that conflicts.

**Tests:**
- Memory CRUD (add, get, search)
- Memory decay and promotion
- Cross-session persistence

---

### Phase 3: Task System + Verification

**Goal:** TaskLibrary and verification commands ready for API integration.

**Files to copy/adapt:**
- `plugins/ralph/tasks.py` — from `ralph_mode/tasks.py`
  - Keep `TaskLibrary` class
  - Default `base_path` → point to `~/.fcc/ralph/tasks/` when no git root
- `plugins/ralph/verification.py` — from `ralph_mode/verification.py`
  - Add async `_run_verification_commands_async` using `asyncio.create_subprocess_exec`
  - Keep sync version for backward compat

**Risk:** Low. Self-contained module.

**Tests:**
- Task file parsing with YAML frontmatter
- Verification command extraction from markdown
- Async and sync command execution

---

### Phase 4: Admin API Integration

**Goal:** Ralf tasks, memory, scanner accessible via `/admin/ralph/*` endpoints.

**Files to create:**
- `api/ralph_routes.py` — new router:
  ```python
  router = APIRouter(prefix="/admin/ralph", tags=["ralph"])

  @router.post("/enable")
  async def ralph_enable(prompt: str, ...): ...

  @router.post("/disable")
  async def ralph_disable(): ...

  @router.get("/status")
  async def ralph_status(): ...

  @router.get("/tasks")
  async def list_tasks(): ...

  @router.post("/tasks/validate")
  async def validate_task(task_file: str): ...

  @router.post("/scan")
  async def run_scan(language: Optional[str] = None): ...

  @router.get("/memory")
  async def search_memory(query: str): ...
  ```

**Files to edit:**
- `api/admin_routes.py` — include `ralph_router`
- `api/admin_static/` — add Ralf management UI tabs (optional)

**Risk:** Low. New API prefix, no impact on existing `/v1/messages` or `/admin` routes.

**Tests:**
- HTTP 200 from each new endpoint
- Enable/disable cycle via API
- Task validation via API
- Scan with test project

---

### Phase 5: AgentTable as Optional Processing Mode

**Goal:** AgentTable can be used as an alternative processing pipeline in `ClaudeMessageHandler`.

**Files to copy:**
- `plugins/ralph/agent_table/` — entire directory (17 files), copied as-is
- `plugins/ralph/agent_table/__init__.py` — unchanged

**Files to create:**
- `plugins/ralph/agent_table/integration.py` — bridges AgentTable to Free Cloud:
  ```python
  class AgentTableProcessor:
      """Replaces the single-Claude-CLI processing with AgentTable deliberation."""

      def __init__(self, provider_adapter: ProviderAdapter, ...):
          self._table = AgentTable()
          ...

      async def process(self, prompt: str) -> AgentTableResult:
          """Run the full Doer→Critic→Arbiter cycle."""
          ...
  ```

**Files to edit:**
- `messaging/handler.py` — add optional AgentTable branch:
  ```python
  if ralph_enabled and self._agent_table_mode:
      return await self._agent_table_processor.process(incoming.text)
  ```

**Risk:** Medium. Must not break existing messaging flow. Gate behind `RALPH_AGENT_TABLE_MODE` env var.

**Tests:**
- AgentTable processes a simple prompt and returns result
- Fallback to normal processing when AgentTable fails
- No regression in existing message handler

---

### Phase 6: Async Loop Runner

**Goal:** Replace `ralph-loop.sh` with an async Python loop that uses `CLISessionManager`.

**Files to create:**
- `plugins/ralph/loop.py`:
  ```python
  class RalphLoopRunner:
      """
      Async replacement for ralph-loop.sh.
      
      Uses CLIAdapter to run Claude CLI sessions with:
      - Network resilience (exponential backoff)
      - Session checkpointing
      - Completion promise detection
      - Graceful shutdown via asyncio
      """

      def __init__(self, cli_adapter: CLIAdapter, state: RalphMode):
          ...
      
      async def run(self) -> None:
          """Main loop — runs prompts, checks completion, iterates."""
          ...
  ```

**Files to edit:**
- `cli/entrypoints.py` — add `fcc-ralph` entry point:
  ```python
  def ralph_loop() -> None:
      """Run Ralf loop (registered as fcc-ralph)."""
      asyncio.run(_ralph_loop_async())
  ```

**Risk:** Medium-high. Loop runner has custom retry/backoff logic that must be preserved.

**Tests:**
- Loop completes a fake task (with mocked CLI)
- Loop respects max_iterations
- Network failure triggers backoff
- Graceful shutdown via SIGINT

---

### Phase 7: Scanner + Polish + Documentation

**Goal:** Security scanner integrated into admin UI; full documentation.

**Files to copy/adapt:**
- `plugins/ralph/scanner.py` — from `ralph_mode/scanner.py`
  - Replace `print()` → `logger.info()`
  - Make CodeQL calls async via `asyncio.create_subprocess_exec`
  - Add scan results to `MemoryStore` automatically

**Files to edit:**
- `api/ralph_routes.py` — add scanner endpoints
- `api/admin_static/` — add scanner results display (optional)
- `AGENTS.md` — update with Ralf agent references
- `README.md` — document Ralf plugin

**Risk:** Low.

**Tests:**
- Scan with CodeQL (if codeql available)
- Scan fallback to grep
- Scan results returned correctly

---

## 7. MVP Identification

The smallest useful merge that proves the integration works:

### MVP Scope (Phase 0 + Phase 1 + Phase 4)

1. **Plugin directory structure** (`plugins/ralph/`) with a working `RalphMode` state machine
2. **Settings integration** — `RALPH_ENABLED`, `RALPH_MAX_ITERATIONS` env vars in `Settings`
3. **Ralph CLI** — `fcc-ralph enable/disable/status/iterate` commands working
4. **Admin API** — `GET /admin/ralph/status` returns current Ralph state

### What the MVP proves
- Ralf code can live inside Free Cloud's package tree
- Ralf reads config from Free Cloud's `Settings`
- Ralf state persists correctly
- Admin UI can monitor Ralf status

### What the MVP deliberately excludes
- AgentTable (Phase 5)
- Loop runner (Phase 6)
- Scanner (Phase 7)
- Memory integration with messaging
- Full task system

---

## 8. Dangerous Parts (Do NOT Merge Yet)

| Component | Danger | Mitigation |
|---|---|---|
| **AgentTable FSM** (agent_table/fsm.py) | Complex state machine with escalation paths. If it blocks message processing, users can't chat. | Gate behind opt-in flag. Never activate by default. |
| **ralph-loop.sh logic** | Shell script has `set -e`, subshell traps, signal forwarding. Python reimplementation may miss edge cases. | Phase 6 only. Keep original shell script as reference. |
| **MemoryStore with live traffic** | TF-IDF over user messages could leak data between sessions. | Only activate memory when `RALPH_ENABLED=True` and document privacy implications. |
| **Scanner `subprocess.run`** | Blocking subprocess in async context → freezes event loop. | Always use async version. 
| **File system state** | Ralf reads/writes `.ralph-mode/` directory. Conflicts with Free Cloud's `~/.fcc/` structure. | Migrate to `~/.fcc/ralph/`. Never write to project root by default. |

## 9. Dependency Conflict Check

### Current Dependencies

| Ralf (current) | Free Cloud | Conflict? | Resolution |
|---|---|---|---|
| Zero runtime deps | FastAPI, httpx, pydantic, etc. | None — Ralf's design choice of zero deps means no conflicts | N/A |
| `pytest` (dev) | `pytest` (dev) | Compatible | Keep single root `dev` group |
| `mypy` (dev) | Not present | No conflict | Add to root dev if wanted |
| `flake8` (dev) | Not present (uses ruff) | Style overlap | Drop flake8; Free Cloud uses `ruff` |
| Python >=3.10 | Python >=3.14 | None — 3.14 is a superset | Keep >=3.14 |

### Verdict: Zero dependency conflicts. Ralf has no runtime deps, so it can't conflict.

---

## 10. Final Recommended Folder Tree

```
free-claude-code/
├── server.py
├── pyproject.toml              ← plugins/ added to wheel packages
├── CLAUDE.md
├── AGENTS.md
├── .github/agents/
│   └── agent-creator.agent.md  ← from Ralf (optional)
│
├── api/
│   ├── app.py
│   ├── routes.py
│   ├── services.py
│   ├── model_router.py
│   ├── admin_routes.py
│   ├── ralph_routes.py          ← NEW: /admin/ralph/* endpoints
│   └── ...
│
├── cli/
│   ├── entrypoints.py           ← +fcc-ralph entry point
│   ├── manager.py
│   └── ...
│
├── config/
│   ├── settings.py              ← +RALPH_* env vars
│   └── ...
│
├── messaging/
│   ├── handler.py               ← +AgentTable integration (Phase 5, gated)
│   └── ...
│
├── plugins/                     ← NEW
│   ├── __init__.py
│   └── ralph/
│       ├── __init__.py
│       ├── state.py             ← RalphMode (adapted)
│       ├── memory.py            ← MemoryStore (adapted)
│       ├── context.py           ← ContextManager (adapted)
│       ├── tasks.py             ← TaskLibrary (adapted)
│       ├── verification.py      ← Verification (adapted, +async)
│       ├── scanner.py           ← CodeQL+grep (adapted)
│       ├── helpers.py           ← Validators, etc.
│       ├── constants.py         ← VERSION, colors
│       ├── adapters.py          ← Interfaces + concrete impls
│       ├── loop.py              ← NEW: async loop runner
│       ├── cli.py               ← Adapted Ralf CLI
│       ├── README.md
│       └── agent_table/
│           ├── __init__.py      ← Re-exports everything
│           ├── table.py
│           ├── fsm.py
│           ├── models.py
│           ├── roles.py
│           ├── strategies.py
│           ├── consensus.py
│           ├── scoring.py
│           ├── transcript.py
│           ├── state.py
│           ├── protocol.py
│           ├── context.py
│           ├── hooks.py
│           ├── validators.py
│           ├── interaction.py
│           ├── negotiation.py
│           ├── router.py
│           └── integration.py   ← NEW: bridges to Free Cloud
│
├── providers/
│   └── ... (17 providers, unchanged)
│
├── core/
│   └── ...
│
└── tests/
    ├── ...
    └── plugins/
        └── ralph/
            ├── test_state.py
            ├── test_memory.py
            ├── test_tasks.py
            ├── test_verification.py
            ├── test_scanner.py
            └── test_agent_table/
                └── ...
```

---

## 11. Decision Point

### Recommended Path

**Merge MVP first** (Phases 0+1+4), then iterate.

This gives you a working integration in ~1-2 days of work, proves the architecture, and lets you decide which Ralf features to prioritize next based on real usage.

### MVP Scope (concrete)

| Deliverable | Files Touched | Est. Effort |
|---|---|---|
| Plugin directory + build config | 2 new, 1 edit | 15 min |
| `RalphMode` state machine (adapted) | 1 new | 1 hr |
| `Settings` integration | 1 edit | 15 min |
| `fcc-ralph` CLI (enable/disable/status/iterate) | 2 new + 1 edit | 2 hr |
| `GET /admin/ralph/status` endpoint | 2 new (ralph_routes.py + edit admin_routes.py) | 1 hr |
| Basic tests | 4-5 test files | 1 hr |
| **Total MVP** | ~10 new files, ~3 edits | **~6 hours** |

### First Files to Touch (in order)
1. `pyproject.toml` — add `plugins` to wheel packages
2. `plugins/__init__.py` — create
3. `plugins/ralph/__init__.py` — create, minimal exports
4. `plugins/ralph/state.py` — adapt from Ralf
5. `config/settings.py` — add `RALPH_*` fields
6. `plugins/ralph/cli.py` — adapt from Ralf
7. `cli/entrypoints.py` — add `fcc-ralph`
8. `api/ralph_routes.py` — create admin endpoints
9. `api/admin_routes.py` — include ralph router

### Files to NOT Touch (unless specifically needed)
- `providers/` (any file) — Ralf does not change provider layer
- `messaging/handler.py` — not until Phase 5
- `messaging/platforms/` — unchanged
- `api/routes.py` — `/v1/messages` is stable
- `api/services.py` — not until Phase 5
- `api/models/` — unchanged
- `core/` — unchanged
- `config/provider_catalog.py` — unchanged

### Open Questions

1. **Should AgentTable be a full replacement for Claude CLI calls, or a pre/post-processor?** (default: replacement, gated behind a setting)
2. **Where should Ralf's `.ralph-mode/` state directory live?** (recommended: `~/.fcc/ralph/` to avoid polluting project directories)
3. **Should the loop runner support the Discord/Telegram queue?** (recommended: yes in Phase 6, via `CLIAdapter`)
4. **Should MemoryStore be shared across all messaging chats or per-chat?** (recommended: global by default, document the privacy implication)
5. **Do we keep the original Ralf pyproject.toml as a standalone reference?** (recommended: archive it in `plugins/ralph/standalone/` for reference)

---

### Summary

- **MVP takes ~6 hours**, proves the architecture, and is safe (no changes to existing Free Cloud functionality)
- **Full merge (7 phases) takes ~40-60 hours** depending on AgentTable integration depth
- **Zero dependency conflicts** — Ralf has no runtime deps
- **Dangerous areas** are clearly gated behind opt-in flags
- **Adapter layer** keeps a clean boundary between Ralf and Free Cloud internals
- **Recommended:** Start with MVP, then decide whether to add AgentTable, loop runner, or scanner next
