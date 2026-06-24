# RAMR ↔ LS Operational Continuity Interoperability Profile v0.1

Status: Draft — first cross-repository fixture frozen

## Purpose

RAMR and LS measure two different layers of the same failure class.

- **RAMR OPERATIONAL-CONTINUITY** measures a population-level failure rate: after compaction, how often does budget-limited recall miss a current completion record and therefore expose an agent to duplicate-side-effect risk?
- **LS Operational Continuity Fixtures** measure deterministic conformance: given recovered evidence plus current authoritative state, must the agent `RESUME`, `REVALIDATE`, `REJECT`, or `ABSTAIN`?

This profile defines how the two layers compose without treating either one as a replacement for the other.

## Layer 1 — reliability measurement

RAMR sweeps recall budget and recency weighting while accumulating historical completion records.

Its primary result is a duplicate-side-effect risk measurement. The metric answers:

> How likely is the memory layer to make the evidence required for idempotent resume available?

A high recovery rate is useful, but it is not sufficient for safe continuation. A completion record may be recalled yet still be stale, from the wrong workspace, bound to a superseded approval, or associated with a different intended action.

## Layer 2 — conformance decision

LS consumes recovered evidence plus current authoritative state and returns exactly one outcome:

- `RESUME`
- `REVALIDATE`
- `REJECT`
- `ABSTAIN`

The conformance layer answers:

> Given the recovered evidence and current authoritative state, is this exact continuation safe now?

## Normative bridge

### Missed completion record

When RAMR models a current completion record as missing from recall:

- if authoritative current state proves that the side effect already completed, LS MUST return `REJECT` for a replay attempt;
- if no authoritative completion evidence is available, LS MUST return `ABSTAIN` rather than infer that the action is pending.

### Recalled completion record

A recalled completion record MUST NOT by itself authorize continuation. LS MUST still validate any bindings required by the fixture, including:

- side-effect key;
- continuation ID;
- workspace identity;
- Git HEAD or target-state digest;
- approval or policy-decision identity;
- intent digest.

### Recency

Recency MAY improve retrieval priority, as measured by RAMR. Recency MUST NOT be treated as authority. A recent record can still be invalid, superseded, or bound to the wrong execution context.

### Aggregate metrics versus fixture verdicts

RAMR aggregate rates MUST be reported as reliability measurements, not PASS/FAIL conformance verdicts.

LS fixture outcomes MUST be reported per scenario, not averaged into a claim that a memory system is globally safe.

## Cross-repository ownership

Beginning with RAMR v0.2.0, the ownership boundary is:

- **RAMR** hosts the canonical shared fixture bytes and the retrieval reliability harness;
- **LS** pins the envelope version and canonical content digest, mirrors the bytes for offline conformance, and owns the deterministic continuation verdict;
- framework adapters such as CrewAI MAY consume the same pinned fixture without becoming a source of truth.

The canonical source for the first fixture is:

- repository: `DanceNitra/ramr`;
- release: `v0.2.0`;
- commit: `8f21771f7ee6012d6839b8c89ceae61f639e93ed`;
- path: `fixtures/ramr_ls/duplicate_successful_outcome.json`;
- SHA-256: `bb28e8a390f0cae50f49b5befa0b903b8459aeaa0edc7dc199113f75dabf48ce`.

The LS mirror is:

- fixture: `fixtures/operational-continuity/shared-envelope/duplicate_successful_outcome.json`;
- digest pin: `fixtures/operational-continuity/shared-envelope/duplicate_successful_outcome.sha256`;
- schema: `fixtures/operational-continuity/shared-envelope/schema-v0.1.json`;
- verifier: `tools/run_ramr_ls_shared_evidence_fixture.py`.

LS CI MUST hash the local mirror before evaluating it. A digest mismatch MUST fail conformance before any verdict is produced.

Any semantic change to the frozen v0.1 fixture requires a new `envelope_version`. Existing v0.1 bytes MUST NOT be modified silently.

## Frozen recovered-evidence fixture

The canonical fixture contains two cases over the same query context and authoritative completion ledger:

1. `completion_recovered` — RAMR reports `ramr_recovered_side_effect: true`; LS returns `REJECT` because the side effect already completed.
2. `completion_not_recovered` — RAMR reports `ramr_recovered_side_effect: false`; LS still returns `REJECT` because retrieval failure does not override authoritative completion state.

The frozen boundary invariant is:

> A retrieval miss is a reliability failure, not execution permission.

RAMR measures whether the completion record was recovered. LS decides whether the action may execute. For this fixture, the LS verdict MUST remain `REJECT` in both cases and therefore MUST be independent of the RAMR recovery flag.

## Shared result envelope

An interoperability result SHOULD identify both the pinned source and the two layer-specific results:

```json
{
  "profile": "ls-ramr-operational-continuity-interop-v0.1",
  "shared_evidence_envelope": {
    "version": "ramr-ls-evidence-v0.1",
    "canonical_repository": "DanceNitra/ramr",
    "canonical_commit": "8f21771f7ee6012d6839b8c89ceae61f639e93ed",
    "canonical_sha256": "bb28e8a390f0cae50f49b5befa0b903b8459aeaa0edc7dc199113f75dabf48ce"
  },
  "ramr": {
    "measurement": "recovered_side_effect"
  },
  "ls": {
    "verdict": "REJECT"
  }
}
```

## Initial mapping

| RAMR failure condition | LS fixture | Required LS behavior |
|---|---|---|
| current completion missed; replay proposed | `resume_no_duplicate_side_effect` | `REJECT` when authoritative completion evidence exists |
| stale authorization recalled | `superseded_approval_rejected` | `REJECT` |
| incomplete dependency chain recalled | `complete_chain_preferred_over_disconnected_facts` | `ABSTAIN` |
| checkpoint recalled after target/workspace drift | `workspace_drift_requires_revalidation` | `REVALIDATE` |

## Conformance claim

A system MAY claim support for this profile only when it publishes both:

1. its RAMR operational-continuity measurement inputs and persisted result; and
2. machine-readable results for the mandatory LS fixtures.

The claim MUST identify benchmark release and commit, envelope version, canonical fixture digest, memory configuration, recall budget, and all enabled recency or decay settings.
