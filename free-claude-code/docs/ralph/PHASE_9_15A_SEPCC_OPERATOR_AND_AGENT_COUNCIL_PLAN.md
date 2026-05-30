# Phase 9.15A — SEPCC Operator & Agent Council V2 Plan

**Date:** 2026-05-30
**Status:** Documentation complete
**Type:** Architecture design — no source code changes

---

## 1. Server Paths

| Item | Path |
|---|---|
| Vega Cloud root | `/opt/vega-cloud` |
| **SEPCC operator/reference repo** | `/opt/vega-cloud/fcc-upstream` |
| VegaClaw repo | `/opt/vega-cloud/vega_claude` |
| **VegaClaw app root** | `/opt/vega-cloud/vega_claude/free-claude-code` |

## 2. SEPCC Operator Path

SEPCC is installed at `/opt/vega-cloud/fcc-upstream`. This is the **active operator** replacing the old FCC server. No edits are made to SEPCC unless the task is specifically about SEPCC itself.

## 3. VegaClaw App Root

All VegaClaw development happens inside `/opt/vega-cloud/vega_claude/free-claude-code`. This is where Agent Council V2, Research Corpus, and all future phases live.

## 4. Route Status

| Route | Address | Status |
|---|---|---|
| **SEPCC (active)** | `127.0.0.1:18083` | ✅ Healthy (`{"status":"healthy"}`) |
| Old FCC (fallback only) | `127.0.0.1:18082` | ⚠️ May still exist — not in use |
| Foreign proxy (unrelated) | `0.0.0.0:8082` | ✅ Preserved — owned by `/opt/sub-proxy-foreign.py` |

## 5. VegaClaw → SEPCC Smoke

The VegaClaw-to-SEPCC smoke test passed with `VEGA_TO_SEPCC_OK`. The SEPCC proxy layer is confirmed operational:

- Health endpoint responds
- DeepSeek V4 Pro/Flash models are configured
- Claude Opus 4, Sonnet 4, Haiku 4 models are available
- System-message schema patch is in place (`api/models/anthropic.py:95`)
- VegaClaw can route API calls through SEPCC correctly

## 6. Port 8082

Port `0.0.0.0:8082` is owned by `/opt/sub-proxy-foreign.py` (PID 816712). It is **untouched** and must remain untouched. VegaClaw does not use this port.

## 7. Old FCC (18082)

The old FCC server at `127.0.0.1:18082` may still be running as a fallback. It is NOT the active operator. All routing goes through SEPCC at `127.0.0.1:18083`. Do not use the old fallback unless explicitly asked.

## 8. Admin UI

Not required. Headless server mode is sufficient for all operations.

## 9. Why Agent Council V2 is Needed

### Current State: Ralph Runtime Orchestration Roles

The Ralph Runtime has 8 orchestration-oriented roles:

| Role | Responsibility |
|---|---|
| Planner | Breaks goals into tasks |
| Architect | Defines system structure |
| Doer | Executes implementation tasks |
| Critic | Reviews output quality |
| Verifier | Runs verification commands |
| Debugger | Fixes failures |
| Arbiter | Decides approve/retry/escalate/stop |
| Summarizer | Produces final reports |

These roles manage the **task lifecycle** — planning, building, verifying, reviewing, debugging, deciding. But they lack **domain expertise**.

### The Gap

The existing roles are a generic pipeline. When a project goal requires:

- Market research before product definition
- UX research before UI design
- Security review before deployment
- Growth analytics after launch
- Coordinated multi-discipline design (brand + product + engineering)

...the current system has no way to model these specialized concerns.

### What Agent Council V2 Adds

Agent Council V2 introduces **domain-specialized agents** that:

1. **Own specific expertise domains** — frontend, backend, database, security, UX, business, etc.
2. **Understand dependency chains** — a UI Designer needs Brand Strategy; a Backend Developer needs an API Contract.
3. **Pass structured artifacts** — not ad-hoc messages, but validated contracts between agents.
4. **Operate in parallel where possible** — independent agents work concurrently; dependent agents wait.
5. **Submit to arbitration** — a Final Arbiter evaluates evidence from all agents before declaring a project complete.

### The Artificial Company Model

The agents are organized as an **artificial product-building company**:

```
Executive Layer    → vision, strategy, go/no-go decisions
Product Layer      → requirements, roadmaps, user stories
Design Layer       → brand, UX, UI, design systems
Engineering Layer  → architecture, frontend, backend, database
Quality Layer      → testing, security, performance, accessibility
Operations Layer   → deployment, observability, reliability
Growth Layer       → analytics, SEO, content, marketing
Governance Layer   → arbitration, compliance, project memory
```

This mirrors how a real product company operates — but executed by AI agents with structured handoffs.

## 10. Why Research Corpus Should Be Guided by Agent Taxonomy

The Research Corpus (Phase 9.15B) will collect 40–50 high-quality GitHub repos. Without a taxonomy, this becomes a random collection of code.

### Taxonomy-First Approach

1. **Each agent in the taxonomy defines what it needs to learn** — a Frontend Engineering agent needs to study React patterns, not database migration tools.
2. **Repo selection is driven by agent relevance** — every repo in the corpus must be directly useful to at least one agent category.
3. **Repo cards map to agents** — each repo's patterns, risks, and recommended uses are tagged by agent relevance.
4. **Fail conditions are derived from real-world anti-patterns** — the corpus provides evidence for what NOT to do.
5. **Artifact contracts are validated against corpus patterns** — does the API Contract template match real-world high-quality APIs?

### The Sequence

```
Agent Taxonomy (9.15A) → Repo Selection Criteria → Repo Cloning (9.15B) →
Repo Cards → Index → Pattern Summaries → Agent Implementation (9.16)
```

Designing the taxonomy first ensures the Research Corpus serves clear purposes and avoids wasted effort on irrelevant repos.

## 11. Phase Structure

| Phase | Name | Description |
|---|---|---|
| **9.15A** | Agent Council V2 Taxonomy & Plan | THIS PHASE — docs and specs only |
| 9.15B | Research Corpus Bootstrap | Clone 40–50 repos, build repo cards, index |
| 9.16 | Agent Council V2 Implementation | Build the agent runtime with domain agents |
| 10 | (Deferred) | Playwright KPI verifier, browser automation, async loop, admin UI |

## 12. Constraint Compliance

- ✅ No source code changed
- ✅ No Phase 10 started
- ✅ No Playwright/browser automation
- ✅ No repo cloning yet
- ✅ No SEPCC edits
- ✅ Port 8082 untouched
- ✅ Admin UI not used
- ✅ No secrets printed
- ✅ Working inside VegaClaw only

## Summary

| Metric | Status |
|---|---|
| SEPCC Server (18083) | HEALTHY |
| VegaClaw Repo | CLEAN (master) |
| Vega → SEPCC Smoke | PASSED |
| Port 8082 | UNTOUCHED |
| Old FCC (18082) | FALLBACK ONLY |
| Source Changed | NO |
| Admin UI Required | NO |
| Blockers | NONE |
