# Verified Transition Loop (VTL) v0.9

VTL treats the **verified state transition**, not the agent, as the primary unit of execution and proof.

```text
Intent
-> Transition Proposal
-> AUTHORIZE | HOLD | BLOCK
-> fresh use-time revalidation
-> EXECUTE | BLOCK
-> ActionGrantBinding
-> external dispatch
-> ToolDispatchReceipt
-> Observed Outcome
-> detached integrity verification
-> AttestedDispatchEnvelope
-> detached signature + current-authority verification
-> signed TrustRootSnapshot
-> verifier-controlled freshness checkpoint
-> rollback / fork / continuity verification
```

## Proof layers stay separate

VTL deliberately does not collapse different claims into one boolean.

```text
use-time authority
-> dispatch consumption integrity
-> producer signature authenticity
-> current signer authority
-> trust-root snapshot authenticity
-> trust-root freshness / continuity
```

A valid higher-layer proof never repairs an invalid lower-layer proof.

## v0.4 — use-time authority

The portable use-time oracle enforces:

```text
AUTHORIZE != EXECUTE
```

Current proposal/source/policy/approval/evidence/executor state is revalidated
at the point of use. The profile contains 10 executable vectors, including
proposal/transition drift and single-use permit semantics. The fixture loader
rejects duplicate or escaped-collision JSON members, and approval expiry is
exclusive: equality with `approval_valid_until_ms` is already expired.

```text
schemas/use-time-conformance-v0.4.schema.json
fixtures/use-time-conformance-v0.4.json
docs/USE_TIME_CONFORMANCE_V0_4.md
```

## v0.5/v0.6 — framework-shaped compatibility

The same semantic contract is exercised through independent shapes:

```text
CrewAI-shaped DEFER -> continuation -> ALLOW | DENY
AutoGen-shaped MissionIntegrityRecord -> CONTINUE | HALT | REQUIRE_REVIEW
```

The adapters enforce request/occurrence binding, verifier/executor separation, fresh authorization after HOLD, replay prevention, mission-version binding, and no latent historical authority.

## v0.7 — grant consumption at dispatch

v0.7 proves that the exact use-time grant was consumed by the exact dispatch occurrence and linked to the exact observed outcome.

```text
AuthorizationReceipt
-> UseTimeReceipt(EXECUTE)
-> ActionGrantBinding
-> ToolDispatchReceipt
-> ObservedOutcome
-> detached verifier
```

The 11-vector dispatch profile covers wrong decision/use IDs, action-envelope drift, executor/occurrence substitution, context/policy mismatch, replay, sibling-capability substitution, cross-transition outcome binding, and outcome tamper.

The detached verifier performs schema/structure validation before digest comparisons so matching missing values cannot accidentally validate a malformed transcript.

The later dispatch receipt must consume the same binding. Envelope drift,
executor/occurrence substitution, replay, sibling capability substitution,
ambiguous JSON, missing authority bindings, verifier/executor collision, an
invalid execution nonce, or an expired approval fails detached verification.

Artifacts:

```text
schemas/tool-dispatch-receipt-v0.7.schema.json
fixtures/tool-dispatch-receipt-v0.7.json
docs/TOOL_DISPATCH_RECEIPT_V0_7.md
```

## v0.8 — attested producer authenticity

v0.8 wraps an already-verified v0.7 transcript in an Ed25519 attestation whose trust root is supplied by the **verifier**, not the transcript producer.

```text
canonical v0.7 transcript digest
-> attestation statement
-> signer key / issuer
-> external trust-root id + policy version
-> validity interval / revocation
-> Ed25519 signature
-> detached authenticity verification
```

It keeps these claims distinct:

```text
integrity_valid
signature_valid
trusted_current_authority
```

The reference v0.8 profile checks:

- exact transcript digest binding;
- deterministic attestation id;
- trusted signer lookup from external trust-root input;
- issuer/key identity binding;
- allowed signature algorithm;
- key and attestation validity intervals;
- signer revocation;
- trust-policy version binding;
- Ed25519 signature validity;
- v0.7 integrity as a prerequisite;
- strict JSON decoding and exact published envelope/trust-root fields;
- non-negative verification and validity times.

