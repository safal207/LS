# Trusted Runtime CaPU execution control

Status: **reference implementation for issue #596**

This layer is the first point in the Trusted Runtime where an approved request
may become a side effect.

```text
verified ProofPath authorization bundle
-> Gate
-> Incubate
-> Commit
-> Execute
-> execution receipt and Cognitive Trail events
```

## Responsibility boundary

LS owns workflow continuity, task/trail identity, adapter sequencing, and the
final reusable artifact.

PythiaLabs decides whether evidence is sufficient.

ProofPath binds the accepted decision to scope, policy, evidence, expiry, and a
nonce.

CaPU owns execution ordering. Its central invariant is:

```text
no effect before durable commit
```

CaPU does not generate evidence and does not reinterpret an evidence decision.
It accepts a verified authorization bundle or fails closed.

## Canonical lifecycle

The implementation preserves the current CaPU vocabulary:

```text
RECEIVED
-> VALIDATING
-> HELD or ACCEPTED
-> COMMITTED
-> EXECUTED
```

Terminal pre-effect states are `REJECTED` and `EXPIRED`.

Canonical decision codes include:

- `PERMIT_OK`
- `REJECT_INVALID_CAUSE`
- `REJECT_POLICY`
- `DEFER_PENDING_CONTEXT`
- `TTL_EXPIRED`
- `ABORT_INTERNAL_ERROR`
- `COMMIT_EXECUTED`
- `COMMIT_NO_EFFECT`

The wire record uses the same frozen values as the CaPU repository rather than
introducing an LS-specific synonym set.

## Protected action

`ProtectedAction` carries:

- a stable action and idempotency identity;
- the requested effect reference;
- the required scope;
- a small serializable payload;
- request, maturity, and expiry timestamps;
- optional metadata.

The action digest and ProofPath authorization reference produce a deterministic
execution identity. Reusing that identity with different action bytes fails as
a state conflict.

## Durable journal

Two reference journals are provided:

- `InMemoryExecutionJournal` for deterministic unit tests;
- `JsonFileExecutionJournal` for local restart and crash fixtures.

`COMMITTED` is written to the journal before the executor is called. If the
journal write fails, `DurableCommitError` is raised and the effect executor is
never invoked.

## Harmless MVP effect

`ReviewResultFileExecutor` writes one review-result JSON file. The file is
created with exclusive-create semantics and includes the action digest.

The executor is inspectable and idempotent:

- an existing matching file is returned as the prior effect;
- a conflicting file is rejected;
- retrying an already executed record does not write a second file.

Payments, deployments, merges, destructive calls, and production credentials
remain out of scope.

## Recovery boundaries

The fixtures cover two interruptions.

### After commit, before effect

The journal contains `COMMITTED` and no effect exists. A new controller reads
the record and executes exactly one effect.

### After effect, before execution receipt

The journal still contains `COMMITTED`, but the idempotent executor can inspect
the existing effect. Recovery records `EXECUTED` without invoking the effect a
second time.

This makes the harmless file effect deterministically recoverable.

## Cognitive Trail and reusable artifact

Every CaPU transition is exported with:

- state;
- namespaced CaPU event type such as `gate.hold`, `commit.ok`, or `execute.ok`;
- canonical decision code;
- effect-attempt flag;
- stable execution-record reference.

Pre-effect transitions use the existing generic trail event type while the two
critical boundaries use:

- `EXECUTION_COMMITTED`
- `EXECUTION_COMPLETED`

The transitions remain ordered through explicit parent-event links. The final
record can also be attached to `ReusableArtifact.execution_ref`.

## Feature flag

`CaPUExecutionAdapter` is disabled by default and requires an injected
controller. Enabling the adapter is an explicit host decision.

## Production boundary

The reference runtime proves local commit-before-effect ordering and
idempotent recovery for an inspectable file effect. A production multi-process
or distributed deployment additionally needs:

- a transactional durable journal;
- a transactional or compare-and-set nonce store;
- an idempotency-capable tool/API boundary;
- ownership leases or fencing tokens for concurrent workers;
- a policy for effects that cannot be inspected after a timeout.

The implementation does not claim universal exactly-once semantics for an
arbitrary external API. It provides the contracts and deterministic local
reference behavior required to build that stronger boundary honestly.

## Validation

```bash
python -m pip install jsonschema pytest
PYTHONPATH=.:python:python/modules \
  python -m pytest python/tests/test_trusted_runtime_c*.py
```
