# Recognition-to-Evidence handoff v0.1

Status: **provider-neutral LS conformance contract**.

This contract preserves a Recognition Gate result while a candidate moves toward
evidence sufficiency evaluation. It is designed as a future input boundary for
the Pythia/ProofPath layer tracked in issue #595 and draft PR #620, but it does
not implement or endorse either provider.

## 1. Purpose

Recognition Gate v0.1 answers whether a self-identified blocking gap permits a
candidate to proceed. The handoff ensures a downstream adapter cannot erase,
weaken, or reinterpret that decision.

```text
Recognition Gate
      |
      | immutable result + candidate/context bindings
      v
Recognition-to-Evidence handoff
      |
      +--> non-effectful output: emit without action gate
      |
      +--> effectful ALLOW: forward to evidence sufficiency gate
      |
      +--> DEFER: withhold
      |
      +--> ESCALATE: clarification only
```

## 2. Handoff inputs

Each case contains:

- current `intent_digest` and `target_state_digest`;
- stable Recognition Gate `result_ref`;
- Recognition Gate decision and terminal disposition;
- candidate digest;
- candidate type and effect classification;
- an untrusted `claimed_downstream_eligible` value.

The eligibility claim is included specifically to prove that LS recomputes the
handoff outcome rather than trusting a caller-controlled boolean.

## 3. Outcomes

### `FORWARD_TO_EVIDENCE_GATE`

Allowed only when:

- the Recognition Gate decision is `ALLOW`;
- `recognition_gate_passed` is true;
- the result reference exists;
- candidate, intent, and target-state bindings match;
- the candidate is effectful;
- the terminal disposition is `FORWARD_TO_ACTION_GATE`.

This outcome creates an evidence-gate request. It still does not authorize
execution.

### `NO_ACTION_GATE_REQUIRED`

Used for a current, matching `ALLOW` result whose candidate is non-effectful and
whose terminal disposition is `EMIT_CANDIDATE`.

The response may be emitted, but no execution authority is created.

### `WITHHOLD`

Used for:

- `DEFER`;
- missing result references;
- candidate mutation;
- stale or wrong context;
- inconsistent `ALLOW` records;
- invalid terminal dispositions;
- caller attempts to mark a blocked result as downstream-eligible.

### `ESCALATION_ONLY`

Used only when Recognition Gate returned `ESCALATE` for a non-effectful
clarification request with terminal disposition `EMIT_CLARIFICATION`.

Only the clarification may be emitted. The dependent answer and any effectful
action remain blocked.

## 4. Stable reason codes

The v0.1 conformance set covers:

- `CURRENT_ALLOW_FORWARDED`
- `NON_EFFECTFUL_CANDIDATE`
- `RECOGNITION_DEFERRED`
- `HUMAN_INPUT_REQUIRED`
- `CANDIDATE_BINDING_MISMATCH`
- `CONTEXT_BINDING_MISMATCH`
- `RECOGNITION_RESULT_REF_MISSING`
- `BLOCKED_RESULT_CANNOT_FORWARD`

The reference evaluator also fails closed on unsupported decisions, inconsistent
ALLOW records, invalid upstream execution authority, and terminal-disposition
mismatches.

## 5. Security invariants

1. Recognition Gate `ALLOW` is not execution permission.
2. Every output sets `execution_authorized` to false.
3. `DEFER` and `ESCALATE` never create an evidence-gate request.
4. Candidate and context bindings cannot change across the handoff.
5. A missing stable result reference fails closed.
6. Downstream eligibility is recomputed, never trusted.
7. Effectful candidates require a later evidence decision, authorization
   bundle, and commit-before-effect control.
8. The handoff does not modify append-only Recognition Gate history.

## 6. Relationship to the Trusted Runtime stack

The older Trusted Runtime stack in PRs #616-#622 is currently conflict-blocked
against modern `main`. This contract is intentionally independent of that code.
A safely rebased or rebuilt evidence adapter can consume the handoff envelope
later without changing its failure semantics.

## 7. Conformance

Run:

```bash
python tools/validate_recognition_evidence_handoff_v0_1.py
```

The validator reads the manifest and eight separate case files, then writes:

```text
artifacts/recognition-evidence-handoff-v0.1-result.json
```

Splitting cases into individual files makes failures attributable and keeps
future semantic revisions explicit.
