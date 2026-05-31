# U3-Lite Low-Cost Development Protocol

**Purpose:** Define a strict, token-saving development workflow for SEPCC-driven
Vega Claude tasks. This protocol replaces the earlier Ralph-loop / fan-out /
multi-agent approaches that proved too expensive.

---

## Core Rules

| # | Rule | Why |
|---|------|-----|
| 1 | **No Ralph loop by default** | Ralph loop costs 1+ DeepSeek call per iteration just for loop overhead |
| 2 | **No Agent Table by default** | Multi-agent deliberation costs 3-5 calls per round |
| 3 | **No simulated fan-out by default** | Sequential role-play costs 4+ calls per task |
| 4 | **Max 1 DeepSeek call per small task** | The implementation itself; everything else is shell/static |
| 5 | **Static inspection before LLM** | `grep`, `find`, `head` cost nothing — use them first |
| 6 | **Small diffs only** | Prefer new files over edits; prefer <200 lines per commit |
| 7 | **Tests before commit** | All new testable code must have a pytest companion |
| 8 | **Push only after commit succeeds** | No partial or broken pushes |
| 9 | **User reviews output** | All staged changes are user-visible before push |

## Standard Task Lifecycle

```
1. Preflight          Verify SEPCC health, branch, port 8082
2. Static inspection  grep/find/head the relevant area (no LLM)
3. Implement          Write the files directly (or 1 DeepSeek call max)
4. Test               py_compile + pytest
5. Diff               git diff --stat, check for unexpected files
6. Commit             git add + git commit -m "..."
7. Push               git push origin ralph-r1-temp
8. Verify             User confirms commit hash and push result
```

## Forbidden Actions

- Running Ralph `ralph-loop.sh` or `ralph-loop-guarded.sh`
- Running `ralph-mode table` for multi-agent deliberation
- Simulating fan-out with multiple sequential SEPCC calls
- Reading research repos with LLM (use `grep`/`head` for patterns)
- Creating long planning documents (>200 lines)
- Modifying main workspace `/opt/vega-cloud/vega_claude/free-claude-code`
- Touching runtime dirs (`.fcc/`, `.ralph-mode/`, `.claude/`)
- Printing or committing env files, secrets, or credentials

## Allowed Research Usage

If a research repo must be consulted for a pattern:
1. Use `find $repo -name "*.md" | head -5` to locate relevant docs
2. Use `head -80 $file` to read short snippets
3. If the snippet is insufficient and the task truly requires the pattern,
   use **at most 1 DeepSeek call** to extract the pattern

## Stop Conditions

| Condition | Action |
|-----------|--------|
| SEPCC unhealthy | Stop, fix SEPCC first |
| Main workspace modified | Stop, restore, report |
| Port 8082 changed | Stop immediately |
| Secret/credential found in diff | Stop, remove, report |
| Test fails | Stop, fix, re-run |
| Unexpected file appears in `git status` | Stop, audit, remove |

U3_LOW_COST_PROTOCOL_READY
