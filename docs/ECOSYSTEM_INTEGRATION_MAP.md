# Ecosystem Integration Map

## Purpose

This document turns the surrounding Liminal repositories into a coherent integration map for LS.

The goal is not to merge every repository into LS.

The goal is to clarify:

- which repository contributes which primitive;
- what LS should absorb now;
- what should stay separate;
- how the pieces form one reviewer-facing architecture.

## Core thesis

```text
Continuity before continuation.
Evidence before action.
Consent before memory.
Repair before judgment.
```

LS is the coordination point for a broader stack:

```text
human signal
-> intention clarification
-> semantic envelope
-> session continuity
-> repair
-> human-owned memory proposal
-> causal/evidence validation
-> replayable trace
-> append-only time/meaning record
-> quality evaluation
```

Short product line:

```text
Continuity infrastructure for human-agent work.
```

Research-facing line:

```text
LS is a local-first runtime for preserving meaning, continuity, consent, and evidence across human-agent sessions.
```

## Layer map

```text
DIF
-> raw signal to intention

LPI
-> semantic context, consent, trust, and session coherence

LRI
-> living identity governance and anti-profile-freezing

SCRL
-> session continuity repair layer

PCG
-> human-owned development graph

CML
-> causal validity and responsibility lineage

ProofPath / PythiaLabs
-> evidence gates before high-risk action

LTP
-> deterministic replay and trace inspection

TTM DB
-> append-only time and meaning substrate

LiminalQA
-> evaluation, quality decisions, and proof of effect
```

## Canonical stack

### 1. DIF — intention clarification

Repository:

- `safal207/DIF`

Role:

```text
raw signal -> context -> meaning hypothesis -> human correction -> confirmed intent
```

What LS should take:

- intention hypothesis loop;
- human correction before action;
- refusal to claim final access to human intent;
- support for messy inputs: text, voice, drawing, screenshot, emotion, file, dialogue.

What should stay separate:

- DIF as a standalone communication/funnel product;
- brand identity and market wedge.

Integration into LS:

```text
unclear user signal
-> DIF-style intent hypotheses
-> user confirms/corrects
-> LS session starts from confirmed intent
```

### 2. LPI — semantic presence and session envelope

Repository:

- `safal207/Liminal-Presence-Interface-LPI`

Role:

```text
message -> semantic envelope with intent, affect, consent, trust, memory, continuity
```

What LS should take:

- semantic context envelope;
- consent-carrying policy fields;
- session coherence / drift vocabulary;
- signed or trust-aware envelope direction;
- handshake concept for context-preserving communication.

What should stay separate:

- full SDK/package implementation unless LS needs it directly;
- protocol branding details.

Integration into LS:

```text
external agent message
-> LPI-style envelope
-> LS gateway reads intent / consent / coherence
-> session continuity check
```

### 3. LRI — living identity governance

Repository:

- `safal207/Living-Relational-Identity-LRI`

Role:

```text
protect living identity from freezing, silent substitution, optimization capture, and continuity loss
```

What LS should take:

- anti-profile-freezing invariant;
- revisability as a safety property;
- authorship boundary;
- memory consent boundary;
- identity drift warning;
- human authority to keep becoming.

What should stay separate:

- deeper identity protocol implementation;
- philosophical identity scope that is broader than LS runtime.

Integration into LS:

```text
agent proposes memory/profile/growth update
-> LRI-style boundary check
-> reject or hold identity-defining claims
-> PCG update remains human-reviewed
```

### 4. SCRL — Session Continuity Repair Layer

Repository:

- `safal207/LS`

Primary artifact:

- `docs/SESSION_CONTINUITY_REPAIR_LAYER.md`
- `schemas/session-continuity-event.v0.1.json`
- `examples/session_continuity/`

Role:

```text
broken continuity -> rupture event -> repair prompt -> safe continuation or hold
```

What LS should implement:

- `last_shared_point` detection;
- `rupture_type` classification;
- hallucination-risk classification;
- repair prompt generation;
- gateway mode mapping: `continue`, `validate_context`, `repair_before_continue`, `hold_until_context`, `human_review`.

