# OVC → VerifiedEpisode v0.2 Bridge

Status: Implementation candidate

## Purpose

This bridge converts an Outcome Verification Center result into a governed `VerifiedEpisode v0.2` learning candidate.

It closes a semantic gap:

- OVC can verify `expected`, `failed`, and `unexpected` outcomes;
- `VerifiedEpisode v0.1` treats only matched outcomes as verified;
- failed and unexpected outcomes must remain trusted evidence without being rewritten as successful matches.

## Input boundary

The bridge accepts only OVC results that preserve:

```json
{
  "verdict": "VERIFIED",
  "experience_eligible": true,
  "execution_authorized": false,
  "retroactive_authorization_created": false,
  "downstream_learning_gate_required": true
}
```

The request also binds execution, action, actor, target, side-effect, expected and verified states, receipt identity, causal trace, observer evidence, task/trail/orientation/transition, lesson interpretation, and lifecycle policy.

## Verdicts

- `WRITE_CANDIDATE` — propose one immutable verified episode for storage;
- `REVIEW` — OVC outcome class and lesson interpretation disagree;
- `FORGET` — retention expired;
- `ABSTAIN` — required lesson or safely redacted evidence is incomplete;
- `REJECT` — non-verified, unsafe, replayed, unbound, or provenance-deficient input.

## Normative precedence

```text
REJECT > REVIEW > FORGET > ABSTAIN > WRITE_CANDIDATE
```

## Outcome classes

- `expected` → `supporting` evidence;
- `failed` → `failure` evidence;
- `unexpected` → `contradicting` evidence.

An unexpected verified state is trusted evidence, not a successful match.

## Deterministic identity

The episode ID canonically binds execution ID, action digest, side-effect key, causal trace ID, outcome class, verified state digest, and lesson repeat key. Replayed episode or causal-trace identities are rejected.

## Lifecycle

Every episode carries retention class, review date, optional expiry, redactable fields, redaction state, and optional supersession reference. Expired material returns `FORGET`. Redaction may not remove required causal provenance.

## Identity boundary

One verified episode never modifies stable identity:

```json
{
  "experience_eligible": true,
  "identity_update_eligible": false,
  "identity_update": {
    "allowed": false,
    "applied": false
  }
}
```

Aggregation and identity proposal remain separate governed operations tracked by #630.

## v0.1 compatibility

- `expected` projects to v0.1 `VERIFIED / MATCHED`;
- `failed` and `unexpected` project fail-closed to `UNVERIFIED / MISMATCHED`.

This prevents old consumers from counting verified failure or contradiction as supporting success evidence.

## Artifacts

- `schemas/trusted_runtime/ovc_verified_episode_adapter_v0.1.schema.json`;
- `schemas/trusted_runtime/verified_episode_v0.2.schema.json`;
- `tools/adapt_outcome_verification_to_verified_episode.py`;
- `tools/run_ovc_verified_episode_fixtures.py`;
- `fixtures/ovc-verified-episode/`;
- tracking issue #697.
