# ToolDispatchReceipt v0.7

## Purpose

VTL v0.7 separates three claims that must not be collapsed into one:

```text
AuthorizationReceipt
    proves: a verifier granted authority for a transition

UseTimeReceipt(EXECUTE)
    proves: that authority was still valid at the point of intended use

ToolDispatchReceipt
    proves: one exact dispatch occurrence claims consumption of that exact use-time grant
```

The new detached verifier is designed so a saved transcript can be checked without importing CrewAI, AutoGen, or the producer process that originally emitted the records.

## Why ActionGrantBinding is required

A use-time permit in v0.6 binds the proposal, executor, policy/evidence context, and execution nonce. It does not by itself freeze a framework-specific action envelope containing the final tool/action arguments.

v0.7 therefore inserts an integrity-verifiable `ActionGrantBinding` immediately after successful use-time revalidation and before dispatch:

```text
UseTimeReceipt(EXECUTE)
        ↓
ActionGrantBinding
  - action_id
  - action_envelope_digest
  - occurrence_id
  - executor_id
  - execution_nonce
  - context_digest
  - policy_ref
        ↓
ToolDispatchReceipt
```

This makes envelope drift and sibling-capability substitution observable to a detached verifier.

## Portable transcript

A v0.7 transcript contains these sections:

```text
proposal
authorization
use_time
action_envelope
grant_binding
dispatch_receipt
observed_outcome
```

`action_envelope` is runtime-shaped data. The verifier does not standardize CrewAI or AutoGen internals; it only requires a deterministic canonical representation whose digest and `action_id` are frozen by the grant binding.

## Core verification invariants

The detached verifier checks:

1. authorization and use-time receipts are internally integrity-valid;
2. authorization verdict is `AUTHORIZE` and use-time verdict is `EXECUTE`;
3. transition/proposal identities agree across every record;
4. the use-time receipt points to the exact authorization decision;
5. the grant binding points to the exact authorization + use receipt;
6. executor, policy, context, execution nonce, and occurrence identity remain unchanged;
7. the frozen action envelope reproduces the same digest and `action_id`;
8. the dispatched action id equals the authorized action id;
9. a seen `use_id` cannot prove a second dispatch;
10. observed outcome ref/digest matches the separately stored outcome;
11. temporal ordering is monotonic: use check -> grant binding -> dispatch -> observation.

## Conformance vectors

The static fixture currently exercises 11 deterministic cases:

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

Run the detached fixture:

```bash
vtl-dispatch-verify fixtures/tool-dispatch-receipt-v0.7.json
```

A valid transcript can also be passed directly to the same CLI. Exit status is non-zero when verification fails.

The CLI rejects ambiguous JSON member names, escaped-name collisions, and
non-finite constants before schema or binding evaluation. Detached verification
also rechecks the inherited authority boundary: verifier/executor separation,
non-empty source/policy/approval bindings, exclusive approval expiry, and a
non-empty whitespace-free execution nonce.

## Cross-runtime proof

The same verifier accepts independently constructed reference transcripts from both existing adapter shapes:

```text
CrewAI-shaped GuardrailRequest / deferred tool release
AutoGen-shaped MissionTransitionRequest / Mission Keeper release
```

The runtime-specific request remains inside `action_envelope.payload`; the portable verifier reasons about the frozen digest and shared VTL bindings rather than importing framework classes.

This is a compatibility proof, not a claim that CrewAI or AutoGen has adopted VTL.

## Trust boundary: integrity is not authenticity

v0.7 receipt IDs and digests are deterministic SHA-256 integrity bindings. They let an independent reader detect mutation, inconsistent bindings, replay within the supplied replay context, sibling-capability substitution, and outcome tampering.

They do **not** by themselves prove who produced the transcript.

A malicious producer that controls every input could manufacture a new self-consistent transcript and recompute all unsigned hashes. Therefore:

```text
detached hash verification
    proves internal transcript consistency / integrity

cryptographic signature or external attestation
    would be required to prove producer identity / provenance
```

A production deployment whose threat model includes a hostile or compromised producer should bind the canonical transcript (or its root digest) to an independently trusted signer, hardware-backed identity, transparency log, Sigstore-style attestation, or equivalent trust root.

That provenance layer is intentionally outside the v0.7 semantic oracle.

## Replay boundary

`seen_use_ids` demonstrates the normative single-use rule, but it is not a production distributed replay database. A real runtime must persist grant consumption durably and make dispatch plus permit consumption atomic enough that concurrent or retried requests cannot create a second side effect.

## Execution boundary

VTL v0.7 records and verifies dispatch evidence; it still does not own the actual dispatch seam.

The reference implementation:

- does not execute a CrewAI or AutoGen tool;
- does not call cloud APIs;
- does not deploy software;
- does not use credentials;
- does not merge code;
- does not claim transactionality with an external runtime.

The embedding runtime remains responsible for performing the side effect and for emitting truthful dispatch/outcome evidence. The detached verifier then checks whether those records are structurally and semantically consistent with the prior grant.

## Machine-readable artifacts

```text
schemas/tool-dispatch-receipt-v0.7.schema.json
fixtures/tool-dispatch-receipt-v0.7.json
src/verified_transition_loop/dispatch_receipt.py
tests/test_dispatch_receipt.py
```