Core invariant:

```text
A session may continue only when the system can identify the last shared orientation point or explicitly repair the missing context.
```

### 5. PCG — Personal Cognitive Garden

Repository:

- `safal207/LS`

Primary artifacts:

- `docs/LS_PERSONAL_COGNITIVE_GARDEN.md`
- `schemas/personal-cognitive-garden-update.v0.1.json`
- `examples/personal_cognitive_garden/`
- `plugins/ls-personal-cognitive-garden/`

Role:

```text
AI session -> development signal -> human-reviewed graph proposal -> accepted private growth state
```

What LS already has:

- session development classification;
- skill delta;
- evidence;
- governance;
- proposed/accepted update flow;
- Codex plugin path.

What to strengthen next:

```text
SCRL event
-> PCG proposal only if repair/continuity state is safe enough
```

### 6. CML — Causal Memory Layer

Repository:

- `safal207/Causal-Memory-Layer`

Role:

```text
functionally correct does not imply causally valid
```

What LS should take:

- causal parent concept;
- permission lineage;
- responsibility preservation;
- causal gap detection;
- audit validity for sensitive transitions.

Integration into LS:

```text
session/action/memory update
-> check causal parent
-> check whether authorization lineage exists
-> reject causally invalid continuation or write
```

### 7. ProofPath — verifiable intent for critical actions

Repository:

- `safal207/ProofPath`

Role:

```text
HTTPS proves the channel. ProofPath proves the action.
```

What LS should take:

- action-level intent;
- causal authorization;
- reversibility classification;
- human approval requirement for irreversible actions;
- hash-chained audit log direction.

Integration into LS:

```text
agent wants external action
-> SCRL checks continuity
-> CML checks causal validity
-> ProofPath-style gate checks intent/scope/reversibility/approval
-> action allowed / held / blocked
```

### 8. PythiaLabs — deterministic evidence gates

Repository:

- `safal207/pythiaLabs`

Role:

```text
evaluate high-risk AI-agent actions before tools are called
```

What LS should take:

- stable stop reasons;
- deterministic evidence gates;
- tamper-checkable evidence artifacts;
- decision-time context checks;
- evidence-before-action product framing.

Integration into LS:

```text
Evidence before action.
Continuity before continuation.
```

PythiaLabs should remain the stronger security / RegTech / action-gate project. LS should absorb the pattern, not blur the brand.

### 9. LTP — Liminal Thread Protocol

Repository:

- `safal207/L-THREAD-Liminal-Thread-Secure-Protocol-LTP-`

Role:

```text
trace -> deterministic replay -> admissible / drift / rejected
```

What LS should take:

- replayable trace thinking;
- two-phase inspection;
- unsupported-path rejection;
- admissibility decisions;
- anchor-backed context.

Integration into LS:

```text
SCRL continuity event
-> emitted as trace event
-> later replayed / inspected / rejected if unsupported
```

### 10. TTM DB — Traces of Time and Meaning

Repository:

- `safal207/ttm-db`

Role:

```text
append-only ground-truth trace substrate for transitions and meaning over time
```

What LS should take:

- `thread_id`;
- `transition_id`;
- append-only trace boundary;
- projection vs ground-truth separation;
- read-time verification envelope.

Integration into LS:

```text
session continuity events
+ PCG updates
+ action decisions
-> append-only transition records
-> derived reviewer views later
```

Key boundary:

```text
Trace is ground truth.
Projection is interpretation.
```

### 11. voice-to-evidence — messy human intake to audit artifact

Repository:

- `safal207/voice-to-evidence`

Role:

```text
voice / transcript -> structured evidence artifact -> human-reviewed snapshot
```

What LS should take:

- intake question protocol;
- transcript-to-structured-artifact flow;
- human reviewer validation;
- audit snapshot pattern.

Integration into LS:

```text
human says: “the agent lost the thread”
-> voice/transcript intake
-> continuity rupture draft
-> human review
-> SCRL event
```

### 12. LiminalQAengineer — evaluation and quality proof

Repository:

- `safal207/LiminalQAengineer`

