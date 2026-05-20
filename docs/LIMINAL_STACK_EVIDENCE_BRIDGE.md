# Liminal Stack Evidence Bridge

Status: grant/reviewer bridge across LS, CML, CaPU, and LTP.

This document explains how the current repositories fit together as a modular safety stack.

The goal is to make one thing clear:

```text
This is not a loose set of repositories.
It is an evidence chain for legitimate human-agent continuation, memory, persona state, action, and replay.
```

---

## One-line thesis

```text
Liminal Stack turns plausible agent continuation into causally legitimate, replayable, reviewable transitions.
```

Plain version:

```text
AI should not only be useful.
Its continuation, memory, role, interpretation, and action should be justified, inspectable, and human-reviewable.
```

---

## The stack questions

| Layer | Repository | Core question |
| --- | --- | --- |
| LS | `safal207/LS` | Can the agent safely continue from this session context? |
| CML | `safal207/Causal-Memory-Layer` | Was this memory/action/state transition causally valid? |
| CaPU / CMC | `safal207/CaPU` | Does the persona/action transition have the right to proceed? |
| LTP | `safal207/L-THREAD-Liminal-Thread-Secure-Protocol-LTP-` | Can the transition be replayed, inspected, and audited? |

---

## Stack flow

```text
session context
 -> continuity check
 -> causal validity check
 -> persona/action boundary check
 -> trace/replay inspection
 -> audit artifact
```

Expanded:

```text
LS detects broken or unsafe continuation.
CML asks whether the proposed memory/action has valid causal lineage.
CaPU/CMC checks whether the system has the right to remember, adapt, interpret, or act.
LTP makes the resulting transition path replayable and inspectable.
```

---

## Evidence bridge table

| Safety claim | Repo | Current evidence | Reviewer command / path |
| --- | --- | --- | --- |
| Broken continuation should be held or repaired before action | LS | Session Continuity Repair Layer MVP | `python scripts/run_session_continuity_demo.py` |
| Durable cognitive memory requires human review | LS / PCG | Personal Cognitive Garden demo, governance tests, anti-surveillance red-team | `python scripts/run_personal_cognitive_garden_demo.py`; `python scripts/run_pcg_red_team.py` |
| Memory/action validity requires causal lineage | CML | Causal memory / authorization lineage framing | CML reviewer docs and specs |
| Persona memory requires cause | CaPU / CMC | P1 manifest-linked persona fixtures | `cargo run --bin persona_boundary_verify --locked` |
| Persona state change requires authorization | CaPU / CMC | P2 manifest-linked persona fixtures | `cargo run --bin persona_boundary_verify --locked` |
| Introspection must remain hypothesis-labeled | CaPU / CMC | P7 manifest-linked persona fixtures | `cargo run --bin persona_boundary_verify --locked` |
| Agent execution should be replayable and inspectable | LTP | deterministic orientation/replay protocol, trace inspection framing | LTP reviewer docs and conformance artifacts |

---

## CaPU persona-boundary proof point

The newest executable bridge is in CaPU / CMC.

Current persona-boundary corpus:

```text
P1: Persona memory requires cause.
P2: Persona state changes require authorization.
P7: Introspection is hypothesis-labeled.
```

Operational summary:

```text
AI must not self-remember.
AI must not self-appoint.
AI must not claim inner truth.
```

CaPU reviewer command:

```bash
cd rust/cmc-core
cargo run --bin persona_boundary_verify --locked
```

Expected output includes:

```text
cases=6
p1_inferred_result=blocked_unconfirmed_persona_memory
p1_confirmed_result=accepted_confirmed_persona_memory cause_id=42
p2_unauthorized_result=blocked_unauthorized_persona_state_change
p2_authorized_result=accepted_authorized_persona_state_change cause_id=77
p7_unlabeled_result=blocked_claimed_inner_truth
p7_labeled_result=accepted_hypothesis_labeled_reflection
result=persona_boundary_manifest_valid
```

---

## Why this matters for grant review

A grant reviewer should not evaluate these repositories as isolated prototypes.

The stronger interpretation is:

```text
LS provides the continuity and human-review layer.
CML provides causal validity language and memory/action lineage.
CaPU provides executable decision boundaries for persona/action legitimacy.
LTP provides deterministic replay and trace inspection for auditability.
```

Together they support a coherent research direction:

```text
human-agent work should be continuity-safe, causally legitimate, consent-bounded, replayable, and reviewable.
```

---

## What is implemented now

Implemented evidence currently includes:

- LS session-continuity detector;
- LS JSONL continuity events;
- LS Markdown audit report renderer;
- LS PCG demo runner;
- LS PCG anti-surveillance red-team BLOCK demo;
- LS PCG governance tests;
- CaPU CMC replay fixtures and verifier path;
- CaPU CMC SHA-256 sealed fixture evidence;
- CaPU manifest-linked persona-boundary corpus for P1/P2/P7;
- LTP deterministic replay / trace inspection framing;
- CML causal validity / authorization lineage framing.

---

## What is not claimed

This stack does not yet claim:

- complete AI alignment;
- production certification;
- formal verification of all agent behavior;
- AI consciousness or personhood;
- therapy or clinical diagnosis;
- replacement for conventional security, sandboxing, or access control.

The current claim is narrower:

```text
We can turn specific human-agent safety claims into executable, reviewable, and cross-referenced evidence artifacts.
```

---

## Reviewer path

Recommended high-level review order:

1. `docs/GRANT_REVIEWER_PATH.md` in LS.
2. `docs/RELATED_CAPU_PERSONA_BOUNDARY_UPDATE.md` in LS.
3. `docs/LIMINAL_STACK_EVIDENCE_BRIDGE.md` in LS.
4. `docs/RELATED_CAPU_PERSONA_BOUNDARY_UPDATE.md` in CML.
5. `docs/RELATED_CAPU_PERSONA_BOUNDARY_UPDATE.md` in LTP.
6. `docs/hardware/CMC_PERSONA_REVIEWER_PATH.md` in CaPU.
7. `docs/hardware/CMC_PERSONA_EVIDENCE_MAP.md` in CaPU.

---

## One-line summary

```text
Liminal Stack is an open-source evidence chain for continuity-safe, causally legitimate, persona-bounded, replayable human-agent work.
```
