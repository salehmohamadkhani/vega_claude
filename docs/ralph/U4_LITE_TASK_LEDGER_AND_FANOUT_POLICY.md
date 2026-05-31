# U4-Lite Task Ledger and Fan-Out Policy

**Purpose:** Define a lightweight task tracking ledger and the conditions under
which the more expensive fan-out development mode may be used as an exception
to the default SEPCC Direct mode.

---

## Default Mode

**SEPCC Direct** is the default for all tasks (as defined in
[U3-Lite](U3_LITE_LOW_COST_DEVELOPMENT_PROTOCOL.md)).

Fan-out may be used only when explicit escalation criteria are met.

## Fan-Out Escalation Criteria

Fan-out may be proposed only when **at least one** of these is true:

| # | Criterion | Example |
|---|-----------|---------|
| 1 | Task touches more than 3 modules or subsystems | Cross-cutting refactor |
| 2 | Task affects auth, secrets, permissions, networking, or deployment | Credential rotation, network change |
| 3 | Task requires architectural decision-making | New subsystem, protocol change |
| 4 | Task requires reading multiple research repos | Pattern extraction across 3+ repos |
| 5 | Task modifies production behavior (not just docs/tests) | Runtime logic, API change |
| 6 | Direct SEPCC attempt failed once + root cause unclear | Implementation bug not reproducible |
| 7 | User explicitly asks for fan-out | User request bypasses all other gates |
| 8 | Safety, security, or data-loss risk is high | Destructive operation, data migration |

## Fan-Out Approval Process

If fan-out is needed:

1. **Report why** — list which criteria are met, what information is missing.
2. **Ask for approval** — do not start fan-out without explicit user consent.
3. **Max 3 agents** — no more than 3 simultaneous or sequential fan-out calls.
4. **Read-only planning first** — fan-out agents may inspect files but not modify.
5. **No implementation during planning** — fan-out ends after a summary report.
6. **One summary call** — after all agents finish, a single synthesis call.
7. **Stop if cost is high** — if estimated calls exceed 10, stop and report.

## Token / Cost Management

| Rule | Detail |
|------|--------|
| Direct mode cost | 0-1 DeepSeek calls per task |
| Fan-out planning cost | 3-4 DeepSeek calls (summarised to 1) |
| Fan-out approval required? | Yes, always |
| Max total calls per task (fan-out) | 5 (3 agents + 1 summary + 1 implementation) |
| Cost reported per task | Yes, in ledger |

## Standard Task Ledger Template

```
task id:       U<N>-LITE
date:          YYYY-MM-DD
mode:          direct | fan-out
fan-out why:   (criteria met, or "not needed")
est. LLM calls: <number>
actual LLM calls: <number>
files changed: <paths>
tests run:     <number> | <result>
commit hash:   <sha>
push result:   success | blocked — <reason>
GitHub verification: <commit URL or "pending">
next task:     <name>
```

## Stop Conditions

| Condition | Action |
|-----------|--------|
| Fan-out requested without approval | Stop, ask user |
| Estimated cost > acceptable | Stop, report, ask |
| Any agent fails | Stop, report, fall back to direct |
| Unsafe file accessed | Stop, investigate |
| Port 8082 changed | Stop immediately |

U4_TASK_LEDGER_POLICY_READY
