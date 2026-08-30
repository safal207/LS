# Build Week reproducible attack matrix

Evidence subject: [`299db4b239eddad32b621f31bd8b47de25f40fd7`](https://github.com/safal207/LS/commit/299db4b239eddad32b621f31bd8b47de25f40fd7)

Run every required scenario with one command:

```bash
./scripts/run_build_week_demo.sh
```

| Scenario | Evidence mutation | Risk in a naive pipeline | LS decision check | Expected result | Fixture |
| --- | --- | --- | --- | --- | --- |
| Stale approval | Review is `APPROVED` for SHA-A while the current PR head is SHA-B | The workflow sees an approval-like state and ignores which code was approved | `review.commit_sha == pull_request.current_head_sha` | `BLOCKED / STALE_APPROVAL` | [`stale-approval.json`](../demo/stale-approval.json) |
| Spoofed reviewer | Login resembles an allowed bot, but the authenticated account type is `User` | A string-only allowlist accepts an impersonating identity | Login, account type, authenticated provenance, and route must match trusted policy | `BLOCKED / UNTRUSTED_REVIEWER` | [`spoofed-reviewer.json`](../demo/spoofed-reviewer.json) |
| Required lane did not run | The required `security` lane is explicitly `NOT_RUN` and has no evidence ID | Missing execution is collapsed into success or absence is ignored | Required lanes preserve `PASS`, `FAIL`, and `NOT_RUN` as distinct states | `BLOCKED / REQUIRED_LANE_NOT_RUN` | [`required-check-not-run.json`](../demo/required-check-not-run.json) |
| Valid current-head review | Reviewer, provenance, approval SHA, and required lanes all bind to the current head | The positive control proves the gate is not an unconditional blocker | Every required check passes for the exact current SHA | `TRUSTED / ALL_REQUIRED_EVIDENCE_VALID` | [`trusted-current-head.json`](../demo/trusted-current-head.json) |

## Failure-closed properties

- A blocked gate exits non-zero during normal use.
- Demo fixture mode exits zero only when both the observed verdict and reason code match the required matrix.
- The runner keeps its own required matrix, so changing a fixture's `expected_outcome` cannot silently redefine success.
- Fixture-only `expected_outcome` data is excluded from the decision-evidence digest and cannot authorize a verdict.
- A stale required-lane result is classified by SHA binding before its `PASS` or `FAIL` outcome is interpreted.
- `TRUSTED` means only eligible for explicit human-authorized delivery; LS performs no delivery action.
