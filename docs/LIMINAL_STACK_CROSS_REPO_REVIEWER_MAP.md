# Liminal Stack Cross-Repo Reviewer Map

Status: reviewer navigation map.

## Purpose

This document gives reviewers a compact path through the Liminal Stack ecosystem.

The goal is to answer one question quickly:

```text
How do the repositories fit together as one safety / oversight system?
```

Short answer:

```text
LS explains the human-centered thesis.
LTP preserves continuity and replay evidence.
CML validates why actions were allowed.
ProofPath / Compute Witness provides executable evidence paths.
CaPU and TTM DB extend the stack toward decision gating and immutable history.
```

---

## 3-minute reviewer path

### 1. Start with LS

Repository:

```text
https://github.com/safal207/LS
```

Role:

```text
Human-centered operating layer and reviewer hub.
```

Use LS to understand:

- the broad thesis;
- the Personal Cognitive Garden direction;
- the human-review boundary;
- the anti-surveillance constraint;
- how repeated AI work can compound into reviewed human-owned artifacts.

Reviewer question:

```text
What is the human-centered problem this stack is trying to solve?
```

---

### 2. Then inspect LTP

Repository:

```text
https://github.com/safal207/L-THREAD-Liminal-Thread-Secure-Protocol-LTP-
```

Role:

```text
Trace / replay / continuity layer.
```

Use LTP to understand:

- deterministic replay for agent traces;
- execution-path admissibility;
- drift detection;
- unsupported path rejection;
- audit-grade trace evidence.

Reviewer question:

```text
Did the agent remain inside a replayable, admissible, grounded thread?
```

Core phrase:

```text
LTP keeps the thread admissible.
```

Bridge doc:

```text
https://github.com/safal207/L-THREAD-Liminal-Thread-Secure-Protocol-LTP-/blob/main/docs/architecture/LTP-CML-Bridge.md
```

---

### 3. Then inspect CML

Repository:

```text
https://github.com/safal207/Causal-Memory-Layer
```

Role:

```text
Causal legitimacy / why-allowed layer.
```

Use CML to understand:

- causal permission lineage;
- parent-cause validation;
- data-scope legitimacy;
- responsibility preservation;
- actions that are functionally correct but causally invalid.

Reviewer question:

```text
Why was this action allowed?
```

Core phrase:

```text
CML keeps the action accountable.
```

Bridge doc:

```text
https://github.com/safal207/Causal-Memory-Layer/blob/main/docs/LTP_CML_BRIDGE.md
```

Positioning docs:

```text
https://github.com/safal207/Causal-Memory-Layer/blob/main/docs/CML_AI_ADOPTION_EQUILIBRIUM_LAYER.md
https://github.com/safal207/Causal-Memory-Layer/blob/main/docs/FINTECH_LIMIT_DEMO.md
```

---

### 4. Then inspect ProofPath / Compute Witness

Repository:

```text
https://github.com/safal207/ProofPath
```

Role:

```text
Executable evidence hub.
```

Use ProofPath to understand:

- how evidence paths are represented;
- how reviewer-facing proof artifacts can be organized;
- how the broader ecosystem can point toward executable or inspectable evidence.

Reviewer question:

```text
Where is the executable or inspectable evidence path?
```

Ecosystem graph:

```text
https://github.com/safal207/ProofPath/blob/main/docs/ECOSYSTEM_GRAPH.md
```

---

### 5. Then map CaPU and TTM DB

These are architecture-layer directions that make the stack more complete.

CaPU role:

```text
Decision gating and boundary enforcement.
```

TTM DB role:

```text
Append-only ground-truth history substrate.
```

Reviewer question:

```text
How does the stack move from evidence and validation toward enforceable decisions and immutable history?
```

---

## Layer map

```text
Human / Operator
   ↓
LS
human-centered review, consent, cognitive garden, anti-surveillance boundary
   ↓
LTP / L-THREAD
thread continuity, replay, admissibility, drift detection
   ↓
T-Trace
replayable event evidence
   ↓
CML
causal legitimacy, permission lineage, responsibility chain
   ↓
CaPU
decision gating and execution boundary
   ↓
TTM DB
append-only historical substrate
   ↓
ProofPath / Compute Witness
executable evidence and reviewer-facing proof paths
```

---

## Reviewer cheat sheet

| Repository | Layer | Primary question |
| --- | --- | --- |
| LS | Human-centered operating layer | What human problem and safety boundary does the stack serve? |
| LTP | Continuity / replay layer | Did the agent remain inside an admissible thread? |
| CML | Causal legitimacy layer | Why was the action allowed? |
| ProofPath | Evidence hub | Where is the inspectable proof path? |
| CaPU | Decision boundary | Should this transition proceed? |
| TTM DB | Historical substrate | What history must remain immutable? |

---

## Core cross-repo story

A reviewer can read the stack as one sequence:

```text
1. LS defines the human-centered boundary.
2. LTP preserves replayable continuity across agent work.
3. CML validates whether sensitive actions were causally legitimate.
4. CaPU can gate transitions using those signals.
5. TTM DB can preserve accepted history.
6. ProofPath can expose evidence paths for review.
```

The combined thesis:

```text
AI systems need more than outputs.
They need continuity, causality, consent, evidence, and reviewable history.
```

---

## Recommended reviewer order

For grant or external review:

```text
1. LS README
2. LS Grant Reviewer Packet
3. This cross-repo reviewer map
4. LTP README and demo
5. CML README and audit docs
6. ProofPath ecosystem graph
7. Relevant demos / fixtures / benchmark evidence
```

---

## Safe claim boundary

This map does not claim the stack is a complete production safety platform.

Safer claim:

```text
The Liminal Stack is an emerging open-source oversight substrate for continuity,
causal accountability, human review, and evidence preservation in AI-assisted work.
```

Avoid:

```text
solves alignment
solves compliance
proves safety
replaces auditors
```

Use:

```text
supports review
preserves evidence
checks continuity
validates causal legitimacy
reduces the evidence gap
```

---

## One-line summary

```text
LS is the human-centered hub; LTP keeps the thread admissible; CML keeps the action accountable; ProofPath exposes the evidence path.
```
