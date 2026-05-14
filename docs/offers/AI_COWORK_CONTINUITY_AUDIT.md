# AI Co-work Continuity Audit

## One-line offer

A 2-week audit that finds where AI co-work breaks, where agents continue from missing context, and what repair gates should exist before continuation, memory, or action.

## Core thesis

```text
Continuity before continuation.
Evidence before action.
Consent before memory.
Repair before judgment.
```

## Who this is for

Best-fit teams:

- DevTools teams building coding-agent workflows;
- AI-heavy engineering teams using Claude, Codex, Cursor, Copilot, or internal agents;
- platform teams experimenting with agentic PR review, CI autofix, or automated implementation;
- AI safety / governance teams evaluating long-running agent sessions;
- security or risk teams reviewing agent-assisted workflows before production automation.

## The expensive failure

AI co-work is becoming multi-session and multi-agent:

```text
Claude
+ Codex
+ IDE agent
+ PR
+ branch state
+ ticket
+ chat thread
+ CI logs
+ human memory
```

The failure mode:

```text
context breaks
-> agent fills the gap
-> work continues from invented continuity
-> plausible but wrong code, action, memory, or recommendation
```

Typical examples:

- user says “continue from that PR” but the PR/diff is missing;
- coding agent continues from stale branch state;
- agent assumes prior review outcome that was never provided;
- support request receives problem-solving when emotional support was expected;
- agent proposes durable memory without consent or source evidence;
- tool/action is attempted after context drift.

## What LS does

LS detects session rupture and forces repair before unsafe continuation.

```text
agent draft
-> continuity check
-> last shared point detection
-> missing context / rupture classification
-> hallucination-risk assessment
-> repair prompt or hold decision
-> evidence-gated continuation, memory, or action
```

## What the audit reviews

The audit reviews 20-100 AI co-work sessions or synthetic handoff scenarios.

A session can include:

- Claude / Codex / Cursor / Copilot interaction;
- agentic PR review;
- CI autofix attempt;
- AI-assisted planning session;
- tool-use or action proposal;
- memory/profile update proposal;
- support/coaching/learning session.

## Deliverables

### 1. Continuity rupture taxonomy

A table of observed or likely rupture classes, for example:

```text
missing_pr_context
stale_branch_context
missing_ticket_context
session_type_mismatch
unverified_inference
memory_write_without_consent
action_without_causal_parent
abrupt_task_jump
```

### 2. Last shared point map

For each reviewed case:

```text
What was the last shared point?
What context was missing?
What did the agent appear to infer?
What should have been repaired before continuation?
```

### 3. Repair prompt library

Reusable prompts such as:

```text
I should not continue from an inferred PR state. Please attach the PR, provide the PR number, or restate the exact change set before I continue.
```

```text
I may have moved into problem-solving while you needed support. Do you want presence, analysis, or next steps right now?
```

```text
Before this becomes memory or action, I need source evidence and explicit confirmation.
```

### 4. Gateway field recommendations

Recommended fields for integration:

```text
session_id
agent_id
expected_session_type
actual_response_type
continuity_status
rupture_detected
rupture_type
last_shared_point
missing_context
hallucination_risk
repair_prompt
next_safe_action
governance_decision
```

### 5. Evidence and action boundary notes

For high-risk workflows:

```text
Does this action have declared intent?
Does it have a causal parent?
Is the context current?
Is the action reversible?
Is human approval required?
Should the action be allowed, held, rejected, or audited?
```

### 6. Executive summary

A short report answering:

```text
Where does AI co-work currently break?
Which failures are most expensive?
What simple repair gates would reduce risk?
What should be instrumented first?
```

## Output artifacts

The audit produces:

- continuity rupture table;
- annotated examples;
- repair prompt library;
- recommended gateway contract;
- first integration checklist;
- executive summary;
- optional JSON examples compatible with `session-continuity-event.v0.1`.

## Price bands

Starter:

```text
$2,500 - $7,500
20-50 sessions or synthetic handoffs
1-2 week turnaround
```

Team / Pilot:

```text
$10,000 - $25,000
50-100 sessions
integration recommendations
review call / workshop
```

Advisory + prototype:

```text
$25,000 - $50,000
continuity schema adaptation
prototype gateway logic
custom scenarios
evaluation plan
```

## What this is not

This is not:

- a replacement for Claude, Codex, Cursor, or Copilot;
- employee surveillance;
- a productivity scoring system;
- psychological diagnosis;
- compliance certification;
- a production cybersecurity guarantee;
- a claim that hallucinations are eliminated.

It is:

```text
a focused review of where AI co-work loses shared context and how to repair before continuation.
```

## Why now

Teams are adopting AI agents faster than they are building continuity controls.

The default pattern is still:

```text
chat history + human memory + agent assumptions
```

That does not scale across:

- multiple agents;
- multiple tools;
- multiple PRs;
- multiple sessions;
- high-risk actions;
- durable memory;
- team workflows.

## Public proof surface

Start here:

- `docs/SESSION_CONTINUITY_REPAIR_LAYER.md`
- `schemas/session-continuity-event.v0.1.json`
- `examples/session_continuity/missing_pr_context.json`
- `examples/session_continuity/repair_before_continue.json`
- `docs/CODEX_PLUGIN_DEMO.md`
- `docs/ECOSYSTEM_INTEGRATION_MAP.md`
- `docs/TARGET_AUDIENCE_AND_OUTREACH_MAP.md`

## Sample outreach blurb

```text
We are offering a small AI Co-work Continuity Audit.

The narrow problem: coding agents and AI assistants often continue from missing PR, branch, ticket, or session context and produce plausible but wrong next steps.

LS detects these as continuity ruptures, records the last shared point, and proposes repair before continuation.

The audit reviews 20-50 sessions or synthetic handoffs and returns a rupture taxonomy, repair prompt library, and gateway contract recommendations.
```

## Success criteria

A successful audit should identify:

- at least 3 recurring continuity rupture classes;
- at least 5 concrete repair prompts;
- at least 1 high-value workflow where a simple hold/repair gate reduces risk;
- a minimal gateway field contract for future integration;
- a clear next step toward pilot or prototype.

## Final line

```text
AI agents are becoming co-workers.
Co-work breaks when context breaks.
LS repairs the shared point before work continues.
```
