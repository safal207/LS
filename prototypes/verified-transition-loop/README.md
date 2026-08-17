# Verified Transition Loop (VTL) v0.10

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
-> cross-language canonical bytes
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
-> canonical-byte interoperability
```

A valid higher-layer proof never repairs an invalid lower-layer proof.

## v0.4 — use-time authority

The portable use-time oracle enforces:

```text
AUTHORIZE != EXECUTE
```

Current proposal/source/policy/approval/evidence/executor state is revalidated at the point of use. The profile contains 10 executable vectors, including proposal/transition drift and single-use permit semantics.

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

The verifier performs schema/structure validation before digest comparisons, so a self-consistent malformed transcript cannot pass through matching missing values.

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

The 14-vector v0.9 profile additionally covers bad snapshot signatures, unknown bootstrap keys, root-payload tamper, expiry/not-yet-valid state, generation floors, root/policy mismatch, and algorithm substitution. Direct regressions cover ambiguous bootstrap key IDs, malformed/wrong-length bootstrap key material, invalid key validity intervals, future checkpoints, and incomplete checkpoint state.

A fresh valid snapshot still cannot rescue an invalid v0.8 attestation.

```text
schemas/trust-root-snapshot-v0.9.schema.json
fixtures/trust-root-snapshot-v0.9.json
docs/TRUST_ROOT_SNAPSHOT_V0_9.md
src/verified_transition_loop/trust_snapshot.py
```

## v0.10 — cross-language canonical proof

v0.10 closes the portability gap between semantic JSON and the exact bytes used for digests/signatures.

```text
same semantic VTL payload
-> Python canonicalizer
-> Node canonicalizer
-> exact UTF-8 bytes
-> SHA-256 digest
-> byte-for-byte / digest-for-digest parity
```

The explicit profile is:

```text
rfc8785-safe-integer/v0.10
```

It is a deliberately restricted RFC 8785/JCS-compatible domain:

```text
null | boolean | string | safe integer | array | object
```

Key properties:

- object names sort by UTF-16 code units;
- insignificant whitespace and alternate escape spelling disappear;
- Unicode scalar values are preserved without normalization;
- valid escaped surrogate pairs normalize to the same Unicode scalar value;
- lone surrogates fail closed;
- duplicate names, including escaped-equivalent names such as `a` and `\u0061`, fail closed;
- floats/exponent forms are outside this v0.10 profile;
- integers outside the interoperable IEEE-754 safe range fail closed;
- the conformance fixture itself is strict-parsed in both runtimes;
- Python-only values such as tuples are not accepted as JSON profile values.

The machine-readable proof contains **18 vectors**: 11 positive canonical-byte cases, 6 fail-closed parser/domain cases, and one semantic-mutation digest case. Python and Node independently compute the same base64-encoded UTF-8 bytes and SHA-256 digest and CI then compares their complete structured results.

```text
schemas/canonical-proof-v0.10.schema.json
fixtures/canonical-proof-v0.10.json
docs/CANONICAL_PROOF_V0_10.md
src/verified_transition_loop/canonical.py
reference/canonical-v0.10.mjs
```

v0.10 does not silently re-hash v0.7/v0.8/v0.9 historical proofs. Existing versions keep their published identity rules. Future proof versions can opt into the v0.10 canonicalization profile explicitly.

## Run the full portable stack

```bash
python -m pip install -e '.[dev]'
pytest
vtl-canonical-verify fixtures/canonical-proof-v0.10.json
node reference/canonical-v0.10.mjs fixtures/canonical-proof-v0.10.json
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

v0.10 proves cross-runtime canonical-byte agreement only for the declared safe-integer JSON subset. It does not claim full RFC 8785 floating-point coverage, Unicode normalization/confusable equivalence, a globally available source of latest trust-root generation, independent witness quorum, transparency-log inclusion, or hardware-backed checkpoint storage.

The central rule is now:

> **Historical authorization is not execution authority; integrity is not authenticity; a valid signature is not automatically current authority; a trusted root is not automatically the freshest root; and a digest is portable only when independent runtimes agree on the exact bytes being digested.**
