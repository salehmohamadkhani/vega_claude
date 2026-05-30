# Research Corpus V1 — Bootstrap Plan

**Date:** 2026-05-30
**Status:** Plan — no implementation yet
**Purpose:** Define the Research Corpus that feeds domain knowledge into Agent Council V2

---

## 1. Overview

The Research Corpus is a curated collection of 40–50 high-quality GitHub repositories that serve as the domain knowledge base for Agent Council V2. Each repo is studied, indexed, and distilled into patterns that agents use for implementation guidance.

### Why a Research Corpus

Agent Council V2 agents need domain expertise. They need to know:

- What does a well-structured React component tree look like?
- How do production APIs handle error responses?
- What database schema patterns work at scale?
- How do real CI/CD pipelines handle multi-environment deployments?
- What does a proper threat model look like?

The Research Corpus answers these questions with evidence from real, high-quality production codebases — not synthetic examples.

---

## 2. Research Root Path

```
/opt/vega-cloud/research/
```

This is **outside** the VegaClaw source tree. Research data must never be mixed with VegaClaw source.

---

## 3. Folder Structure

```
/opt/vega-cloud/research/
├── repos/                          # Cloned repositories (read-only)
│   ├── <org>-<repo>/               # e.g., facebook-react/
│   │   └── .git/                   # Shallow clone
│   └── ...
│
├── repo-cards/                     # Structured analysis per repo
│   ├── <org>-<repo>.yaml           # Machine-readable card
│   └── <org>-<repo>.md             # Human-readable notes
│
├── indexes/                        # Searchable indexes
│   ├── by-category.yaml            # Group repos by category
│   ├── by-agent.yaml               # Map repos to agents
│   ├── by-pattern.yaml             # Cross-cutting pattern index
│   └── full-text.db                # SQLite FTS index (optional)
│
├── notes/                          # Analysis notes
│   ├── patterns/                   # Pattern summaries across repos
│   ├── anti-patterns/              # Common mistakes found
│   └── comparisons/                # Cross-repo comparisons
│
├── logs/                           # Indexing and analysis logs
│   ├── clone-<date>.log
│   ├── index-<date>.log
│   └── errors.log
│
└── rejected/                       # Repos considered but rejected
    ├── <org>-<repo>.yaml           # Rejection reason
    └── ...
```

---

## 4. Target Repo Count

**40–50** high-quality GitHub repositories.

Why this count:
- Enough to provide cross-repo pattern validation
- Few enough that each repo gets deep analysis, not shallow scanning
- Manageable acquisition and indexing time
- Covers all 15 agent-relevant categories with 2–5 repos each

---

## 5. Selection Criteria

Every repo must satisfy **all** mandatory criteria and **at least 3** preferred criteria.

### Mandatory Criteria

| # | Criterion |
|---|---|
| M1 | High-quality code — clean architecture, meaningful tests, documentation |
| M2 | Real production use OR strong community adoption (100+ stars, active maintenance) |
| M3 | Clear architecture — understandable module boundaries, named patterns |
| M4 | Relevant to at least one agent category (see Section 6) |
| M5 | Not abandoned (commits within last 12 months) unless historically significant (landmark projects) |
| M6 | Permissive or readable license (MIT, Apache 2.0, BSD, GPL with LGPL linking, MPL) |

### Preferred Criteria

| # | Criterion | Weight |
|---|---|---|
| P1 | Strong test suite (≥ 60% coverage or visible testing culture) | High |
| P2 | Comprehensive documentation (README, CONTRIBUTING, architecture docs) | High |
| P3 | Multiple contributors (not a solo project) | Medium |
| P4 | CI/CD pipeline visible (GitHub Actions, CircleCI, etc.) | Medium |
| P5 | Semantic versioning and changelog | Low |
| P6 | Demonstrated accessibility practices | Low |
| P7 | Active issue/PR triage | Low |

### Rejection Criteria

