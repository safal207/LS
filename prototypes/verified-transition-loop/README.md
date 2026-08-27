# Verified Transition Loop (VTL) v0.11

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
-> cross-language canonical signed envelope
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
-> canonical-signature interoperability
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
- the fixture contract rejects missing/extra fields, empty vector groups,
  duplicate IDs, malformed expected encodings, and no-op mutation claims;
- Python-only values such as tuples are not accepted as JSON profile values.

The machine-readable proof contains **21 vectors**: 11 positive canonical-byte
cases, 9 fail-closed parser/domain cases, and one semantic-mutation digest
case. Python and Node independently compute the same base64-encoded UTF-8 bytes
and SHA-256 digest and CI then compares their complete structured results.

```text
schemas/canonical-proof-v0.10.schema.json
fixtures/canonical-proof-v0.10.json
docs/CANONICAL_PROOF_V0_10.md
src/verified_transition_loop/canonical.py
reference/canonical-v0.10.mjs
```

v0.10 does not silently re-hash v0.7/v0.8/v0.9 historical proofs. Existing versions keep their published identity rules. Future proof versions can opt into the v0.10 canonicalization profile explicitly.

## v0.11 — canonical signed envelope

v0.11 makes the canonicalization profile itself part of the Ed25519-signed identity.

```text
canonical payload
-> SHA-256 payload digest
-> versioned canonical signed statement
-> Ed25519 signature
-> Python verifier
-> Node verifier
-> identical structured result
```

The signed statement binds:

```text
attestation_id
profile_id
schema_version
canonical_profile
payload_digest
issuer_id
signer_key_id
trust_root_id
issued_at_ms
not_before_ms
not_after_ms
signature_algorithm
```

This produces an important separation:

```text
payload_digest_matches
attestation_id_valid
canonical_profile_valid
signature_valid
trusted_current_authority
```

A payload mutation can leave the old signature mathematically valid while the envelope fails `PAYLOAD_DIGEST_MISMATCH`. A canonical-profile substitution changes the signed bytes themselves and therefore invalidates both attestation identity and signature. Revocation/expiry can leave `signature_valid=true` while `trusted_current_authority=false`.

The shared v0.11 fixture contains **12 deterministic vectors** and uses exactly one public key, one signed byte sequence, and one Ed25519 signature in both runtimes. CI requires complete Python/Node result equality.

Both runtimes snapshot the caller inputs once, reject unpublished fields at the
envelope/attestation/trust-root/key boundaries, require non-negative safe epoch
times and boolean revocation state, and pin canonical base64 Ed25519 material to
32-byte public keys and 64-byte signatures. The fixture contract itself rejects
duplicate IDs, empty cases, unsafe/missing mutation paths, prototype-polluting
path segments, and canonical no-op mutations; an invalid base envelope cannot
produce `all_passed=true`.

```text
schemas/canonical-signed-envelope-v0.11.schema.json
fixtures/canonical-signed-envelope-v0.11.json
docs/CANONICAL_SIGNED_ENVELOPE_V0_11.md
src/verified_transition_loop/canonical_signed_envelope.py
reference/canonical-signed-envelope-v0.11.mjs
```

v0.11 is opt-in and does not change historical v0.8/v0.9 signature identities,
v0.7 replay/single-use behavior, verifier-controlled freshness, or the
no-external-effect boundary. The v0.11 workflow supersedes the v0.10 workflow
while retaining its 21-vector cross-runtime and malformed-fixture gates.

## Run the full portable stack

```bash
python -m pip install -e '.[dev]'
pytest
vtl-canonical-verify fixtures/canonical-proof-v0.10.json
node reference/canonical-v0.10.mjs fixtures/canonical-proof-v0.10.json
vtl-canonical-envelope-verify fixtures/canonical-signed-envelope-v0.11.json
node reference/canonical-signed-envelope-v0.11.mjs fixtures/canonical-signed-envelope-v0.11.json
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

v0.11 proves cross-runtime signature verification only for the declared v0.10 safe-integer canonical JSON subset and a verifier-supplied trust root. It does not claim full RFC 8785 floating-point coverage, Unicode normalization/confusable equivalence, a globally available source of latest trust-root generation, independent witness quorum, transparency-log inclusion, or hardware-backed checkpoint storage.

The central rule is now:

> **Historical authorization is not execution authority; integrity is not authenticity; a valid signature is not automatically current authority; a trusted root is not automatically the freshest root; a digest is portable only when runtimes agree on its exact bytes; and a signature is portable only when the canonicalization profile is itself bound into what was signed.**