Role:

```text
raw outcomes -> decision packet -> quality judgment
```

What LS should take:

- decision packet pattern;
- flake vs bug vs known issue thinking;
- root-cause evidence;
- counterfactual improvement estimate;
- evaluation harness style.

Integration into LS:

```text
without SCRL: agent continues from missing context and fails
with SCRL: agent repairs first and avoids wrong action
-> measure avoided failures
```

## What not to merge

```text
Do not merge all repositories into LS.
Do not rename everything into LS.
Do not blur PythiaLabs / ProofPath security framing with PCG.
Do not turn LRI into employee scoring.
Do not turn PCG into HR analytics.
Do not claim DIF gives final access to intent.
Do not claim SCRL eliminates hallucinations.
```

## Recommended integration order

### Phase 0 — Documentation alignment

```text
1. ECOSYSTEM_INTEGRATION_MAP.md
2. README link to the map
3. GRANT.md reference to the stack
```

### Phase 1 — Session continuity runtime MVP

```text
1. Add continuity fields to gateway output
2. Add simple heuristic continuity checker
3. Emit session-continuity-event artifacts
4. Show rupture/repair summary in Codex plugin output
```

### Phase 2 — Evidence and causal validation

```text
1. Map SCRL events to CML-style causal parent checks
2. Add PythiaLabs-style stop reasons
3. Add ProofPath-style action boundary for irreversible actions
4. Add LTP-style replay fixture
```

### Phase 3 — Human signal intake and identity governance

```text
1. Add DIF-style intent hypothesis when prompt is unclear
2. Add LPI-style semantic envelope fields
3. Add LRI-style identity and memory boundary checks
4. Add voice-to-evidence style intake for rupture reports
```

### Phase 4 — Evaluation and investor proof

```text
1. Create before/after scenarios
2. Measure avoided wrong continuation
3. Produce LiminalQA-style decision packets
4. Package as investor/grant demo
```

## Investor story

Problem:

```text
AI co-work is becoming multi-agent and multi-session.
People move between Claude, Codex, ChatGPT, IDEs, tickets, PRs, and voice notes.
The context breaks.
Agents and humans fill gaps with invented continuity.
This causes wrong actions, wasted time, unsafe automation, and broken trust.
```

Solution:

```text
LS preserves continuity, detects rupture, repairs shared orientation, and requires evidence before memory or action.
```

Proof surface:

```text
schema
examples
gateway
plugin
trace/replay direction
safety boundaries
grant-ready docs
```

Market wedge:

```text
Session continuity and repair for AI co-work.
```

Enterprise wedge:

```text
Stop agents from continuing from missing context.
```

AI safety wedge:

```text
Detect hallucinated continuation before it becomes action or memory.
```

## One-page architecture

```text
                   ┌──────────────────────────┐
                   │        Human signal       │
                   └─────────────┬────────────┘
                                 │
                                 ▼
                         DIF intent loop
                                 │
                                 ▼
                      LPI semantic envelope
                                 │
                                 ▼
                  LS gateway / session runtime
                                 │
             ┌───────────────────┼───────────────────┐
             ▼                   ▼                   ▼
          SCRL                PCG                 Action gate
   continuity repair   development proposal   ProofPath/Pythia
             │                   │                   │
             ▼                   ▼                   ▼
       TTM trace axis       LRI governance        CML validity
             │                   │                   │
             └───────────────────┼───────────────────┘
                                 ▼
                           LTP replay / audit
                                 │
                                 ▼
                         LiminalQA evaluation
```

## Final synthesis

The surrounding repositories are not random.

They form a meaning-preserving agent stack:

```text
DIF clarifies intention.
LPI carries semantic presence.
LRI protects living identity.
SCRL repairs broken continuity.
PCG grows human-owned skill capital.
CML checks causal validity.
ProofPath and PythiaLabs gate risky action.
LTP replays and inspects traces.
TTM DB preserves time and meaning.
LiminalQA measures decision quality.
```

Short version:

```text
LS is the runtime center.
The ecosystem supplies the primitives.
The product is continuity infrastructure for human-agent work.
```
