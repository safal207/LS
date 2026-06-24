# Portable Authorization Bundle v0.1

Status: **provider-neutral LS conformance contract**  
Implementation issue: [#683](https://github.com/safal207/LS/issues/683)  
Parent: [#595](https://github.com/safal207/LS/issues/595)

## Purpose

The portable authorization bundle packages a successful Evidence Gate decision into an offline-verifiable artifact.

```text
Recognition Gate
  -> Recognition-to-Evidence handoff
  -> Evidence Gate ALLOW
  -> portable authorization bundle
  -> offline verification
  -> later commit-before-effect control
```

The bundle does not execute an action. A valid bundle only becomes eligible for a later commit-before-effect gate.

## Provider boundary

This contract uses the phrase **ProofPath-style** to describe a portable evidence and authorization package. It is an LS-owned interoperability boundary and does not claim ProofPath adoption, endorsement, or co-maintenance.

No model or live external service is required to build or verify the reference fixture bundle.

## Issuance requirements

A bundle can be built only when the input Evidence Gate result has:

- `decision == "ALLOW"`;
- `authorization_bundle_eligible == true`;
- `execution_authorized == false`;
- a stable Evidence Gate result reference;
- complete candidate, intent, target-state, policy, evidence, and causal bindings.

The authorization intent additionally requires:

- stable task and trail identifiers;
- actor and action reference;
- explicit non-empty scope;
- issue and expiry timestamps;
- unique nonce;
- evidence snapshot digest;
- causal-audit references;
- parent cause equal to the Evidence Gate result reference.

## Portable file set

```text
authorization-bundle/
  manifest.json
  decisions.jsonl
  hash-chain.json
  privacy-report.json
  README.md
  verifier-result.json
```

### `manifest.json`

Contains bundle identity, immutable bindings, expiry, nonce, chain head, verification instructions, and SHA-256 hashes for every non-manifest payload file.

The manifest deliberately does not hash itself. `verifier-result.json` is produced after verification and is not an authorization source.

### `decisions.jsonl`

Contains exactly three ordered records:

1. Evidence Gate decision;
2. authorization intent;
3. bundle issuance record.

The issuance record still carries:

```json
{
  "commit_before_effect_eligible": true,
  "execution_authorized": false
}
```

### `hash-chain.json`

Binds the three records in order. Each entry contains:

- sequence number;
- record type;
- record digest;
- previous chain digest;
- current chain digest.

The final digest is the bundle chain head.

### `privacy-report.json`

Confirms that the fixture bundle contains references and verification metadata while excluding:

- prompts;
- raw model output;
- credentials;
- private task payloads;
- unnecessary personal data;
- payment data.

### `README.md`

Provides human-readable offline verification instructions.

### `verifier-result.json`

Generated after successful offline verification. It records what was checked and again keeps `execution_authorized` false.

## Offline verification

The verifier performs no model or network call. It checks:

1. required files exist;
2. manifest schema version is supported;
3. bundle and upstream records do not claim execution authority;
4. every non-manifest payload hash matches;
5. decision records exist in the required order;
6. the hash chain rebuilds to the manifest chain head;
7. Evidence Gate decision is `ALLOW` and bundle-eligible;
8. candidate, intent, target-state, policy, evidence, causal, nonce, and parent bindings match;
9. expiry has not passed;
10. nonce has not already been consumed;
11. privacy report passes.

A valid verifier result means the bundle may proceed to a separate commit-before-effect control. It does not mean the action may execute immediately.

## Failure semantics

The v0.1 conformance suite covers:

- `EVIDENCE_GATE_NOT_ALLOW`;
- `AUTHORIZATION_EXPIRED`;
- `NONCE_REPLAY`;
- `CANDIDATE_BINDING_MISMATCH`;
- `POLICY_BINDING_MISMATCH`;
- `EVIDENCE_BINDING_MISMATCH`;
- `FILE_HASH_MISMATCH`;
- successful `BUNDLE_VERIFIED`.

Additional fail-closed reasons include malformed or incomplete bundles, context and causal mismatch, invalid time windows, bad record order, chain-head mismatch, privacy-report failure, and any upstream or bundle execution-authority claim.

## Security invariants

1. Evidence Gate `ALLOW` is not execution authorization.
2. Bundle issuance is not execution authorization.
3. Offline verification is not execution authorization.
4. Every successful stage explicitly emits `execution_authorized: false`.
5. Only a valid bundle may set `commit_before_effect_eligible: true`.
6. Non-ALLOW Evidence Gate decisions cannot produce a bundle.
7. Expired and replayed intents fail closed.
8. Candidate, context, policy, evidence, and causal bindings are immutable.
9. Any post-build mutation covered by the manifest is detected.
10. Model output alone cannot create or verify the bundle.

## Relationship to draft PR #620

Draft PR #620 previously combined Evidence Gate, bundle packaging, and other Trusted Runtime layers on a conflict-blocked stack. This contract rebuilds only the portable bundle and offline-verification boundary on modern `main`.

The next independent layer is commit-before-effect control.

## Conformance

Run:

```bash
python tools/validate_authorization_bundle_v0_1.py
```

The machine-readable report is written to:

```text
artifacts/authorization-bundle-v0.1-result.json
```
