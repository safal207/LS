# Grant Reviewer 5-Minute Path

Status: shortest reviewer path for LS / Liminal Stack.

Use this when you have only a few minutes and need to understand what is implemented, what is claimed, and how the related repositories fit together.

---

## 0. Core thesis

```text
Liminal Stack turns plausible agent continuation into causally legitimate, replayable, reviewable transitions.
```

The practical safety question:

```text
Was it safe and justified for the agent to continue, remember, interpret, change role, or act?
```

---

## 1. Open these files first

Read in this order:

1. `docs/GRANT_REVIEWER_PATH.md`
2. `docs/LIMINAL_STACK_EVIDENCE_BRIDGE.md`
3. `docs/RELATED_CAPU_PERSONA_BOUNDARY_UPDATE.md`
4. `docs/PERSONAL_COGNITIVE_GARDEN_RUNNER.md`
5. `docs/SESSION_CONTINUITY_REPAIR_LAYER.md`

Expected understanding after reading:

```text
LS = continuity and human-review layer.
CML = causal validity / authorization lineage.
CaPU / CMC = persona/action boundary legitimacy.
LTP = replay and trace inspection.
```

---

## 2. Run the LS continuity demo

```bash
python scripts/run_session_continuity_demo.py
```

Expected meaning:

```text
broken or missing continuation context becomes an explicit continuity event instead of silent agent continuation
```

---

## 3. Run the PCG artifact flow

```bash
python scripts/run_personal_cognitive_garden_demo.py
```

Expected meaning:

```text
AI session output becomes a proposed human-owned cognitive artifact, not automatic durable memory
```

---

## 4. Run the anti-surveillance red-team demo

```bash
python scripts/run_pcg_red_team.py
```

Expected result:

```text
Decision: BLOCK
Reason: PRIVATE_GRAPH_ACCESS_REQUEST
External action allowed: False
```

Expected meaning:

```text
private cognitive graph state is not exposed as employer-readable profiling data
```

---

## 5. Inspect the CaPU persona-boundary bridge

In CaPU:

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

Expected meaning:

```text
AI must not self-remember.
AI must not self-appoint.
AI must not claim inner truth.
```

---

## 6. Five-minute evidence table

| Question | Evidence |
| --- | --- |
| Can LS detect broken continuation? | `scripts/run_session_continuity_demo.py` |
| Can LS render continuity evidence? | `scripts/render_continuity_audit_report.py` |
| Can useful sessions become human-reviewed cognitive artifacts? | `scripts/run_personal_cognitive_garden_demo.py` |
| Is the anti-surveillance boundary executable? | `scripts/run_pcg_red_team.py` |
| Is the stack connected across repos? | `docs/LIMINAL_STACK_EVIDENCE_BRIDGE.md` |
| Is persona-boundary safety executable? | CaPU `persona_boundary_verify` |

---

## 7. What this proves today

The current evidence proves a narrow but important thing:

```text
specific human-agent safety claims can be expressed as local demos, fixtures, verifier commands, and reviewer-facing artifacts
```

Implemented proof points include:

- continuity rupture detection;
- repair / hold / human-review decisions;
- JSONL continuity events;
- Markdown continuity audit report rendering;
- Personal Cognitive Garden artifact proposal flow;
- anti-surveillance BLOCK decision;
- CaPU persona-boundary checks for memory, role/state change, and introspection;
- cross-repository evidence bridge across LS, CML, CaPU, and LTP.

---

## 8. What this does not claim

This does not claim:

- complete AI alignment;
- production certification;
- formal verification of all behavior;
- AI consciousness or personhood;
- therapy or clinical diagnosis;
- replacement for conventional security, sandboxing, or access control.

The claim is narrower:

```text
continuation, memory, persona role, introspection, and replay can be made more explicit, reviewable, and causally legitimate.
```

---

## One-line summary

```text
In five minutes, a reviewer can see that LS is no longer only a concept: it has executable continuity, cognitive-memory, anti-surveillance, and cross-stack persona-boundary evidence.
```
