# Phase 9.16T3 — Telegram Mini App Full Control Report

**Date:** 2026-05-31
**Phase:** 9.16T3
**Status:** MVP Complete, Awaiting HTTPS Setup

## Overview

A full-control Telegram Mini App was built for managing SEPCC/VegaClaw directly from
Telegram. The Mini App provides a complete operational dashboard: prompts, live logs,
git operations, verification checks, and SEPCC process control — all gated behind
Telegram WebApp initData validation.

## Architecture Decision

A separate FastAPI backend was created (port 19090) rather than extending the existing
SEPCC `/admin` routes, because:

1. SEPCC admin routes are loopback-only (require_loopback_admin)
2. Telegram Mini App needs public HTTPS access
3. Different auth model (initData vs loopback)
4. Keeps VegaClaw source unmodified (documentation only)

## Location

- **Working copy:** `/opt/vega-cloud/spc/miniapp/`
- **Final destination:** `/opt/vega-cloud/miniapp/` (needs `sudo mkdir + chown`)
- **Backend:** FastAPI + uvicorn on `127.0.0.1:19090`
- **Frontend:** Static HTML/CSS/JS (mobile-first, Telegram dark mode)

## Integration with VegaClaw

The Mini App operates in the VegaClaw workspace:
- **Workspace:** `/opt/vega-cloud/vega_claude/free-claude-code`
- **Git commands:** Run against the VegaClaw monorepo
- **Prompts:** Executed via `uv run fcc-claude --print` through SEPCC
- **Checks:** uv-based ruff, pytest, ty in the SEPCC project
- **Logs:** SEPCC server logs streamed via SSE

## Security

The Mini App does NOT:
- Modify VegaClaw source
- Access research repos
- Expose env files or tokens
- Allow arbitrary shell commands
- Run as root

All destructive actions require explicit confirmation, even for the allowed user.

## Current Status

| Item                | Status                                    |
|---------------------|-------------------------------------------|
| Backend             | Running on 127.0.0.1:19090                |
| Frontend            | Served from /static                        |
| Auth                | HMAC-SHA-256 initData validation           |
| Dev Bypass          | Disabled (secure default)                  |
| SEPCC               | Healthy on 127.0.0.1:18083                 |
| Port 8082           | Untouched                                  |
| HTTPS               | Caddy available, route not yet configured  |
| Telegram Menu       | Not yet set (needs public URL)             |

## Next Steps

1. User creates `/opt/vega-cloud/miniapp/` with correct permissions
2. User adds Caddy route for `vega.welinkup.org → 127.0.0.1:19090`
3. Set `VEGA_MINIAPP_PUBLIC_URL`
4. Run `miniapp-set-menu-button.sh`
5. End-to-end Telegram testing
