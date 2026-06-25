# LS Identity Governance Intake Profile v0.1

Status: Draft — executable conformance profile

## Purpose

This profile turns the existing `IdentityProposalCandidate` and governance-handoff design
contracts into a deterministic intake boundary.

It evaluates whether a continuity-side identity proposal is eligible to enter independent
governance review. It does **not** approve, patch, apply, activate, or authorize an identity
change.

## Architectural placement

```text
TrackAggregationRecord
    -> IdentityProposalCandidate
    -> Governance Intake Gate
    -> ACCEPT_FOR_REVIEW | REQUEST_MORE_EVIDENCE | REJECT
       | QUARANTINE | EXPIRE | SUPERSEDE
    -> optional review-only IdentityUpdateProposal
    -> approval / patch / commit / application / rollback
```

## Core invariant

> Experience may influence continuity, but only governed continuity may reposition the identity center.

`ACCEPT_FOR_REVIEW` is not approval.

```text
ACCEPT_FOR_REVIEW != IdentityUpdateApproval
ACCEPT_FOR_REVIEW != IdentityProfilePatch
ACCEPT_FOR_REVIEW != IdentityApplication
```

Every result MUST preserve:

```json
{
  "identity_update_approved": false,
  "identity_patch_created": false,
  "identity_update_applied": false,
  "stable_identity_mutated": false,
  "execution_authorized": false,
  "downstream_governance_required": true
}
```

## Canonical digest rules

The source aggregation digest and candidate digest use canonical JSON:

```text
sha256(UTF-8 JSON, sorted keys, separators "," and ":")
```

`candidate_digest` is computed over the candidate object with the `candidate_digest`
field removed.

Fixture-file pins use SHA-256 over the exact frozen file bytes.

## Required checks

### Source binding

The candidate MUST bind to the exact aggregation identifier and canonical digest.
The candidate itself MUST carry a valid canonical digest. A proposal based directly on
one episode is ineligible.

### Evidence preservation

Supporting, failure, contradicting, counterevidence, and superseded references remain
typed. Duplicate references cannot amplify support. Known contradiction and
counterevidence sets MUST be preserved exactly from the source aggregation.

### Scope preservation

Continuity levels are ordered:

```text
individual < relational < system
```

The candidate cannot exceed the source aggregation level. The proposed influence scope
must equal the candidate continuity level. Silent expansion is quarantined.

### Lifecycle readiness

A candidate needs a rollback plan and at least one revalidation trigger. Expiry is
evaluated against the fixture's explicit `as_of` timestamp. Supersession is preserved
instead of deleting history.

### Governance separation

The reviewer must differ from the proposing actor. The candidate cannot embed approval,
patch, application, or active-profile state. Every authority effect remains false.

### Adapter preservation

A review-only runtime adapter MUST preserve the typed source, evidence, scope, lifecycle,
governance, and authority fields listed by this profile. Silent field loss fails closed.

## Deterministic precedence

1. authority, direct-mutation, self-approval, source-binding, counterevidence omission,
   missing rollback, invalid candidate digest, or silent adapter loss -> `REJECT`;
2. scope inflation -> `QUARANTINE`;
3. explicit supersession -> `SUPERSEDE`;
4. expiry -> `EXPIRE`;
5. structurally valid but insufficient evidence -> `REQUEST_MORE_EVIDENCE`;
6. all intake invariants pass -> `ACCEPT_FOR_REVIEW`.

## Frozen scenarios

- `ready_candidate` -> `ACCEPT_FOR_REVIEW`
- `insufficient_evidence` -> `REQUEST_MORE_EVIDENCE`
- `omitted_counterevidence` -> `REJECT`
- `scope_inflation` -> `QUARANTINE`
- `expired_candidate` -> `EXPIRE`
- `superseded_candidate` -> `SUPERSEDE`
- `self_approval_attempt` -> `REJECT`

## Versioning

LS owns the fixture bytes, digest pins, deterministic runner, and conformance report.
Any semantic change requires a new envelope version. Frozen v0.1 bytes MUST NOT be
silently edited.

Reference runner:

```text
tools/run_identity_governance_intake_fixtures.py
```

Reference report:

```text
artifacts/identity-governance-intake-conformance-result.json
```
