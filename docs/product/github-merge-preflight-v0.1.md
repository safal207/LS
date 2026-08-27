# LS GitHub Merge Preflight v0.1

## Promise

A merge approval is bound to the exact repository, pull request, base SHA, head SHA, and immutable exact-head evidence bundle.

```text
Exact-head Evidence Acquisition #802
→ evidence SHA-256
→ approval binding
→ ReviewDecision Gateway projection
→ ALLOW_CLAIM | BLOCK
→ Commit-Before-Effect #691
```

The preflight opens no socket, accepts no credential, calls no GitHub mutation API, and performs no merge.

## Canonical binding

```json
{
  "action": "github.merge_pull_request",
  "repository": "safal207/LS",
  "pull_request_number": 813,
  "expected_base_sha": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
  "expected_head_sha": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "expected_evidence_sha256": "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"
}
```

Compact sorted JSON is hashed with SHA-256:

```text
approval_id = github-merge:<binding_digest>
evidence_ref = exact-head-evidence:<expected_evidence_sha256>
```

Changing the base, head, evidence bytes, repository, or pull-request number invalidates the approval.

## Output boundary

`ALLOW_CLAIM` means only that the exact-bound approval projection may enter the next gate.

```json
{
  "handoff": {
    "commit_before_effect_eligible": true,
    "live_evidence_verified": false,
    "authorization_bundle_verified": false,
    "execution_authorized": false
  },
  "merge_performed": false,
  "side_effects_performed": false
}
```

Before an effect, downstream must independently verify that the live evidence bundle from #802 matches every bound field, validate the authorization bundle and verifier-result reference, then perform the durable commit required by #691.

## Components

- `github_merge_binding_v0_1.py` — canonical binding and drift rejection;
- `github_merge_projection_v0_1.py` — fail-closed Gateway response evaluation;
- `merge_preflight_adapter_v0_1.py` — composition over a local service object;
- canonical fixture and deterministic unit/integration controls.

No component contains a GitHub token, network client, shell command, or merge call.