| # | Criterion |
|---|---|
| R1 | Licensed under non-permissive terms preventing study |
| R2 | Contains primarily generated/minified code |
| R3 | Malware, spam, or known security risks |
| R4 | Too trivial — single-file projects, tutorial repos |
| R5 | Too large to study effectively (> 10K files, enterprise monoliths) |

---

## 6. Repo Categories

Each category maps to one or more Agent Council V2 layers.

### Category → Agent Mapping

| Category | Target Count | Relevant Agent Layers |
|---|---|---|
| Multi-agent orchestration | 3–4 | Orchestration, Arbitration (Layer 17) |
| Software engineering agents | 3–4 | Architecture, Backend, Frontend (Layers 7–9) |
| Code review / quality tools | 2–3 | QA, Security (Layers 11–12) |
| Product / design systems | 3–4 | UX/UI Design, Brand (Layers 5–6) |
| UI component libraries | 3–4 | Frontend, Design System (Layers 6, 8) |
| Browser automation / testing | 2–3 | QA, Test Automation (Layer 11) |
| Debugging / self-healing systems | 2–3 | QA, DevOps, SRE (Layers 11, 13–14) |
| Backend / API frameworks | 3–4 | Backend, API Architecture (Layers 7, 9) |
| Database / schema tooling | 2–3 | Database, Data Engineering (Layer 10) |
| DevOps / deployment tooling | 3–4 | DevOps, Infrastructure (Layer 13) |
| Security scanning / hardening | 2–3 | Security, Compliance (Layer 12) |
| Observability / monitoring | 2–3 | Observability, SRE (Layer 14) |
| Marketing / SEO / content | 1–2 | Brand, Content, Growth (Layers 5, 15) |
| Analytics / growth tooling | 1–2 | Growth, Analytics (Layer 15) |
| Evaluation / scoring frameworks | 2–3 | QA, Arbitration (Layers 11, 17) |

---

## 7. Repo Card Schema

Each cloned repo gets a machine-readable YAML card and a human-readable notes file.

### YAML Card Schema

```yaml
repo_id: "<org>-<repo>"                     # e.g., facebook-react
name: "<Human-readable name>"
url: "https://github.com/<org>/<repo>"
stars: <integer>
license: "<SPDX identifier>"
last_activity: "<YYYY-MM-DD>"
primary_language: "<language>"
category:
  - "<primary category>"
  - "<secondary category>"
agent_relevance:
  - agent_id: "<agent_id>"                 # e.g., senior_frontend_developer
    relevance: "high|medium|low"
    why: "<one-line reason>"
key_patterns:
  - pattern: "<pattern name>"
    description: "<what makes this pattern notable>"
    files: ["path/to/file1", "path/to/file2"]
files_to_study:
  - path: "<file path>"
    reason: "<why this file is worth studying>"
risks:
  - "<risk 1>"
  - "<risk 2>"
do_not_copy:
  - "<pattern/approach that looks good but should not be replicated>"
recommended_use_in_vegaclaw: "<specific recommendation for Agent Council V2>"
clone_date: "<YYYY-MM-DD>"
analysis_date: "<YYYY-MM-DD>"
analyst_notes: "<freeform notes>"
```

### Human-Readable Notes

The `.md` file contains:
- Executive summary (3–5 sentences)
- Architecture overview
- Key design decisions and rationale
- Notable patterns with file references
- Anti-patterns or concerns
- Test strategy observations
- CI/CD pipeline observations
- What VegaClaw should learn from this repo

---

## 8. How Research Corpus Feeds Agent Council

### Direct Mapping

Each repo maps to one or more agents. When an agent is activated for a project, the Orchestrator pulls relevant repo cards and pattern summaries into the agent's context.

```
Project: Build a SaaS dashboard
   │
   ├─ Agent: Senior Frontend Developer
   │   └─ Context: react repo card + design-system repo card + frontend-patterns summary
   │
   ├─ Agent: Senior Backend Developer
   │   └─ Context: fastapi repo card + django repo card + api-patterns summary
   │
   └─ Agent: Database Developer
       └─ Context: prisma repo card + postgres-patterns summary
```

