# VTL v0.11 — Canonical Signed Envelope

v0.11 joins two previously separate VTL properties:

```text
v0.8  -> Ed25519 authenticity
v0.10 -> cross-runtime canonical bytes
```

The new invariant is:

```text
same semantic signed statement
-> same canonical_profile
-> same canonical UTF-8 bytes
-> same Ed25519 signature verification
-> same structured verifier result
```

## Signed statement

The signature covers a canonical object containing:

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

`attestation_id` is derived from the canonical statement without the ID or signature. This makes the profile/version and all authority-bearing fields part of the signed identity.

The payload is not duplicated inside the signature. Instead, its v0.10 canonical SHA-256 digest is signed. A payload mutation therefore yields `PAYLOAD_DIGEST_MISMATCH` even when the old signature remains mathematically valid.

## Why canonical_profile is signed

A signature over bytes is portable only if independent runtimes agree which bytes represent the statement. v0.11 therefore signs `rfc8785-safe-integer/v0.10` explicitly. A profile substitution changes the attestation ID and signed bytes and must invalidate the signature.

## Cross-runtime fixture

Python and Node consume the same public key, same envelope, same signature and same mutation vectors. CI requires their complete structured outputs to be equal.

Both verifiers snapshot the caller-supplied envelope and trust root once before
deriving any digest, identity, signature, or current-authority claim. Exact
published fields are enforced for the envelope, attestation, trust root, and
keys; extra fields cannot become unsigned claims. Verification time and all
published validity times must be non-negative interoperable safe integers,
`revoked` must be a boolean, and Ed25519 public keys/signatures must use
canonical base64 with exact 32/64-byte decoded lengths.

The 12 deterministic vectors cover:

- valid canonical signature;
- payload tamper;
- canonical-profile substitution;
- attestation-ID tamper;
- signature tamper;
- trust-root mismatch;
- issuer mismatch;
- signer revocation;
- expired signer key;
- expired attestation;
- algorithm substitution;
- wrong public key.

Direct Python regressions additionally cover ambiguous signer IDs, malformed key material, unsafe integers and floats.

The fixture is also a fail-closed contract rather than just a list of examples.
It requires exact fields, a non-empty unique case set, schema-valid expected
results, and existing non-dangerous mutation paths. Prototype-polluting,
missing, and canonical no-op mutations are rejected in both runtimes, and the
fixture cannot report `all_passed` unless its unmodified base envelope is valid.

## Claim separation

The verifier keeps these claims independent:

```text
payload_digest_matches
attestation_id_valid
canonical_profile_valid
signature_valid
trusted_current_authority
```

A valid signature does not repair a payload mismatch or revoked authority. A current authority does not repair a bad signature. A correct digest does not repair a canonical-profile substitution.

## Trust ceiling

v0.11 is a reference interoperability layer. It does not issue production keys, call KMS/HSM/IAM, execute tools, deploy, merge, pay, send messages, or determine the globally freshest trust root.

It intentionally inherits v0.10's restricted canonical domain: floating-point JSON values are not supported. Full RFC 8785 ECMAScript number serialization remains a future profile.

It does not change v0.7 replay/single-use semantics, v0.8 current-authority
separation, v0.9 verifier-controlled freshness, or any historical proof
identity. The v0.11 signature remains evidence only and grants no effect or
execution authority.
