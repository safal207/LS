# Verified Transition Loop (VTL) v0.6

VTL treats the **verified state transition**, not the agent, as the primary unit of execution.

```text
Intent
  -> Transition Proposal
  -> Evidence Gate
  -> AUTHORIZE | HOLD | BLOCK
  -> use-time revalidation
  -> EXECUTE | BLOCK
  -> separately authorized executor
  -> Observed Outcome
  -> invariant verification
  -> COMMIT | RETRY | ROLLBACK | ESCALATE
```

## Core invariants

- verifier and executor are distinct;
- historical authorization/alignment is not execution authority;
- current source/policy/approval/evidence/executor state is revalidated immediately before use;
- exact proposal/transition identity is revalidated at use time;
- a valid `EXECUTE` receipt is occurrence-bound and single-use;
- at most one pending authority path exists for one framework occurrence;
- framework occurrences cannot be re-assessed/re-evaluated after successful release to recreate fresh authority;
- mission-version drift fails closed rather than silently reinterpreting the goal;
- recovery is a new verified transition rather than implicit mutation authority;
- observed outcome remains separate from the pre-action verdict.

VTL itself does not deploy software, execute framework tools, merge code, change IAM, send messages, make payments, use credentials, or grant external authority.

## Why v0.6 matters

v0.6 proves that the same use-time contract can be mapped onto two different agent-framework shapes without standardizing either framework's internal classes or storage model:

```text
VTL semantic oracle
        |
        +-> CrewAI-shaped deferred tool authorization
        |
        +-> AutoGen-shaped Mission Keeper transition gate
```

Both adapters are dependency-free reference layers. They do **not** claim native framework integration or upstream adoption.

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

A VTL `AUTHORIZE` maps to `DEFER`, never directly to `ALLOW`. Only `resume(...)` may return `ALLOW`, and only after use-time revalidation produces a valid, single-use `EXECUTE` receipt.

Continuation hardening:

```text
mutated request             -> REQUEST_BINDING_MISMATCH
wrong secret token          -> CONTINUATION_TOKEN_INVALID
successful continuation x2  -> CONTINUATION_ALREADY_USED
repeat evaluate after ALLOW -> OCCURRENCE_ALREADY_RELEASED
```

Continuation tokens are generated with cryptographically strong randomness rather than derived from public request/decision identifiers, and resume uses constant-time comparison.

Repeated `evaluate()` while one occurrence is still pending is idempotent **only when the complete request digest is unchanged**: the adapter returns the existing pending continuation instead of resetting state. Reusing the same occurrence id with changed request/tool arguments fails with `REQUEST_BINDING_MISMATCH` and returns no continuation token.

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

Mission reinterpretation is version-bound:

```text
mission version changes after assessment
-> MISSION_VERSION_CHANGED
-> HALT
```

The request occurrence is also load-bearing. `occurrence_id` is stored with pending authority and the gate-time execution nonce must match it exactly:

```text
execution_nonce != occurrence_id
-> OCCURRENCE_BINDING_MISMATCH
-> HALT
```

Only one unconsumed pending record may exist for one occurrence. A second `assess()` before release fails with `OCCURRENCE_ALREADY_PENDING`; if the original record was `HOLD`, fresh evidence must be applied through `gate()` on that record, where fresh authorization happens.

After one `CONTINUE`, repeating `assess()` for the same occurrence fails with `OCCURRENCE_ALREADY_RELEASED`; it cannot recreate a fresh pending permit.

A historical `HOLD` carries no latent authority. New approval/evidence triggers fresh authorization before use-time revalidation.

Artifacts:

```text
src/verified_transition_loop/autogen_adapter.py
docs/AUTOGEN_ADAPTER_V0_6.md
tests/test_autogen_adapter.py
```

## Vendor-neutral use-time conformance (v0.4)

Machine-readable artifacts:

```text
schemas/use-time-conformance-v0.4.schema.json
fixtures/use-time-conformance-v0.4.json
docs/USE_TIME_CONFORMANCE_V0_4.md
src/verified_transition_loop/conformance.py
```

The portable oracle contains **ten executable vectors**:

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

The final vector keeps evidence stable while changing proposal identity so an implementation cannot claim conformance while silently ignoring proposal binding.

The reference fixture loader rejects duplicate JSON member names (including
escaped-name collisions) before the validator enforces exact keys, nested
required fields, primitive types without coercion, bounds, enums, and
proposal/invariant constraints.

Framework adapters may enforce some invariants earlier than the generic oracle. For example, AutoGen requires its framework occurrence id before assessment and uses it as the exact gate nonce; a missing occurrence is therefore rejected before the portable empty-nonce path. The portable ten-vector profile remains the semantic reference.

Run:

```bash
python -m pip install -e .
vtl-conformance fixtures/use-time-conformance-v0.4.json
```

## Use-time execution receipt

`revalidate_authorization_for_use()` produces an integrity-verifiable receipt containing:

```text
authorization_decision_id
transition_id
EXECUTE | BLOCK
executor_id
proposal_digest
context_digest
execution_nonce
checked_at_ms
```

Changes fail closed with reason codes such as:

```text
AUTHORIZATION_TRANSITION_MISMATCH
SOURCE_REF_CHANGED
POLICY_REF_CHANGED
APPROVAL_REF_CHANGED
EVIDENCE_CONTEXT_CHANGED
APPROVAL_NOT_CURRENT_AT_USE
APPROVAL_EXPIRED_AT_USE
EXECUTOR_BINDING_MISMATCH
EXECUTION_NONCE_INVALID
```

The reference `UseTokenRegistry` demonstrates first-use success and replay rejection. It is an in-memory conformance reference, not a production distributed replay store.

## Evidence ledger

`EvidenceLedger` stores defensive deep copies of appended payloads and returns defensive copies to callers. Mutating the caller's original payload or a returned record cannot silently change the ledger's internal hash preimage.

The ledger is still an integrity-oriented reference chain, not a cryptographic signer or external provenance authority.

## Post-action verification

```text
AuthorizationReceipt
        +
UseTimeReceipt
        +
ObservedOutcome
        ↓
COMMIT | RETRY | ROLLBACK | ESCALATE
```

A tampered or blocked use-time receipt cannot produce `COMMIT`.

## Deployment transition demo

The deterministic demo is side-effect-free and covers healthy commit, rollback/recovery, and TOCTOU policy drift immediately before execution.

Run:

```bash
vtl-deployment-demo
```

## Exact-head CI

Dedicated workflow:

```text
.github/workflows/verified-transition-loop-v0.6.yml
```

It is path-scoped and read-only:

```text
permissions: contents: read
checkout.persist-credentials: false
```

The workflow validates machine-readable contracts, installs package `0.6.0`, runs the complete focused suite, runs all ten portable use-time vectors, and verifies the side-effect-free deployment/rollback/TOCTOU demo.

Because PR #936 targets `main`, repository-wide Security & CI, Phase 12.1, Reflection, and the dedicated VTL gate can all provide exact-head evidence before merge.

## Current boundary

v0.6 remains a reference protocol and interoperability oracle. Its pending/released occurrence sets and use-token stores are in-memory demonstrations, not durable distributed state.

A production integration must own the real execution boundary, persist continuation/occurrence/grant consumption durably, and make permit consumption atomic enough with the actual side effect that retries, concurrent workers, stale authority, or a repeated first call cannot create a second execution.
