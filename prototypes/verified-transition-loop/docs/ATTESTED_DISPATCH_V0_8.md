# VTL v0.8 — Attested Dispatch Authenticity

VTL v0.7 proves that a particular authorization/use-time grant was consumed by an exact dispatch and linked to an observed outcome. v0.8 adds a separate authenticity layer around that already-verified transcript.

```text
v0.7 transcript
  -> detached integrity verification
  -> canonical transcript digest
  -> Ed25519 attestation
  -> verifier-controlled trust root
  -> freshness / revocation / policy checks
```

The verifier returns three independent claims:

```text
integrity_valid
signature_valid
trusted_current_authority
```

`valid=true` requires all three, plus exact transcript-digest and attestation-id binding.

## Trust-root ownership

The trust root is a separate verifier input. The attested envelope may name a `trust_root_id`, but it cannot supply the public key that grants itself authority. The CLI therefore verifies a single envelope with two files:

```bash
vtl-attestation-verify envelope.json --trust-root trust-root.json --now-ms 1800000001000
```

The conformance fixture embeds a reference trust root only to make the profile deterministic and executable. Production runtimes must source trust roots from an independently controlled configuration/PKI/attestation system.

## Signed statement

The Ed25519 signature covers canonical JSON containing:

```text
attestation_id
profile_id
schema_version
transcript_digest
issuer_id
signer_key_id
trust_root_id
issued_at_ms
not_before_ms
not_after_ms
trust_policy_version
signature_algorithm
```

`attestation_id` is itself derived from the statement fields excluding the signature. The complete v0.7 transcript is bound through `transcript_digest`.

## Verification order

1. Validate envelope and external trust-root shape.
2. Run the complete v0.7 detached transcript verifier.
3. Recompute the exact transcript digest.
4. Recompute the attestation id.
5. Resolve signer identity only from the external trust root.
6. Check algorithm policy, issuer binding, key validity and revocation.
7. Verify the Ed25519 signature.
8. Check attestation freshness/validity interval.
9. Report integrity, signature, and current trust authority separately.

A valid signature never overrides an invalid v0.7 transcript.

## Executable negative profile

The v0.8 fixture covers:

```text
valid trusted attestation                   -> PASS
transcript tampered after signing            -> FAIL
self-consistent replacement transcript       -> FAIL
wrong signature                              -> FAIL
unknown signer                               -> FAIL
issuer mismatch                              -> FAIL
wrong trust root                             -> FAIL
expired attestation                          -> FAIL
not-yet-valid attestation                    -> FAIL
revoked signer                               -> FAIL
trust-policy version drift                   -> FAIL
algorithm substitution                       -> FAIL
wrong signer key material                    -> FAIL
valid signature over invalid v0.7 transcript -> FAIL
```

## Trust ceiling

The reference profile proves Ed25519 signature validity against a verifier-supplied static trust root. It does not provide production key issuance, KMS/HSM custody, certificate identity, transparency-log inclusion, online revocation distribution, or atomic trust-root rotation. Those are integration responsibilities and should remain independently auditable.
