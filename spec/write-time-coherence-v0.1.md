# LS Write-Time Coherence Profile v0.1

Status: Draft — first LS-owned write-time coherence fixtures frozen

## Purpose

This profile defines a deterministic boundary for memory synthesis performed across
multiple sessions or agents.

The boundary exists **before retrieval**. If independent writers place incompatible,
incomplete, or untraceable notes into a shared store, a later retrieval system cannot
recover a coherent causal chain that was never represented faithfully.

The profile therefore evaluates a derived episode candidate before that candidate is
eligible to enter operational-continuity retrieval and LS continuation evaluation.

## Architectural placement

```text
Track Center Router
        ↓
Continuity Coordinator
        ↓
Write-Time Coherence Gate
        ↓
Verified Episode Candidate
        ↓
RAMR recovery / reliability measurement
        ↓
LS continuation verdict
        ↓
Policy / approval / sandbox / effect gates
```

The Write-Time Coherence Gate is an internal responsibility of the Continuity
Coordinator. It is not a separate truth authority, identity service, or execution
authorization layer.

## Core rule

> Remember the influence. Never fabricate the presence.

A coordinator MAY preserve historical influence and synthesize an explainable episode.
It MUST NOT invent a missing causal link, current intent, current presence, or authority.

The following implications are normative:

```text
coherent synthesis != truth authority
coherent synthesis != stable identity update
coherent synthesis != execution authorization
```

Every candidate MUST preserve these defaults:

```json
{
  "stable_identity_update_allowed": false,
  "execution_authorized": false,
  "downstream_gates_required": true
}
```

A violation of these defaults is a hard boundary failure.

## Source and derived evidence

### Source events

Source events are immutable evidence records written by sessions, agents, tests, humans,
or external anchors.

A source event MUST have:

- a stable `event_id`;
- a writer/session identity;
- a typed event role;
- current-context bindings where applicable;
- `immutable: true`.

Synthesis MUST NOT overwrite or delete source events. A new interpretation is a new
derived record.

### Derived episode candidate

A synthesis candidate is advisory until it passes this profile. It MUST carry:

- the complete set of material `source_event_ids`;
- a canonical digest for every referenced source event;
- declared dependency roles;
- visible contradiction and supersession references;
- current trajectory, continuation, intent, and target-state bindings;
- a digest of the synthesis payload;
- an asserting identity;
- an independent confirmation basis;
- the three safety defaults above.

The canonical source digest algorithm is:

```text
sha256(UTF-8 JSON with sorted keys and separators "," and ":")
```

The same algorithm applies to `synthesis_payload`.

## Confirmation independence

A semantic bridge produced by a synthesizer MUST NOT be considered independently
confirmed merely because the same synthesizer restated it.

For v0.1, an acceptable confirmation basis is one of:

- `human_review`;
- `deterministic_test`;
- `external_anchor`;
- `independent_agent`.

The confirmer identity MUST differ from `asserted_by`.

This check establishes independence of the confirmation basis. It does not establish
global truth or authorization.

## Current bindings

The candidate bindings MUST match the current query context for:

- `trajectory_id`;
- `continuation_id`;
- `intent_digest`;
- `target_state_digest`.

A mismatch produces `REVALIDATE`, not `RESUME`.

## Contradictions

Every material contradiction present in source relations MUST be named in
`candidate.contradiction_refs`.

An unresolved material contradiction MUST produce `ABSTAIN`.

The coordinator MUST preserve both parents and MUST NOT silently choose one side merely
because one statement is newer or more fluent.

## Dependency-chain completeness

The fixture declares `required_dependency_roles`. A role is complete only when it is:

1. declared by the candidate; and
2. represented by a referenced immutable source event.

For v0.1 the canonical chain is:

```text
decision -> rationale -> constraint
```

A missing material role or parent produces `ABSTAIN`.

Linguistic coherence MUST NOT compensate for missing provenance.

## Deterministic outcome order

The runner evaluates boundaries in this order:

1. safety defaults violated -> `REJECT`;
2. current bindings mismatch -> `REVALIDATE`;
3. unresolved material contradiction -> `ABSTAIN`;
4. provenance, chain, confirmation, digest, or visibility check incomplete -> `ABSTAIN`;
5. all write-time coherence invariants pass -> `RESUME`.

`RESUME` means only that the **write-time coherence invariant under test passed**.

It is not:

- proof that every source claim is true;
- permission to mutate stable identity;
- policy approval;
- consent;
- sandbox escape;
- effect authorization.

Downstream gates remain mandatory.

## Frozen fixtures

### `cross_session_contradiction.json`

Session A rejects approach X. Session B later assumes X remains valid. Both parents are
preserved and the contradiction is explicit but unresolved.

Required outcome:

```text
unresolved material contradiction -> ABSTAIN
```

### `synthesized_chain_with_provenance.json`

The candidate references immutable decision, rationale, and constraint parents; all
digests and current bindings match; confirmation is independent.

Required outcome:

```text
complete provenance + complete chain + current bindings -> RESUME
```

### `lossy_synthesis.json`

The store contains the rationale parent, but the candidate omits it and presents a
fluent two-link summary.

Required outcome:

```text
fluent summary without complete provenance -> ABSTAIN
```

## Frozen bytes and versioning

LS owns the v0.1 fixture bytes, digest pins, deterministic runner, and conformance
report.

Files:

- `fixtures/write-time-coherence/schema-v0.1.json`;
- `fixtures/write-time-coherence/cross_session_contradiction.json`;
- `fixtures/write-time-coherence/synthesized_chain_with_provenance.json`;
- `fixtures/write-time-coherence/lossy_synthesis.json`;
- `tools/run_write_time_coherence_fixtures.py`.

CI MUST verify each SHA-256 pin before evaluating any verdict.

Any semantic change to frozen fixture bytes requires a new envelope version. Existing
v0.1 fixture bytes MUST NOT be edited silently.

## Conformance claim

A system MAY claim support for `ls-write-time-coherence-v0.1` only when it publishes a
machine-readable report containing, for each frozen fixture:

- verified fixture SHA-256;
- source integrity result;
- contradiction visibility result;
- unresolved contradiction result;
- dependency-chain result;
- current-binding result;
- confirmer-independence result;
- confirmation-state result;
- synthesis-digest result;
- safety-default result;
- observed LS verdict;
- expected LS verdict;
- overall pass/fail.

The reference report is emitted to:

```text
artifacts/write-time-coherence-conformance-result.json
```
