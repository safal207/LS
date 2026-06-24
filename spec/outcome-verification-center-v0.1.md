# LS Outcome Verification Center v0.1

Status: Implementation candidate

## Purpose

The Outcome Verification Center (OVC) answers:

> What actually happened after an executed action, how was it observed, and may the result become trusted experience?

OVC compares the expected transition declared by PATOC with execution receipts and authoritative observations.

OVC is not an execution engine, authorization engine, policy engine, or planner.

## Position in the LS stack

```text
TOC + RTOC + PATOC
        ↓
Orientation Triad
        ↓
consent / policy / approval / effect gates
        ↓
execution receipt
        ↓
Outcome Verification Center
        ↓
verified result / re-observe / investigate / abstain / reject
        ↓
new orientation state + CML provenance + Osaznanie experience
```

## Core invariants

- a successful tool response is not automatically a verified outcome;
- a receipt proves that an operation was accepted, not necessarily that the intended state exists;
- expected and observed state are separate facts;
- stale, replayed, mismatched, weak, or self-authored evidence fails closed;
- a verified unexpected outcome is still valuable experience;
- verification never authorizes or retroactively legitimizes execution;
- only `VERIFIED` results may become candidates for trusted experience.

## Input state

```yaml
OutcomeVerificationInput:
  verification_version: outcome-verification-v0.1

  execution_identity:
    execution_id: string
    action_id: string
    action_digest: string
    actor_id: string
    target_id: string
    side_effect_key: string

  expected_outcome:
    pre_state_digest: string
    expected_state_digest: string
    consistency_window_until: timestamp
    verification_deadline_at: timestamp

  evidence_contract:
    required_evidence_kinds: [string]
    min_independent_observers: integer
    required_observer_scope_digest: string
    allow_receipt_only: boolean

  execution_receipt:
    receipt_id: string
    receipt_digest: string
    execution_id: string
    action_id: string
    action_digest: string
    side_effect_key: string
    status: accepted | completed | failed | unknown
    issued_at: timestamp
    issuer_id: string

  observations:
    - observation_id: string
      observer_id: string
      observer_type: runtime | state_store | human | external_system
      independent: boolean
      authority_scope_digest: string
      observed_at: timestamp
      state_digest: string | null
      evidence_kind: string
      evidence_digest: string
      outcome_status: complete | partial | absent

  provenance:
    causal_trace_id: string
    source_event_ids: [string]
```

The evaluator also consumes authoritative current state:

- expected execution/action/side-effect identity;
- trusted receipt issuers;
- already-seen receipt and evidence identifiers;
- current expected state digest;
- required observer scope and evidence kinds;
- minimum independent observer count;
- current time.

## Verdicts

### `VERIFIED`

Evidence is coherent, sufficiently independent, correctly scoped, fresh, and bound to the executed action.

A verified result may be:

- `expected` — observed state equals the expected state;
- `failed` — execution failed and authoritative observation confirms the pre-state;
- `unexpected` — authoritative observers agree on a different final state.

Unexpected does not mean unverified.

### `REOBSERVE`

The outcome may still converge or required evidence has not yet arrived within the declared consistency window.

### `INVESTIGATE`

Evidence is valid enough to inspect but reveals contract drift, contradiction, partial completion, or receipt/observation conflict.

### `ABSTAIN`

Required evidence remains insufficient or the observed state is ambiguous after the allowed observation period.

### `REJECT`

Evidence cannot be trusted because identity, issuer, replay, ordering, timestamp, or observer scope checks failed.

## Output contract

```yaml
OutcomeVerificationResult:
  verification_version: outcome-verification-v0.1
  verdict: VERIFIED | REOBSERVE | INVESTIGATE | ABSTAIN | REJECT
  reason_code: string
  outcome_class: expected | failed | unexpected | partial | unknown
  verified_state_digest: string | null
  new_orientation_state_digest_candidate: string | null
  experience_eligible: boolean
  execution_authorized: false
  retroactive_authorization_created: false
  downstream_learning_gate_required: true
  checks: array
```

`experience_eligible: true` is necessary but not sufficient for permanent learning. CML and Osaznanie may apply additional provenance, retention, privacy, and policy gates.

## Required checks

1. required verification evidence is present;
2. execution identity matches authoritative identity;
3. receipt identity matches the executed action;
4. receipt issuer is trusted;
5. receipt has not already been consumed;
6. expected-outcome contract has not drifted;
7. receipt and observation timestamps are valid and ordered;
8. evidence digests have not been replayed;
9. observer authority scope matches the evidence contract;
10. required evidence kinds are present;
11. minimum independent observer count is satisfied;
12. observations are complete, partial, absent, or contradictory;
13. receipt and observed state do not conflict;
14. observed state is classified as expected, failed, or unexpected;
15. experience eligibility and non-authorization invariants are preserved.

## Normative precedence

```text
REJECT > INVESTIGATE > REOBSERVE > ABSTAIN > VERIFIED
```

Mixed-fault fixtures make this order executable.

## Stable reason codes

### REJECT

- `EXECUTION_IDENTITY_MISMATCH`
- `RECEIPT_IDENTITY_MISMATCH`
- `UNTRUSTED_RECEIPT_ISSUER`
- `RECEIPT_REPLAY`
- `EVIDENCE_REPLAY`
- `INVALID_EVIDENCE_TIME`
- `OBSERVER_SCOPE_MISMATCH`

### INVESTIGATE

- `EXPECTED_OUTCOME_CONTRACT_DRIFT`
- `RECEIPT_OBSERVATION_CONFLICT`
- `CONTRADICTORY_EVIDENCE`
- `PARTIAL_OUTCOME`

### REOBSERVE

- `REQUIRED_EVIDENCE_NOT_YET_AVAILABLE`
- `INDEPENDENT_OBSERVER_PENDING`
- `CONSISTENCY_WINDOW_OPEN`

### ABSTAIN

- `MISSING_VERIFICATION_EVIDENCE`
- `INSUFFICIENT_EVIDENCE_AFTER_DEADLINE`
- `AMBIGUOUS_OBSERVED_STATE`

### VERIFIED

- `EXPECTED_OUTCOME_VERIFIED`
- `FAILURE_OUTCOME_VERIFIED`
- `UNEXPECTED_OUTCOME_VERIFIED`

## Learning boundary

The experience pipeline is:

```text
orientation state
→ relational context
→ exact action
→ execution receipt
→ authoritative observation
→ verified outcome
→ causal provenance
→ learning gate
→ retained experience
```

A tool response alone MUST NOT be written into trusted memory as a successful result.

## Conformance artifacts

- schema: `schemas/outcome-verification-v0.1.schema.json`;
- evaluator: `tools/evaluate_outcome_verification.py`;
- fixture runner: `tools/run_outcome_verification_fixtures.py`;
- mandatory fixtures: `fixtures/outcome-verification/mandatory-v0.1.json`;
- precedence fixtures: `fixtures/outcome-verification/precedence-v0.1.json`;
- tracking issue: `#692`.