A self-consistent replacement transcript fails exact attested-digest binding; a valid signature over an invalid v0.7 transcript still fails; revoked or expired signer authority remains separate from mathematical signature validity. Ambiguous signer IDs and malformed trust-root key material fail closed.

The v0.8 authenticity profile contains 14 deterministic vectors.

```text
schemas/attested-dispatch-v0.8.schema.json
fixtures/attested-dispatch-v0.8.json
docs/ATTESTED_DISPATCH_V0_8.md
```

## v0.9 — rollback-resistant trust-root freshness

v0.9 closes the next gap:

```text
trusted root != fresh trusted root
```

A historically valid trust-root file may become stale after key revocation or policy replacement. v0.9 therefore authenticates the root itself and compares it with an independently retained verifier checkpoint.

```text
out-of-band bootstrap authority
-> signed TrustRootSnapshot generation N
-> verifier-controlled TrustCheckpoint
-> fresh v0.8 trust-root payload
-> v0.8 attested dispatch verification
```

The snapshot verifier exposes separate claims:

```text
snapshot_integrity_valid
bootstrap_signature_valid
bootstrap_authority_valid
freshness_valid
continuity_valid
```

The checkpoint can carry a generation floor plus an optional known generation/digest. With known state, the verifier rejects:

```text
older generation                    -> SNAPSHOT_ROLLBACK
same generation / different digest  -> SNAPSHOT_FORK_DETECTED
next generation / wrong predecessor -> PREVIOUS_SNAPSHOT_DIGEST_MISMATCH
skipped unseen generations           -> SNAPSHOT_CONTINUITY_GAP
```

The 14-vector v0.9 profile additionally covers bad snapshot signatures, unknown bootstrap keys, root-payload tamper, expiry/not-yet-valid state, generation floors, root/policy mismatch, and algorithm substitution. Direct regressions cover ambiguous bootstrap key IDs, malformed/wrong-length bootstrap key material, invalid key validity intervals, future checkpoints, and incomplete checkpoint state. Strict input regressions also reject duplicate or escaped-collision JSON member names, non-finite values, unpublished fields at every v0.9 authority boundary, negative epoch times, and invalid verifier time before cryptographic or continuity decisions.

A fresh valid snapshot still cannot rescue an invalid v0.8 attestation.

```text
schemas/trust-root-snapshot-v0.9.schema.json
fixtures/trust-root-snapshot-v0.9.json
docs/TRUST_ROOT_SNAPSHOT_V0_9.md
src/verified_transition_loop/trust_snapshot.py
```

## Run the full portable stack

```bash
python -m pip install -e '.[dev]'
pytest
vtl-conformance fixtures/use-time-conformance-v0.4.json
vtl-dispatch-verify fixtures/tool-dispatch-receipt-v0.7.json
vtl-attestation-verify fixtures/attested-dispatch-v0.8.json
vtl-trust-root-verify fixtures/trust-root-snapshot-v0.9.json
```

For a single v0.9 snapshot, both authority and freshness state are external verifier inputs:

```bash
vtl-trust-root-verify snapshot.json \
  --bootstrap-authority bootstrap-authority.json \
  --checkpoint checkpoint.json \
  --now-ms 1800000001000
```

## Safety and trust ceiling

VTL remains a reference verification protocol. It does not execute framework tools, deploy software, merge code, call cloud IAM/KMS/HSM, send messages, make payments, or grant production authority.

v0.9 protects against rollback and same-generation forks **relative to verifier-controlled bootstrap and checkpoint state**. It does not yet provide a globally available source of the latest generation, independent witness quorum, transparency-log inclusion, hardware-backed checkpoint storage, or cross-language canonical-byte standardization.

The central rule is now:

> **Historical authorization is not execution authority; integrity is not authenticity; a valid signature is not automatically current authority; and a trusted root is not automatically the freshest root the verifier may accept.**
