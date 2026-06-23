# Trusted Runtime evidence decisions and authorization bundles

Status: **reference implementation for issue #595**

This layer sits between causal validation and effectful execution.

```text
CML causal audit
-> EvidenceGateRequest
-> PythiaLabs or deterministic evidence gate
-> ALLOW / HOLD / BLOCK / ESCALATE
-> ProofPath authorization intent matching
-> portable authorization bundle
-> offline verification
-> later CaPU commit-before-effect boundary
```

## Responsibility boundary

LS owns sequencing, task/trail identity, canonical evidence references, policy
version, causal ancestry, scope, expiry, nonce state, and Cognitive Trail
continuity.

PythiaLabs owns evidence-sufficiency judgment. It may return:

- `ALLOW` — evidence, policy, causal ancestry, and scope are sufficient;
- `HOLD` — required evidence is incomplete or not verified yet;
- `BLOCK` — a deterministic policy or causal condition forbids authorization;
- `ESCALATE` — a human or higher-authority review is required.

ProofPath owns verifiable authorization packaging. It does not decide whether an
action is safe and does not execute the action. It binds an accepted decision to
scoped intent, policy, evidence, causal references, expiry, and a nonce.

Model output is never treated as authorization.

## Evidence gate request

`EvidenceGateRequest` is assembled by LS, not by a worker model. It carries:

- task and trail identifiers;
- actor and intent reference;
- requested scope;
- canonical evidence references;
- policy version;
- accepted causal-audit reference;
- evidence-artifact digest and verification status;
- missing-evidence, risk, and escalation signals.

The deterministic adapter is intentionally small and inspectable:

```text
causal invalid or risk flag -> BLOCK
manual review required       -> ESCALATE
evidence missing/unverified  -> HOLD
all required checks pass     -> ALLOW
```

## PythiaLabs adapter

`PythiaLabsEvidenceAdapter` is disabled by default and accepts an injected
runner. This avoids inventing a network or CLI contract that PythiaLabs does not
currently guarantee.

The adapter normalizes existing decision terms:

| Pythia/demo term | LS decision |
| --- | --- |
| `accepted`, `accept`, `ALLOW` | `ALLOW` |
| `deferred`, `pending`, `HOLD` | `HOLD` |
| `rejected`, `reject`, `BLOCK` | `BLOCK` |
| `escalated`, `human_review`, `ESCALATE` | `ESCALATE` |

For `ALLOW`, the adapter additionally requires:

- LS causal authorization is still valid;
- no LS risk flag or missing evidence remains;
- evidence references match the LS request;
- policy version matches;
- the response digest matches the verified LS evidence artifact;
- the Pythia artifact reports verified status.

A model-provided `ALLOW` string by itself fails closed.

## ProofPath authorization intent

`AuthorizationIntent` carries the fields that must be bound before execution:

```text
intent_id
+ task_id / trail_id
+ action_ref / scope
+ issued_at / expires_at
+ nonce
+ policy_version
+ evidence_refs / evidence_digest
+ causal_audit_refs
+ parent_cause
```

`ProofPathAuthorizationBundleAdapter` accepts only an `ALLOW` decision and
requires exact task, trail, policy, evidence, and causal-reference matching.
`HOLD`, `BLOCK`, and `ESCALATE` cannot produce an execution authorization.

## Portable bundle

The adapter exports the ProofPath v0.1 reviewer shape:

```text
proofpath-evidence/
  manifest.json
  decisions.jsonl
  hash-chain.json
  verifier-result.json
  privacy-report.json
  README.md
```

`manifest.json` records SHA-256 hashes for every non-manifest file.
`decisions.jsonl` contains the evidence decision followed by the execution
authorization. `hash-chain.json` binds both records in order.

The bundle intentionally contains references and verification metadata, not:

- prompts;
- raw model output;
- credentials;
- private task content;
- unnecessary personal or payment data.

## Offline verification

`verify_authorization_bundle_files()` does not call a model or live ProofPath
service. It checks:

1. required files exist;
2. manifest hashes match;
3. the decision and authorization records are present and ordered;
4. the hash chain is complete;
5. the decision is `ALLOW`;
6. task, trail, policy, scope, evidence, and parent references match;
7. the authorization is currently valid;
8. the privacy report passes;
9. the nonce has not already been consumed.

Example:

```python
store = InMemoryNonceStore()
result = verify_authorization_bundle_files(
    bundle.to_files(),
    now="2026-06-23T08:30:00Z",
    nonce_store=store,
    consume_nonce=True,
)
```

A second verification with `consume_nonce=True` rejects the same nonce as a
replay attempt.

## Fixtures

```text
python/tests/fixtures/trusted-runtime/evidence/
├── allow.json
├── hold.json
├── block.json
├── escalate.json
├── expired_intent.json
└── replay_attempt.json
```

The test suite also covers digest mismatch, malformed Pythia vocabulary,
policy mismatch, bundle tampering, and offline verification without rerunning a
model.

## Validation

```bash
python -m pip install jsonschema pytest
PYTHONPATH=.:python:python/modules \
  python -m pytest python/tests/test_trusted_runtime_evidence_authorization.py
```

This layer still does not execute a side effect. The next boundary is CaPU:

```text
verified authorization bundle
-> Gate
-> Incubate
-> Commit
-> Execute
```
