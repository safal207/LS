# LS GitHub Merge Preflight v0.1

## Promise

A user approval is valid only for the exact repository, pull request, and head SHA that was reviewed.

```text
exact PR identity
→ SHA-256 binding
→ ReviewDecision Gateway projection
→ ALLOW_CLAIM | BLOCK
→ Commit-Before-Effect
```

The preflight is offline and in-process. It opens no socket, accepts no credentials, calls no GitHub API, and performs no merge.

## Input

```json
{
  "repository": "safal207/LS",
  "pull_request_number": 813,
  "expected_head_sha": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "gateway_url": "in-process://review-decision-gateway-v0.1",
  "approval": {
    "approval_id": "github-merge:<binding_digest>",
    "signal": "USER_APPROVED",
    "actor": {"type": "USER", "id": "operator-1"},
    "reason": "exact-bound review decision",
    "evidence_ref": null,
    "exact_bindings_match": true,
    "expiry_policy_configured": false
  }
}
```

The binding contains action, repository, pull-request number, and expected head SHA. Compact sorted JSON is hashed with SHA-256:

```text
approval_id = github-merge:<binding_digest>
```

Changing any bound field invalidates the old approval.

## Output meaning

`ALLOW_CLAIM` means only that the request may be handed to Commit-Before-Effect. It does not authorize or perform a merge.

Every result contains:

```json
{
  "handoff": {
    "commit_before_effect_eligible": false,
    "execution_authorized": false
  },
  "merge_performed": false,
  "side_effects_performed": false
}
```

Eligibility becomes true only for an exact-bound `UserApproved` projection with approved authority, unused execution, a user/reviewer actor, and no Gateway side effect.

## Run and verify

```bash
python tools/run_github_merge_preflight_v0_1.py --input preflight.json
python tools/test_github_merge_preflight_core_v0_1.py
python tools/test_merge_preflight_integration_v0_1.py
```

A future network adapter and a future GitHub effect adapter require separate review. The effect adapter must enter through Commit-Before-Effect rather than bypassing it.
