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

## Mission and occurrence binding

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

`occurrence_id` is also load-bearing, not descriptive metadata. It is stored with the pending mission decision, and `gate()` requires the concrete use-time `execution_nonce` to reproduce that exact occurrence:

```text
execution_nonce != assessed occurrence_id
-> OCCURRENCE_BINDING_MISMATCH
-> HALT
```

After a successful `CONTINUE`, that occurrence is marked released for the lifetime of the reference adapter instance. Repeating `assess()` for the same occurrence cannot recreate unconsumed authority:

```text
OCCURRENCE_ALREADY_RELEASED
```

Repeated assessment before release does not overwrite the existing pending record.

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

If fresh authorization succeeds and the use-time context and occurrence are unchanged:

```text
CONTINUE
```

## Portable v0.4 oracle

The portable core profile contains ten executable vectors, including explicit proposal/transition drift.

This adapter maps the vectors that reach its use-time layer while enforcing two properties earlier in the framework-shaped boundary:

- proposal identity is already frozen by the complete request digest, so synthetic case-level proposal replacement is a core-oracle test rather than an adapter input;
- the framework occurrence id is the required execution nonce, so a missing occurrence is rejected at assessment with `OCCURRENCE_ID_MISSING` rather than being allowed to reach the generic empty-nonce path.

For applicable use-time drift cases, the mapping remains:

```text
stable context              -> CONTINUE
source changed              -> HALT
policy changed              -> HALT
approval identity changed   -> HALT
evidence context changed    -> HALT
approval revoked            -> HALT
approval expired            -> HALT
executor substituted        -> HALT
```

Denied cases preserve the ordered VTL reason codes produced by the portable revalidation layer.

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

## Reference-state boundary

The pending-decision map, released-occurrence set, and use-token registry are in-memory conformance mechanisms. They demonstrate the intended single-use and no-reset semantics but are not a durable distributed replay store.

A production runtime must persist occurrence/grant consumption durably and make release atomic enough with the actual transition execution to prevent duplicate side effects under retries or concurrency.

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
