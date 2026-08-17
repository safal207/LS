# Verified Transition Loop (VTL) v0.8

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
-> detached signature + trust-root verification
```

## The three claims are deliberately separate

v0.8 makes the trust model explicit:

```text
integrity_valid
signature_valid
trusted_current_authority
```

A transition is not accepted merely because one of those claims is true.

- A self-consistent transcript without a trusted signature proves integrity, not producer identity.
- A mathematically valid signature over an invalid v0.7 transcript does not repair the transcript.
- A valid historical signature from a revoked/expired/untrusted signer is not current authority.

## v0.4 — use-time authority

The portable use-time oracle enforces:

```text
AUTHORIZE != EXECUTE
```

Current proposal/source/policy/approval/evidence/executor state is revalidated at the point of use. The profile contains 10 executable vectors, including proposal/transition drift and single-use permit semantics.

Artifacts:

```text
schemas/use-time-conformance-v0.4.schema.json
fixtures/use-time-conformance-v0.4.json
docs/USE_TIME_CONFORMANCE_V0_4.md
```

## v0.5/v0.6 — framework-shaped compatibility

The same semantic contract is exercised through:

```text
CrewAI-shaped DEFER -> continuation -> ALLOW | DENY
AutoGen-shaped MissionIntegrityRecord -> CONTINUE | HALT | REQUIRE_REVIEW
```

The reference adapters enforce request/occurrence binding, verifier/executor separation, fresh authorization after HOLD, replay prevention, mission-version binding, and no latent historical authority.

## v0.7 — grant consumption at dispatch

v0.7 proves a different claim from authorization:

> Did the exact use-time grant get consumed by the exact dispatch occurrence and linked to the exact observed outcome?

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
-> validity interval
-> Ed25519 signature
-> detached authenticity verification
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
- v0.7 integrity as a prerequisite.

The 14-vector authenticity profile includes tamper, self-consistent replacement transcripts, wrong signature/key, unknown signer, issuer/root mismatch, expiry, not-yet-valid authority, revocation, trust-policy drift, algorithm substitution, and a valid signature over an invalid v0.7 transcript.

Artifacts:

```text
schemas/attested-dispatch-v0.8.schema.json
fixtures/attested-dispatch-v0.8.json
docs/ATTESTED_DISPATCH_V0_8.md
src/verified_transition_loop/attestation.py
```

Run all portable layers:

```bash
python -m pip install -e '.[dev]'
pytest
vtl-conformance fixtures/use-time-conformance-v0.4.json
vtl-dispatch-verify fixtures/tool-dispatch-receipt-v0.7.json
vtl-attestation-verify fixtures/attested-dispatch-v0.8.json
```

For a single signed envelope, the trust root is a separate verifier-controlled file:

```bash
vtl-attestation-verify envelope.json \
  --trust-root trust-root.json \
  --now-ms 1800000001000
```

## Safety and trust ceiling

VTL remains a reference verification protocol. It does not execute framework tools, deploy software, merge code, call cloud IAM/KMS, send messages, make payments, or grant production authority.

v0.8 uses real asymmetric Ed25519 verification, but its static reference trust-root model is not production PKI. Production integrations still need independently managed key issuance/custody, rotation, revocation distribution, certificate or workload identity, optional transparency evidence, and atomic coupling between grant consumption and the real side-effect seam.

The central rule remains:

> **Historical authorization is not execution authority; integrity is not authenticity; a signature is not current trust authority.**
