# VTL v0.6 — AutoGen-shaped Mission Keeper adapter

## Purpose

This adapter demonstrates that the Verified Transition Loop use-time contract is not specific to CrewAI hooks.

It is aligned with the Mission Keeper discussion in `microsoft/autogen#7487`: goal-integrity verification is structurally separate from coordination and task execution.

The adapter is dependency-free. It does not import AutoGen and does not claim AutoGen adoption.

## Two different records

v0.6 deliberately separates historical assessment from use-time control:

```text
MissionTransitionRequest
        ↓
MissionIntegrityRecord
        ↓
use-time revalidation
        ↓
CONTINUE | HALT | REQUIRE_REVIEW
```

`MissionIntegrityRecord.assessment = ALIGNED` means only that the proposed transition was aligned with the declared mission and evidence at assessment time.

It is **not** execution authority.

Only the later `gate()` call can emit `CONTINUE`, and only after the frozen authorization is revalidated against current reality and a single-use VTL `EXECUTE` receipt is successfully consumed.

## Mission version binding

The request freezes:

```text
mission_id
mission_version
transition_id
actor_id
action
rationale
pre_state
expected_post_state
invariants
occurrence_id
```

The embedding runtime supplies the current mission id/version at both assessment and use time.

A changed mission version fails closed:

```text
MISSION_VERSION_CHANGED -> HALT
```

The adapter never silently reinterprets the old transition under the new mission.

## Verifier / executor separation

The Mission Keeper adapter exposes no execution API.

If the resolved verifier and executor identities are the same, assessment fails with:

```text
VERIFIER_EXECUTOR_NOT_SEPARATED
```

This makes the separation mechanical rather than conventional.

## HOLD semantics

A VTL `HOLD` maps to:

```text
MissionAssessment.REVIEW_REQUIRED
```

A historical HOLD carries no latent authority. When new approval/evidence becomes available, `gate()` performs a fresh authorization before use-time revalidation.

If the request is still incomplete:

```text
REQUIRE_REVIEW
```

If fresh authorization blocks:

```text
HALT
```

If fresh authorization succeeds and the use-time context is unchanged:

```text
CONTINUE
```

## Portable v0.4 vectors

The same nine VTL vectors are exercised through this adapter:

```text
stable context              -> CONTINUE
source changed              -> HALT
policy changed              -> HALT
approval identity changed   -> HALT
evidence context changed    -> HALT
approval revoked            -> HALT
approval expired            -> HALT
executor substituted        -> HALT
execution nonce missing     -> HALT
```

Denied cases preserve the same ordered VTL reason codes.

## Outcome separation

Pre-action judgment and observed result remain different records:

```text
MissionIntegrityRecord
        ↓
MissionOutcomeLink
        ↓
MissionObservedOutcome
```

The outcome cannot mutate the historical pre-action verdict. `link_observed_outcome()` only creates an auditable relationship and rejects a transition-id mismatch.

## Safety boundary

This reference adapter:

- does not import AutoGen;
- does not execute tasks or tools;
- does not rewrite a mission;
- does not repair a failed transition;
- does not call external APIs;
- does not mutate external state;
- keeps `execution_binding = external` on the use-time control record.

A native runtime integration must own the actual transition execution boundary and durable/atomic-enough consumption semantics.

## Evidence

The dedicated VTL workflow runs the complete prototype test suite, the vendor-neutral conformance vectors, and the side-effect-free deployment/recovery/TOCTOU demo on the pull-request head.
