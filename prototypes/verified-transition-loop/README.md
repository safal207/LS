# Verified Transition Loop (VTL) v0.7

VTL treats the **verified state transition**, not the agent, as the primary unit of execution.

```text
Intent
  -> Transition Proposal
  -> Evidence Gate
  -> AUTHORIZE | HOLD | BLOCK
  -> use-time revalidation
  -> EXECUTE | BLOCK
  -> exact ActionGrantBinding
  -> external dispatch
  -> ToolDispatchReceipt
  -> Observed Outcome
  -> invariant verification
  -> COMMIT | RETRY | ROLLBACK | ESCALATE
```

## Core invariants

- verifier and executor are distinct;
- historical authorization/alignment is not execution authority;
- exact proposal, source, policy, approval, evidence, executor, and occurrence bindings are revalidated at use time;
- a valid `EXECUTE` receipt is single-use;
- repeating the first framework call after release cannot recreate fresh authority for the same occurrence;
- the final runtime action envelope is frozen before dispatch;
- grant authority and grant consumption are different claims;
- sibling/equivalent-effect capability substitution fails closed;
- mission-version drift fails closed rather than silently reinterpreting the goal;
- observed outcome remains separate from pre-action and dispatch records.

VTL itself does not deploy software, execute framework tools, merge code, change IAM, send messages, make payments, use credentials, or grant external authority.

## Hardened v0.6 base carried into v0.7

v0.7 is stacked on the reviewed v0.6 interoperability layer and now carries its independent-review hardening as merge ancestry.

### CrewAI-shaped continuation boundary

```text
GuardrailRequest
-> authorization
-> DEFER
-> secret continuation token
-> fresh use-time revalidation
-> ALLOW | DENY
```

The reference adapter now enforces:

```text
mutated request             -> REQUEST_BINDING_MISMATCH
wrong secret token          -> CONTINUATION_TOKEN_INVALID
continuation replay         -> CONTINUATION_ALREADY_USED
repeat evaluate after ALLOW -> OCCURRENCE_ALREADY_RELEASED
```

Continuation tokens are cryptographically random rather than derivable from public decision/request identifiers, and are checked with constant-time comparison. Repeated evaluation while an occurrence is still pending is idempotent and returns the existing continuation rather than resetting state.

### AutoGen-shaped Mission Keeper boundary

```text
MissionTransitionRequest
-> MissionIntegrityRecord
-> exact occurrence-bound gate
-> CONTINUE | HALT | REQUIRE_REVIEW
```

`occurrence_id` is stored with pending authority. The gate-time execution nonce must reproduce that occurrence exactly:

```text
execution_nonce != occurrence_id
-> OCCURRENCE_BINDING_MISMATCH
-> HALT
```

After `CONTINUE`, repeating assessment for the same occurrence fails with `OCCURRENCE_ALREADY_RELEASED`.

### Strict portable v0.4 oracle

The vendor-neutral profile now contains **10 executable vectors**:

```text
stable context              -> EXECUTE
source changed              -> BLOCK
policy changed              -> BLOCK
approval identity changed   -> BLOCK
evidence context changed    -> BLOCK
approval revoked            -> BLOCK
approval expired            -> BLOCK
executor substituted        -> BLOCK
execution nonce missing     -> BLOCK
proposal/transition changed -> BLOCK / AUTHORIZATION_TRANSITION_MISMATCH
```

The built-in fixture validator enforces the consumed JSON contract strictly: exact keys, nested required fields, primitive types without coercion, bounds/enums, and proposal/invariant constraints.

Framework adapters may reject some invalid states earlier than the generic core oracle. For example, AutoGen requires its framework occurrence at assessment and uses it as the exact use-time nonce; proposal mutation is also prevented by the bound request digest.

Artifacts:

```text
schemas/use-time-conformance-v0.4.schema.json
fixtures/use-time-conformance-v0.4.json
docs/USE_TIME_CONFORMANCE_V0_4.md
src/verified_transition_loop/conformance.py
```

## What v0.7 adds: detached grant-consumption proof

v0.7 extends verification beyond “authority was granted and still fresh” to:

> Can a third party inspect a saved transcript and verify that the **exact use-time grant** was consumed by the **exact dispatch occurrence** and linked to the **exact observed outcome**?

```text
AuthorizationReceipt
        ↓
UseTimeReceipt(EXECUTE)
        ↓
ActionGrantBinding
        ↓
ToolDispatchReceipt
        ↓
Observed Outcome
        ↓
detached verifier
```

### ActionGrantBinding

Immediately before external dispatch, the reference proof freezes:

```text
authorization_decision_id
use_id
transition_id
proposal_digest
action_id
action_envelope_digest
executor_id
execution_nonce
occurrence_id
context_digest
policy_ref
bound_at_ms
```

The later dispatch receipt must consume the same binding. Envelope drift, executor/occurrence substitution, replay, or sibling capability substitution fails detached verification.

### Detached dispatch conformance

Machine-readable artifacts:

```text
schemas/tool-dispatch-receipt-v0.7.schema.json
fixtures/tool-dispatch-receipt-v0.7.json
docs/TOOL_DISPATCH_RECEIPT_V0_7.md
src/verified_transition_loop/dispatch_receipt.py
tests/test_dispatch_receipt.py
```

The v0.7 fixture has **11 deterministic vectors**:

```text
exact authorized dispatch              -> PASS
wrong authorization decision           -> FAIL
wrong use_id                            -> FAIL
action envelope drift                  -> FAIL
executor substitution                  -> FAIL
occurrence / nonce substitution        -> FAIL
context / policy mismatch              -> FAIL
same grant consumed by second dispatch -> FAIL
sibling-capability substitution        -> FAIL
outcome bound to different transition  -> FAIL
tampered observed outcome              -> FAIL
```

The same detached verifier accepts both CrewAI-shaped and AutoGen-shaped reference transcripts when their bindings are exact.

Run:

```bash
vtl-conformance fixtures/use-time-conformance-v0.4.json
vtl-dispatch-verify fixtures/tool-dispatch-receipt-v0.7.json
```

## Evidence ledger hardening

The reference `EvidenceLedger` deep-copies appended payloads into internal state and returns defensive copies. Mutating the caller's original payload, the returned append result, or a `records` snapshot cannot silently alter the internal hash preimage.

This is still an integrity reference chain, not producer authentication.

## Trust ceiling: integrity != authenticity

v0.7 uses canonical JSON and deterministic SHA-256 bindings to detect internal transcript inconsistency, mutation, replay within the supplied replay context, and sibling-capability substitution.

Those hashes do **not** prove producer identity. A producer controlling every input could manufacture a new self-consistent unsigned transcript. A hostile-producer threat model therefore requires an external signature, attestation, transparency log, hardware-backed identity, or equivalent trust root over the canonical transcript/root digest.

Likewise, in-memory pending/released/use-token sets are conformance mechanisms, not a durable distributed transaction database. Production runtimes must own durable occurrence/grant consumption and make it atomic enough with real dispatch to prevent duplicate effects under retries or concurrency.

## Side-effect-free recovery demo

The deterministic demo still covers healthy commit, rollback/recovery, and TOCTOU policy drift immediately before execution without performing external side effects.

```bash
vtl-deployment-demo
```

## Exact-head CI

Dedicated workflow:

```text
.github/workflows/verified-transition-loop-v0.7.yml
```

It is path-scoped and read-only:

```text
permissions: contents: read
checkout.persist-credentials: false
```

The workflow validates v0.4 and v0.7 machine-readable contracts, verifies package `0.7.0`, runs the complete focused suite, all **10** portable use-time vectors, all **11** detached dispatch vectors, and the deployment/rollback/TOCTOU demo.

## Current boundary

v0.7 is a reference protocol, semantic/conformance oracle, two framework-shaped compatibility adapters, and a detached dispatch-transcript verifier.

It has no native CrewAI/AutoGen dependency, no framework-adoption claim, no production dispatch adapter, no cloud/IAM/credential/payment capability, no automatic merge authority, no durable distributed consumption registry, and no cryptographic producer-provenance signer.

A production integration must own the real execution boundary, durable replay/grant state, atomic-enough permit consumption, and an external authenticity mechanism when producer identity is part of the threat model.
