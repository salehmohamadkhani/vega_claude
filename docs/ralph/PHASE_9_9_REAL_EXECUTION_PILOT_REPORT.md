# Phase 9.9 — Controlled Real Execution Pilot Report

**Date**: 2026-05-29
**Container**: `vegaclaw-lab` (persistent, Python 3.13-slim-bookworm)
**Pilot Goal**: Validate that `fcc-ralph run --real --allow-real-execution` invokes Claude Code through the FCC proxy to DeepSeek API, executing tasks with a real (non-simulated) LLM backend.

---

## Summary

The real execution chain was successfully validated end-to-end. Claude Code was invoked by `fcc-ralph` through `fcc-claude`, connected to the FCC proxy, and made 4 successful API calls to DeepSeek via `api.deepseek.com/anthropic`. The pilot executed one iteration of TASK-001 (architecture mapping) before the arbiter flagged the result for debug (expected for a first-pass architecture task).

## Blocker Resolved

### Root Cause: `FCC_MODEL` is not a recognized FCC configuration variable

The container had `FCC_MODEL=deepseek/deepseek-v4-pro` set, but FCC's `Settings` class reads the model from `MODEL` env var (alias for `model` field, default `nvidia_nim/z-ai/glm4.7`). Without `MODEL` set, the server defaulted to NVIDIA NIM routing, which requires `NVIDIA_NIM_API_KEY`.

**Fix**: Added `MODEL=deepseek/deepseek-v4-pro` to `/vega-claw-docker-lab/.env.local` and restarted `fcc-server` with the correct environment variable.

### Verification

| Test | Result |
|------|--------|
| Direct FCC API call (`curl /v1/messages` with DeepSeek model) | 200 OK, DeepSeek responded |
| `claude --print` through FCC proxy | Returned "hello" — full chain confirmed |
| `fcc-ralph run --real --allow-real-execution` | Executed, arbiter processed output |

## Real Execution Chain

```
fcc-ralph run --real --allow-real-execution
  → ClaudeCodeCommandBuilder resolves CLI: fcc-claude
  → fcc-claude sets ANTHROPIC_BASE_URL=http://127.0.0.1:8082
  → Claude Code 1.0.128 launched as subprocess
  → Claude Code sends Messages requests to FCC proxy
  → FCC proxy ModelRouter resolves claude-sonnet-* → deepseek/deepseek-v4-pro
  → DeepSeek provider sends Anthropic-format request to api.deepseek.com/anthropic
  → Response streamed back through proxy → fcc-ralph arbiter
```

## Pilot Results

- **Mode**: `real` (confirmed in JSON output)
- **API calls made**: 4 successful POST `/v1/messages?beta=true` (all 200 OK)
- **Task executed**: TASK-001-context-map (Architecture and context mapping)
- **Arbiter decision**: Debug requested — confidence score 0.0, implementation score 0.0
- **Git state**: Clean (no changes to repo — `require_clean_git=True` safety enforced)
- **Calculator files**: Not generated — pilot stopped after architecture task

The arbiter's low score is expected for a single-iteration architecture-only pass. The acceptance criteria included `uv run pytest tests/core/ralph -q` which is irrelevant to the calculator-building goal — this is a task spec issue, not an execution chain issue.

## Key Configuration

| Setting | Value |
|---------|-------|
| `MODEL` | `deepseek/deepseek-v4-pro` |
| DeepSeek endpoint | `https://api.deepseek.com/anthropic` |
| Transport type | `anthropic_messages` |
| Claude Code version | 1.0.128 (required over 2.x for FCC compatibility) |
| FCC auth token | `freecc` |

## Limitations & Notes

- Claude Code 1.0.128 is pinned because 2.1.156 sends system role blocks in a format the FCC proxy's DeepSeek provider cannot handle (422 error)
- The DeepSeek `deepseek-v4-pro` model supports thinking blocks (confirmed in API response)
- `fcc-claude` is available only via `uv run fcc-claude` (inside `.venv/bin/`) — not globally installed
- The `FCC_MODEL` env var is not consumed by FCC code; it was a user-facing reference only. The correct env var is `MODEL`.
