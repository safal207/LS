# LS Evidence Gate v0.1

Status: **provider-neutral conformance contract**  
Parent: [#595](https://github.com/safal207/LS/issues/595)  
Implementation issue: [#677](https://github.com/safal207/LS/issues/677)

## Purpose

The Evidence Gate is the decision boundary between an eligible effectful candidate and any later authorization-bundle layer.

```text
Recognition Gate
  -> Recognition-to-Evidence handoff
  -> Evidence Gate
  -> ALLOW / HOLD / BLOCK / ESCALATE
  -> later authorization bundle
  -> later commit-before-effect control
```

This contract consumes only `FORWARD_TO_EVIDENCE_GATE` handoffs. It does not execute actions and does not issue portable authorization bundles.

## Inputs

Each request binds:

- stable Recognition Gate result reference;
- candidate digest;
- intent digest;
- target-state digest;
- evidence references and evidence-snapshot digest;
- causal validation status;
- policy identifier and version;
- scope;
- reversibility classification;
- approval requirement and approval reference;
- verifier status.

Bindings are immutable across the handoff and Evidence Gate request.

## Decisions

### `ALLOW`

Evidence is complete and verified. Causal lineage and policy bindings are valid. Scope and reversibility are explicit. Any required approval is present.

`ALLOW` sets `authorization_bundle_eligible: true`, but always keeps `execution_authorized: false`.

### `HOLD`

The request may become admissible without changing the original intent, but evidence is missing, verification is pending, scope is incomplete, or reversibility is unknown.

The current execution attempt stops.

### `BLOCK`

The handoff is ineligible, a binding changed, policy or causal lineage is invalid, or evidence verification failed.

The current execution attempt stops and cannot be converted to `ALLOW` by a caller-controlled flag.

### `ESCALATE`

Required human approval or judgment is absent. Only the approval or clarification path may continue.

## Stable reason codes

The v0.1 conformance set includes:

- `EVIDENCE_SUFFICIENT`
- `EVIDENCE_MISSING`
- `VERIFICATION_PENDING`
- `CAUSAL_LINEAGE_INVALID`
- `HANDOFF_NOT_ELIGIBLE`
- `CANDIDATE_BINDING_MISMATCH`
- `POLICY_BINDING_MISMATCH`
- `HUMAN_APPROVAL_REQUIRED`

The evaluator also fails closed for missing result references, context mismatch, invalid upstream execution authority, failed verification, incomplete scope, and unknown reversibility.

## Security invariants

1. Recognition Gate `ALLOW` is not Evidence Gate `ALLOW`.
2. Evidence Gate `ALLOW` is not execution permission.
3. Every result sets `execution_authorized: false`.
4. Only `ALLOW` can become eligible for a later authorization bundle.
5. `HOLD`, `BLOCK`, and `ESCALATE` are terminal for the current execution attempt.
6. Candidate, intent, target-state, policy, and evidence bindings are checked deterministically.
7. Model output alone cannot satisfy evidence, causal, policy, scope, reversibility, or approval requirements.
8. This contract does not claim implementation or adoption by PythiaLabs or ProofPath.
9. Raw prompts, credentials, private task payloads, and unnecessary personal data are outside the fixture contract.

## Relationship to old draft PR #620

Draft PR #620 remains useful design evidence, but it is stacked on conflict-blocked Trusted Runtime branches. This v0.1 contract rebuilds only the Evidence Gate boundary on modern `main`.

ProofPath-style authorization bundles are deliberately deferred to a separate follow-up contract.

## Conformance

Run:

```bash
python tools/validate_evidence_gate_v0_1.py
```

The evaluator reads the manifest and eight independent case files, then writes:

```text
artifacts/evidence-gate-v0.1-result.json
```
