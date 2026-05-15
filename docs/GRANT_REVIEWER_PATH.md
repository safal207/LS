# LS Grant Reviewer Path

Start here if you are reviewing LS for grants, safety research, or open-source infrastructure relevance.

LS is a session-continuity and repair layer for AI co-work. It focuses on a specific failure mode:

```text
context breaks
-> agent continues anyway
-> hallucinated continuity becomes action, memory, or evaluation
```

The first LS runtime artifact detects that class of failure before continuation.

## One-line summary

```text
LS detects broken AI co-work continuity and turns it into repairable, auditable events.
```

## Core principle

```text
Continuity before continuation.
Evidence before action.
Consent before memory.
Repair before judgment.
```

## What is implemented now

LS currently includes a deterministic Session Continuity Repair Layer MVP:

```text
prompt + raw_output
-> continuity detector
-> ContinuityEvent
-> gateway output
-> JSONL events
-> Markdown audit report
```

Implemented components:

- Session Continuity Repair Layer documentation: `docs/SESSION_CONTINUITY_REPAIR_LAYER.md`
- Event schema: `schemas/session-continuity-event.v0.1.json`
- Deterministic detector: `ls/continuity/`
- Demo runner: `scripts/run_session_continuity_demo.py`
- Route gateway integration: `plugins/ls-personal-cognitive-garden/scripts/route_gateway.py`
- Audit report renderer: `scripts/render_continuity_audit_report.py`
- Ready-made audit report example: `examples/session_continuity/session_continuity_audit.md`
- AI Co-work Continuity Audit offer: `docs/offers/AI_COWORK_CONTINUITY_AUDIT.md`
- Outreach kit: `docs/outreach/AI_COWORK_CONTINUITY_OUTREACH_KIT.md`
- Ecosystem map: `docs/ECOSYSTEM_INTEGRATION_MAP.md`
- Grant narrative layer: `docs/GRANT_NARRATIVE_LAYER.md`

## Reviewer quickstart

Run the continuity demo:

```bash
python scripts/run_session_continuity_demo.py
```

Generate session-continuity events:

```bash
python scripts/run_session_continuity_demo.py \
  --write-jsonl data/session_continuity_events.jsonl
```

Render a Markdown audit report:

```bash
python scripts/render_continuity_audit_report.py \
  --input data/session_continuity_events.jsonl \
  --output reports/session_continuity_audit.md
```

Run the gateway continuity check without a remote server:

```bash
python plugins/ls-personal-cognitive-garden/scripts/route_gateway.py \
  --prompt "continue from that PR" \
  --raw-output "I will update the files now" \
  --continuity \
  --skip-remote-gateway
```

Expected result:

```text
Session continuity: ruptured
Rupture type: missing_pr_context
Decision: hold_until_context
```

## What the MVP detects

The deterministic v0.1 detector covers these failure classes:

| Failure class | Example | Decision |
|---|---|---|
| `missing_pr_context` | Agent continues from an unspecified PR/diff. | `hold_until_context` |
| `session_type_mismatch` | User needs support but agent jumps into solution mode. | `repair_before_continue` |
| `memory_write_without_consent` | Agent proposes durable memory without explicit review. | `human_review` |
| `action_without_causal_parent` | Agent proposes merge/deploy/delete/send without approval lineage. | `human_review` |
| `none` | Context appears sufficient. | `continue` |

## Why this matters

Many agentic failures are not just wrong answers. They are continuity failures:

```text
The agent acts as if it knows what conversation, artifact, authority, or emotional session it is continuing.
```

That can produce unsafe behavior:

- coding agents updating the wrong PR or file set;
- assistants acting from inferred context;
- memory systems writing durable state without consent;
- support agents responding with solutions when the actual session needs repair;
- high-risk tools being called without a grounded causal parent.

LS turns those failures into explicit events that can be held, repaired, reviewed, and reported.

## Related open-source safety stack

LS is the continuity and audit center. Related repositories provide complementary primitives.

```text
LS
├── SCRL: session continuity / repair
├── PCG: human-owned cognitive artifacts
├── CML: causal validity and authorization lineage
├── PythiaLabs: evidence/action gates before high-risk tools
└── LTP: deterministic replay and trace inspection
```

### Causal Memory Layer

Repository: https://github.com/safal207/Causal-Memory-Layer

CML checks whether a sensitive action was causally valid, permission-backed, and responsibility-preserving.

Relationship:

```text
LS asks: was the session continuous enough to continue?
CML asks: was the action causally valid once recorded?
```

### PythiaLabs

Repository: https://github.com/safal207/pythiaLabs

PythiaLabs provides deterministic evidence gates for high-risk agentic actions before tools are called.

Relationship:

```text
LS asks: should the agent continue from this context?
PythiaLabs asks: should the proposed action be allowed, blocked, or escalated?
```

### Liminal Thread Protocol

Repository: https://github.com/safal207/L-THREAD-Liminal-Thread-Secure-Protocol-LTP-

LTP provides deterministic replay and trace inspection for agent execution paths.

Relationship:

```text
LS emits continuity events.
LTP can replay and inspect the broader execution path that produced them.
```

## Stack flow

The broader research direction is:

```text
session rupture
-> continuity event
-> causal validity check
-> evidence/action gate
-> trace/replay inspection
-> audit artifact
```

This supports AI safety, governance, DevTools, and enterprise AI adoption work where the question is not only "did the agent answer?" but:

```text
Was it safe and justified for the agent to continue from this context?
```

## What is implemented vs roadmap

### Implemented in LS

- deterministic continuity detector;
- stable rupture classes;
- repair prompts;
- gateway integration;
- JSONL event emission;
- Markdown audit report renderer;
- paid audit offer and outreach kit.

### Roadmap

- richer schema validation and conformance fixtures;
- integration with broader trace/replay flows;
- dashboard views over continuity events;
- expanded rupture taxonomy;
- pilot data from real AI co-work sessions;
- deeper connection to CML, PythiaLabs, and LTP artifacts.

## Reviewer framing

A useful way to evaluate this repository:

```text
Does LS make hallucinated continuation visible before it becomes action, memory, or evaluation?
```

The current answer is intentionally narrow but executable:

```text
broken context in
-> deterministic rupture event out
-> repair/hold/human-review decision
-> audit report artifact
```

## Boundary claims

LS is not claiming to solve all AI safety problems.

It contributes one specific safety primitive:

```text
session-continuity validation before continuation, memory, or action.
```

The related repositories contribute complementary primitives:

- CML: causal validity;
- PythiaLabs: evidence/action gates;
- LTP: replay and trace inspection.

Together they form a coherent open-source path for deterministic oversight of human-agent work.