### Pattern Extraction

Common patterns across multiple repos become:

1. **Implementation guidance** — "In 8 of 10 backend repos, error handling follows this pattern..."
2. **Default choices** — "7 of 8 React repos use this state management approach..."
3. **Anti-patterns** — "3 repos had this subtle bug pattern; avoid by..."
4. **Architecture decisions** — "Monorepo vs polyrepo: pros/cons from 5 studied codebases..."

### Evidence Citation

Future VegaClaw design docs and agent decisions cite Research Corpus evidence:

> "Decision: Use repository pattern for data access. Evidence: 4 of 5 studied backend repos use this pattern successfully at scale (django/django, pallets/flask, tiangolo/fastapi, encode/httpx)."

---

## 9. Phase 9.15B Execution Plan

### Step 1: Create folder structure

```bash
mkdir -p /opt/vega-cloud/research/{repos,repo-cards,indexes,notes/{patterns,anti-patterns,comparisons},logs,rejected}
```

### Step 2: Select repo list

Curate the preliminary list of 40–50 repos. Each selection must cite which selection criteria it satisfies and which agents it serves.

### Step 3: Clone repos

Shallow clone (`--depth 1`) each repo into `/opt/vega-cloud/research/repos/`. Repos are read-only — never modified.

Expected total size: 2–5 GB (shallow clones of medium-sized repos).

### Step 4: Generate repo cards

For each cloned repo, produce:
- `<org>-<repo>.yaml` (machine-readable card)
- `<org>-<repo>.md` (human-readable notes)

This is the most time-intensive step. Each card requires reading the repo's structure, architecture, tests, and documentation.

### Step 5: Build indexes

Generate:
- `by-category.yaml` — repos grouped by category
- `by-agent.yaml` — repos mapped to agent IDs
- `by-pattern.yaml` — cross-cutting patterns with repo references

### Step 6: Summarize patterns

Aggregate findings into:
- Pattern summaries (what works, with evidence)
- Anti-pattern catalog (what to avoid, with examples)
- Cross-repo comparisons (different approaches to same problem)

### Step 7: Validate

- Every repo has a card
- Every agent in the taxonomy has at least 2 relevant repos
- Every pattern claim has evidence (repo + file reference)

---

## 10. Preliminary Repo Candidates

The following is a **preliminary list** to be finalized during Phase 9.15B. Each candidate must pass the selection criteria audit before cloning.

### Multi-Agent Orchestration (3–4)
- `microsoft/autogen` — Multi-agent conversation framework
- `langchain-ai/langgraph` — Agent orchestration with state machines
- `crewAIInc/crewAI` — Role-based AI agent framework
- `significant-gravitas/AutoGPT` — Autonomous AI agent (historically significant)

### Software Engineering Agents (3–4)
- `sweepai/sweep` — AI-powered junior developer
- `cursor-ai/cursor` (or study papers if code unavailable) — AI-first IDE
- `OpenDevin/OpenDevin` — Autonomous AI software engineer
- `princeton-nlp/SWE-agent` — Language model for software engineering

### Code Review / Quality (2–3)
- `reviewpad/reviewpad` — Automated code review
- `coderabbitai/ai-pr-reviewer` — AI pull request review
- `astral-sh/ruff` — Fast Python linter (study quality tool architecture)

### Product / Design Systems (3–4)
- `tailwindlabs/tailwindcss` — Design system as code
- `radix-ui/primitives` — Accessible component primitives
- `shadcn-ui/ui` — Component distribution pattern
- `storybookjs/storybook` — UI component development environment

### UI Component Libraries (3–4)
- `mui/material-ui` — Mature React component library
- `chakra-ui/chakra-ui` — Accessible component library
- `ant-design/ant-design` — Enterprise UI framework
- `nextui-org/nextui` — Modern React UI library

### Browser Automation / Testing (2–3)
- `microsoft/playwright` — Cross-browser automation
- `cypress-io/cypress` — Frontend testing framework
- `webdriverio/webdriverio` — Browser testing framework

