# Related CaPU Persona-Boundary Evidence

Status: grant/reviewer cross-reference note.

This note records a related executable safety artifact in CaPU that strengthens the broader Liminal Stack grant narrative.

Repository:

```text
https://github.com/safal207/CaPU
```

---

## Why this matters for LS / PCG

LS / Personal Cognitive Garden asks:

```text
When should AI-generated insight become durable human-owned memory at all?
```

CaPU / CMC persona-boundary evidence adds a lower-level safety question:

```text
Does the AI persona have the right to remember, reinterpret, or change its role toward the human?
```

This complements LS because PCG is not only about useful memory. It is about authorized, human-owned, non-surveillance memory.

---

## Current CaPU persona-boundary proof points

CaPU now includes manifest-linked executable persona-boundary fixtures for:

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

---

## Evidence artifacts in CaPU

```text
rust/cmc-core/fixtures/persona/MANIFEST.tsv
rust/cmc-core/fixtures/persona/inferred_preference_rejected.jsonl
rust/cmc-core/fixtures/persona/confirmed_preference_accepted.jsonl
rust/cmc-core/fixtures/persona/unauthorized_persona_state_change_rejected.jsonl
rust/cmc-core/fixtures/persona/authorized_persona_state_change_accepted.jsonl
rust/cmc-core/fixtures/persona/unlabeled_introspection_rejected.jsonl
rust/cmc-core/fixtures/persona/hypothesis_labeled_introspection_accepted.jsonl
rust/cmc-core/src/bin/persona_boundary_verify.rs
```

Reviewer command in CaPU:

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

## Relationship to LS / PCG

| LS / PCG concern | CaPU persona-boundary complement |
| --- | --- |
| Consent before memory | P1: memory requires cause |
| Anti-surveillance boundary | P1/P7: no unauthorized memory or inner-truth claims |
| Human-owned cognitive graph | P1/P2: updates and persona state changes require authorization |
| Session interpretation | P7: introspection must remain hypothesis-labeled |
| Agent role in the session | P2: persona must not self-appoint into a new role |

---

## Grant framing

This strengthens the broader Liminal Stack grant case:

```text
LS makes session continuity and cognitive-memory governance visible.
CaPU makes persona memory, role adaptation, and introspective interpretation legitimacy executable.
```

Together:

```text
human-agent work should not only be useful; it should be causally legitimate, consent-bounded, and reviewable.
```

---

## Non-claims

This note does not claim that LS or CaPU provide complete AI alignment, therapy, production companion safety, AI consciousness, or personhood.

It records a narrow executable evidence bridge between LS/PCG and CaPU/CMC.

---

## One-line summary

```text
CaPU adds executable persona-boundary evidence showing that AI personas must not self-remember, self-appoint, or claim inner truth.
```
