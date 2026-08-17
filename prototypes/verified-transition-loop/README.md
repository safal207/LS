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
- current source/policy/approval/evidence/executor state is revalidated immediately before use;
- a valid `EXECUTE` receipt is occurrence-bound and single-use;
- the final runtime action envelope is frozen before dispatch;
- grant authority and grant consumption are different claims;
- sibling/equivalent-effect capability substitution fails closed;
- mission-version drift fails closed rather than silently reinterpreting the goal;
- recovery is a new verified transition rather than implicit mutation authority;
- observed outcome remains separate from the pre-action verdict and dispatch record.

VTL itself does not deploy software, execute framework tools, merge code, change IAM, send messages, make payments, use credentials, or grant external authority.

## What v0.7 adds

v0.6 established a portable use-time semantic oracle across two independent framework-shaped surfaces:

```text
VTL semantic oracle
        |
        +-> CrewAI-shaped deferred tool authorization
        |
        +-> AutoGen-shaped Mission Keeper transition gate
```

v0.7 extends that chain past authorization and asks a different question:

> Can a third party inspect a saved transcript and verify that the **exact use-time grant** was consumed by the **exact dispatch occurrence** and linked to the **exact observed outcome**?

The new proof chain is:

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

### Why `ActionGrantBinding` exists

The v0.6 use-time receipt binds proposal, evidence/policy context, executor, and execution nonce. Framework-specific final arguments still need an explicit frozen boundary before dispatch.

`ActionGrantBinding` commits to:

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

`ToolDispatchReceipt` must consume that same binding. A different `dispatched_action_id`, changed envelope, changed executor, changed occurrence, replayed grant, or changed outcome fails detached verification.

Full v0.7 contract and trust-boundary notes:

```text
docs/TOOL_DISPATCH_RECEIPT_V0_7.md
```

## Detached dispatch verification (v0.7)

Machine-readable artifacts:

```text
schemas/tool-dispatch-receipt-v0.7.schema.json
fixtures/tool-dispatch-receipt-v0.7.json
src/verified_transition_loop/dispatch_receipt.py
tests/test_dispatch_receipt.py
```

Run:

```bash
python -m pip install -e .
vtl-dispatch-verify fixtures/tool-dispatch-receipt-v0.7.json
```

Current deterministic vectors:

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

The same detached verifier is exercised against both CrewAI-shaped and AutoGen-shaped reference transcripts.

## Trust boundary: integrity != authenticity

v0.7 uses deterministic canonical JSON and SHA-256 IDs/digests to make transcript mutations and inconsistent bindings detectable.

This proves **internal transcript integrity/consistency**, not producer identity.

A producer that controls every input could create another self-consistent unsigned transcript and recompute the hashes. If hostile-producer provenance is in scope, a production system needs an external trust root such as a signature, transparency log, hardware-backed identity, or attestation over the canonical transcript/root digest.

Likewise, the reference replay set demonstrates the single-use rule but is not a distributed durable replay database. The embedding runtime must own durable permit consumption and the real dispatch seam.

## CrewAI-shaped adapter (v0.5)

```text
GuardrailRequest
-> VTL authorization
-> DEFER | DENY
-> continuation / external approval
-> fresh authorization when prior state was HOLD
-> use-time revalidation
-> ALLOW | DENY
```

A VTL `AUTHORIZE` maps to `DEFER`, never directly to `ALLOW`. Only `resume(...)` may release a tool, and only after fresh use-time revalidation.

Continuation safety includes:

```text
mutated request             -> REQUEST_BINDING_MISMATCH
wrong continuation token    -> CONTINUATION_TOKEN_INVALID
successful continuation x2  -> CONTINUATION_ALREADY_USED
```

The adapter reports `execution_binding = external` because it cannot claim atomicity with a real CrewAI tool side effect.

Artifacts:

```text
src/verified_transition_loop/crewai_adapter.py
docs/CREWAI_ADAPTER_V0_5.md
tests/test_crewai_adapter.py
```

## AutoGen-shaped Mission Keeper adapter (v0.6)

```text
MissionTransitionRequest
        ↓
MissionIntegrityRecord
        ↓
use-time revalidation
        ↓
CONTINUE | HALT | REQUIRE_REVIEW
```

`MissionIntegrityRecord.assessment = ALIGNED` is historical evidence only. It is not an execution permit. The adapter intentionally exposes no executor/repair/rewrite API.

Important boundaries:

```text
same verifier + executor
-> VERIFIER_EXECUTOR_NOT_SEPARATED

mission version changes after assessment
-> MISSION_VERSION_CHANGED
-> HALT
```

A historical `HOLD` carries no latent authority; new approval/evidence requires a fresh authorization.

Artifacts:

```text
src/verified_transition_loop/autogen_adapter.py
docs/AUTOGEN_ADAPTER_V0_6.md
tests/test_autogen_adapter.py
```

## Vendor-neutral use-time conformance (v0.4)

The portable use-time semantic oracle remains:

```text
schemas/use-time-conformance-v0.4.schema.json
fixtures/use-time-conformance-v0.4.json
docs/USE_TIME_CONFORMANCE_V0_4.md
src/verified_transition_loop/conformance.py
```

Reference vectors:

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
```

Cross-runtime mapping:

```text
stable context              -> EXECUTE / CrewAI ALLOW / AutoGen CONTINUE
source changed              -> BLOCK   / DENY         / HALT
policy changed              -> BLOCK   / DENY         / HALT
approval identity changed   -> BLOCK   / DENY         / HALT
evidence context changed    -> BLOCK   / DENY         / HALT
approval revoked            -> BLOCK   / DENY         / HALT
approval expired            -> BLOCK   / DENY         / HALT
executor substituted        -> BLOCK   / DENY         / HALT
execution nonce missing     -> BLOCK   / DENY         / HALT
```

Run:

```bash
vtl-conformance fixtures/use-time-conformance-v0.4.json
```

## Post-action and recovery verification

The existing outcome layer remains separate:

```text
AuthorizationReceipt
        +
UseTimeReceipt
        +
ObservedOutcome
        ↓
COMMIT | RETRY | ROLLBACK | ESCALATE
```

The deterministic deployment demo is side-effect-free and covers healthy commit, rollback/recovery, and TOCTOU policy drift before execution.

Run:

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

The workflow:

- validates the v0.4 and v0.7 machine-readable contracts;
- installs the isolated package;
- verifies package version `0.7.0`;
- runs the complete focused suite;
- runs all nine use-time vectors;
- runs all eleven detached dispatch vectors;
- verifies the side-effect-free deployment / rollback / TOCTOU demo.

## Development

```bash
python -m pip install -e '.[dev]'
pytest
```

## Current boundary

v0.7 is a reference protocol, simulation oracle, two framework-shaped compatibility adapters, and a detached dispatch-transcript verifier.

It has:

- no native CrewAI dependency;
- no native AutoGen dependency;
- no claim of framework adoption;
- no production deployment or tool-execution adapter;
- no GitHub write capability inside VTL;
- no cloud API or IAM capability;
- no credential or payment capability;
- no automatic merge path;
- no durable distributed use-token / continuation / grant-consumption registry;
- no cryptographic signer identity or provenance attestation for v0.7 transcripts.

A production integration must own the real execution boundary, persist continuation/consumption state durably, consume permits atomically enough to prevent duplicate effects, and add an external authenticity mechanism when producer identity is part of the threat model.