### Debugging / Self-Healing (2–3)
- `facebook/react` (error boundaries, devtools) — Error handling patterns
- `getsentry/sentry` — Error monitoring
- `hyperdxio/hyperdx` — Open-source observability

### Backend / API Frameworks (3–4)
- `tiangolo/fastapi` — Modern Python API framework
- `encode/httpx` — HTTP client (study async patterns)
- `django/django` — Mature web framework (study architecture at scale)
- `pallets/flask` — Micro-framework (study minimalism)

### Database / Schema Tooling (2–3)
- `prisma/prisma` — Modern database toolkit (study schema management)
- `sqlalchemy/sqlalchemy` — Python SQL toolkit (study ORM patterns)
- `supabase/supabase` — Open-source Firebase alternative

### DevOps / Deployment (3–4)
- `vercel/next.js` — Full deployment pipeline study
- `docker/compose` — Container orchestration
- `kubernetes/kubernetes` — Container orchestration at scale
- `hashicorp/terraform` — Infrastructure as code

### Security Scanning (2–3)
- `aquasecurity/trivy` — Vulnerability scanner
- `github/codeql` — Code analysis
- `zaproxy/zaproxy` — Web app security scanner

### Observability / Monitoring (2–3)
- `grafana/grafana` — Observability platform
- `open-telemetry/opentelemetry-js` or `-python` — Observability framework
- `prometheus/prometheus` — Monitoring system

### AI/ML Engineering (additional)
- `huggingface/transformers` — State-of-the-art ML
- `langchain-ai/langchain` — LLM application framework
- `microsoft/TypeChat` — Type-safe natural language interfaces

### Evaluation / Scoring (2–3)
- `microsoft/promptflow` — LLM evaluation framework
- `langchain-ai/langsmith-sdk` — LLM observability and evaluation
- `confident-ai/deepeval` — LLM evaluation framework

**Total preliminary candidates: ~50**. This list will be audited and pruned during Phase 9.15B based on selection criteria.

---

## 11. Safety and Constraints

### Do Not

- ❌ Modify cloned repos
- ❌ Mix research data with VegaClaw source
- ❌ Commit research data to the VegaClaw git repo
- ❌ Expose repos publicly through VegaClaw
- ❌ Run code from cloned repos without review
- ❌ Copy code directly from cloned repos into VegaClaw (study patterns, not copy code)
- ❌ Use repos with incompatible licenses

### Do

- ✅ Shallow clone only (`--depth 1`)
- ✅ Keep research at `/opt/vega-cloud/research/` (separate from source)
- ✅ Add research directory to `.gitignore` of VegaClaw if needed
- ✅ Attribute all patterns to their source repos
- ✅ Respect license terms — study, don't copy

---

## 12. Timeline Estimate

| Step | Estimated Duration |
|---|---|
| Create folder structure | < 1 minute |
| Finalize repo list (audit against criteria) | 1 session |
| Clone repos (parallel, 4 at a time) | ~10 minutes |
| Generate repo cards (deep analysis per repo) | 2–3 sessions |
| Build indexes | 1 session |
| Summarize patterns | 1–2 sessions |
| Validate completeness | 1 session |
| **Total** | **5–8 sessions** |

---

## 13. Success Criteria

Phase 9.15B is complete when:

1. 40–50 repos cloned at `/opt/vega-cloud/research/repos/`
2. Every repo has a machine-readable card and human-readable notes
3. Indexes by category, agent, and pattern are generated
4. At least 20 cross-repo patterns documented with evidence
5. Every Agent Council V2 agent has at least 2 relevant repo references
6. No research data in VegaClaw source tree
7. All repo licenses verified as compatible

---

## 14. Constraint Compliance

- ✅ No repos cloned yet — plan only
- ✅ Research root outside VegaClaw source
- ✅ Phase 10 not started
- ✅ No source code changes
- ✅ Working inside VegaClaw documentation only
- ✅ Index structure designed for agent consumption
- ✅ Repo card schema designed for machine readability
