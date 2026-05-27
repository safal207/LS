# Conductor PR Review CLI Patch Prompt

Use this prompt with Codex, Claude Code, or another repo-editing agent.

Goal: implement the first minimal LS Conductor CLI wrapper for issue `#586`.

## Patch-only instruction

You are editing the LS repository.

Implement a minimal developer-facing Conductor CLI wrapper:

```text
scripts/ls_conductor_review_pr.py
```

This is **not** a new architecture and not a new agent framework.

Reuse the existing PR-review scripts and functions:

```text
scripts/run_pr_review_trail_artifact.py
scripts/run_pr_role_market_demo.py
```

Do not rewrite LS internals.

## Files to modify

Preferred minimal file set:

```text
scripts/ls_conductor_review_pr.py
python/tests/test_ls_conductor_review_pr.py
```

Optional docs-only update if needed:

```text
docs/CONDUCTOR_API_VISION.md
```

Do not modify unrelated files.

## Existing functions to reuse

Import and reuse:

```python
from run_pr_review_trail_artifact import build_pr_review_artifact
from run_pr_role_market_demo import build_pr_role_market_payload
```

`build_pr_review_artifact(...)` already provides:

```text
artifact_type
created_at
repo
diff_source
stat
files
file_summary
selected_route
review_flow
signals
quality
route_reward
updated_route
decision
human_summary
diff_excerpt
diff_truncated
```

`build_pr_role_market_payload(...)` already provides:

```text
artifact_type
demo
live_model_calls
attached_role_outputs
available_actor_roster
role_actor_assignments
source_artifact
baseline
cooperative
synergy
best_role_contributor
best_actor_contributor
role_scores
ledger
next_step
```

## Required CLI

Add this command:

```bash
python scripts/ls_conductor_review_pr.py \
  --diff-file latest.diff \
  --policy cooperative_pr_review \
  --json
```

Also support git range mode:

```bash
python scripts/ls_conductor_review_pr.py \
  --base HEAD~1 \
  --head HEAD \
  --policy cooperative_pr_review \
  --json
```

Recommended args:

```text
--repo PATH                  default: repo root
--base REV                   default: HEAD~1
--head REV                   default: HEAD
--diff-file PATH             optional saved diff file
--policy TEXT                default: cooperative_pr_review
--store-path PATH            optional route stats path
--role-outputs PATH          optional role outputs JSON passed to role market
--output PATH                optional JSON output path
--max-diff-chars INT         default: 12000
--json                       print full Conductor JSON
```

## Required response shape

The script must emit stable JSON when `--json` is passed.

Top-level shape:

```json
{
  "artifact_type": "ls.conductor.review_pr.v0.1",
  "conductor_version": "v0.1",
  "task_type": "pr_review",
  "policy": "cooperative_pr_review",
  "final_answer": "...",
  "route_id": "...",
  "route_score": 0.0,
  "confidence": 0.0,
  "route_won_vs_single": true,
  "evidence": [],
  "disagreements": [],
  "signals": [],
  "decision": "...",
  "cost_usd": null,
  "latency_ms": 0,
  "artifact_path": null,
  "source_artifact": {},
  "role_market": {},
  "claim_boundary": "Conductor wrapper over LS PR-review route artifacts; not a formal proof of best answer or global model ranking."
}
```

## Mapping rules

Build the Conductor response from the two existing payloads:

```text
source_artifact = build_pr_review_artifact(...)
role_market = build_pr_role_market_payload(...)
```

Map fields:

```text
final_answer          <- source_artifact["human_summary"]
route_id              <- role_market["cooperative"]["route"] or source_artifact["selected_route"]["route_key"]
route_score           <- role_market["cooperative"]["reward"]
confidence            <- source_artifact["quality"]["overall"]
route_won_vs_single   <- role_market["cooperative"]["reward"] > role_market["baseline"]["reward"]
evidence              <- compact evidence items derived from signals and files
disagreements         <- [] for v0.1 unless role outputs expose unsupported_claims
decision              <- source_artifact["decision"]
signals               <- source_artifact["signals"]
latency_ms            <- role_market["cooperative"]["latency_ms"]
source_artifact       <- compact source artifact or full source artifact
role_market           <- compact role market payload or full payload
```

Evidence items can be simple in v0.1:

```json
{
  "claim": "Code or script files changed without an obvious test file in the same diff.",
  "source": "diff",
  "status": "signal",
  "signal_code": "missing_tests"
}
```

## Human output mode

When `--json` is not passed, print a short summary:

```text
LS Conductor PR Review
Policy: cooperative_pr_review
Decision: review_with_conditions
Route: pr_review>draft_reviewer>risk_critic>evidence_verifier>final_reviewer
Route won vs single: true
Confidence: 0.82
Summary: ...
```

## Implementation constraints

- Use only Python standard library plus existing LS modules.
- Keep the wrapper deterministic and local.
- Do not call hosted model APIs.
- Do not introduce new dependencies.
- Do not create a server in this PR.
- Do not implement full SDKs in this PR.
- Do not claim global model ranking.
- Do not claim formal Nash equilibrium.
- Preserve claim boundary exactly or very close to:

```text
Conductor wrapper over LS PR-review route artifacts; not a formal proof of best answer or global model ranking.
```

## Test requirements

Add a small pytest file:

```text
python/tests/test_ls_conductor_review_pr.py
```

Suggested tests:

1. `test_conductor_review_pr_json_shape_from_diff_file`
   - create a temporary `.diff` file;
   - run `scripts/ls_conductor_review_pr.py --diff-file <tmp> --json`;
   - parse JSON;
   - assert required top-level fields exist;
   - assert `artifact_type == "ls.conductor.review_pr.v0.1"`;
   - assert `policy == "cooperative_pr_review"`;
   - assert `claim_boundary` contains `not a formal proof`.

2. `test_conductor_review_pr_route_won_vs_single_is_boolean`
   - assert `route_won_vs_single` is a bool.

3. `test_conductor_review_pr_human_output`
   - run without `--json`;
   - assert output includes `LS Conductor PR Review`, `Policy:`, `Decision:`, `Route:`.

Use a tiny diff fixture inside the test body, for example:

```diff
diff --git a/scripts/example.py b/scripts/example.py
new file mode 100644
index 0000000..1111111
--- /dev/null
+++ b/scripts/example.py
@@ -0,0 +1,2 @@
+def demo():
+    return "ok"
```

## Definition of Done

- `python scripts/ls_conductor_review_pr.py --diff-file <sample.diff> --json` emits valid JSON.
- JSON includes `final_answer`, `route_id`, `route_score`, `confidence`, `route_won_vs_single`, `evidence`, `signals`, `decision`, `claim_boundary`.
- `python -m pytest python/tests/test_ls_conductor_review_pr.py` passes.
- Existing PR-review scripts still work.
- No hosted model calls are introduced.
- No global ranking or Nash overclaim is introduced.

## Suggested commit message

```text
feat: add minimal LS Conductor PR review CLI
```
