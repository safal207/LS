# Route Artifact v2

Route Artifact v2 is the first narrow contract for the **Verified Route Network**.
It records a reusable problem-solving route without binding that route forever to
one model provider.

> Models are replaceable. A route is promoted only when its useful effect is
> reproducible.

## Boundary

A route artifact is evidence memory. It does not authorize merge, deployment,
execution, memory writes, or any other protected side effect.

## Verification tiers

### T0 — deterministic replay

T0 requires:

- a declared Git host, repository, ref, and exact commit;
- a local checkout whose `origin`, `HEAD`, declared ref, and commit all match;
- sandbox execution;
- an executable replay command;
- matching expected and observed exit codes;
- passing deterministic assertions;
- an evidence digest recomputed from the replay payload.

`verification.replay.evidence_digest` is SHA-256 over the canonical replay
object with only the `evidence_digest` field omitted. Changing the command,
exit codes, assertions, or replay result without updating that digest fails
verification. The top-level Route Artifact digest independently protects the
complete artifact.

A 40-character hexadecimal string alone is not T0 evidence.

Only T0 may contribute to confirmed metrics, route promotion, or a
training/distillation corpus.

### T1 — artifact-attested

T1 requires inspectable artifacts and explicit human sign-off, but it does not
claim deterministic replay, source-checkout binding, or sealed honeypot
ground-truth evaluation.

The seed route references:

- `safal207/LS#770`;
- `safal207/robys-coffee-house-demo#153`.

Those runs remain T1 until replayable evidence and outcomes exist.

### T2 — narrative-only

T2 is strictly narrative-only:

- no source;
- no exact HEAD;
- no sandbox claim;
- no replay;
- no artifact references;
- no human sign-off;
- no honeypot evaluation.

T2 is rejected from the canonical store. It may be parsed only in
rejection-audit mode so the rejection reason can be recorded.

## Sealed honeypot ground truth

A promotion-eligible honeypot is an explicit evidence object:

```json
{
  "id": "terminal_authority_multihop",
  "sealed": true,
  "ground_truth_digest": "<sha256>",
  "observed_result_digest": "<sha256>",
  "matched": true
}
```

Promotion checks both the protocol minimum count and the actual list of sealed,
matched ground-truth evaluations. The numeric counter must equal the number of
verified evaluation objects, so it cannot be inflated independently.

## Canonical content identity

Each route version has a SHA-256 content digest. The digest covers the whole
artifact with `integrity.content_digest` normalized to `null` before hashing.

Canonicalization:

- recursively normalizes strings and object keys to Unicode NFC;
- sorts object keys;
- uses compact UTF-8 JSON;
- rejects NaN and infinities;
- rejects key collisions created by Unicode normalization.

## Immutable lineage

A newer object may declare:

```json
{
  "lineage": {
    "supersedes": ["high-risk-code-review@1.0.0"]
  }
}
```

The older object is never edited. `superseded_by` is a derived registry
projection. Missing references, self-supersession, duplicate references, and
cycles fail closed. Cycle detection is iterative, so a deep valid lineage does
not escape through Python recursion depth.

## Promotion statuses and configured thresholds

- `draft`
- `experimental`
- `candidate`
- `validated`
- `deprecated`
- `revoked`

A non-T0 artifact cannot become `candidate` or `validated`.

The repository default in
`config/route_artifact_v2_promotion_thresholds.json` is:

- at least 20 T0 runs;
- at least two repositories;
- at least two task variants;
- at least one sealed, matched honeypot evaluation;
- zero unresolved critical false negatives;
- confidence intervals;
- maintainer approval for `validated`.

The verifier selects this external file by default, and the CLI can select a
different reviewed file with `--promotion-thresholds`. An artifact must carry
the exact numeric values selected by the verifier, so it cannot lower its own
thresholds. JSON Schema validates the policy shape; runtime verification binds
the artifact to the externally selected values and enforces them.

Zero unresolved critical false negatives, confidence intervals, and explicit
maintainer approval for `validated` remain mandatory v2 invariants and are not
weakened by the numeric threshold configuration.

These are operational gates, not a claim of statistical proof.

## Architecture hold

This PR defines the narrow route-evidence contract only. It does not establish a
generic governance lifecycle or a universal registry runtime.

Route-governance compatibility is evaluated separately by issue `#773` and
Draft PR `#774`. Their canonical manual specimen binds a decision to an exact
candidate digest and returns `REQUEST_MORE_EVIDENCE` without creating a promoted
`RouteVersionRecord` or ledger entry when the protocol floors are not met.

Until that decision is independently reviewed, this PR does not add:

- a generic candidate framework;
- a universal graph registry;
- additional lifecycle states;
- marketplace behavior;
- route or model rankings;
- CausalFragment execution tooling.

The current `status`, `metrics.maintainer_approved`, promotion-policy, lineage,
and registry-projection fields remain part of this Draft verifier contract.
They are not proof that an artifact may approve itself, finalize independent
truth, or gain action authority.

## One deterministic command

The verification environment must provide Python 3.11 and `jsonschema` 4.23 or
newer.

```bash
python3 scripts/verify_route_contract.py
```

The command validates the JSON Schema, materializes a real local Git checkout
for T0 source binding, verifies T0 and T1, proves canonical T2 rejection plus
rejection-audit acceptance, and runs all mutation/contract tests.

For a single artifact:

```bash
python3 scripts/verify_route_artifact.py \
  --artifact path/to/route.json \
  --repo-root path/to/its/checked-out-repository
```

`--repo-root` is mandatory for T0 ingestion. `--allow-t2-audit` is valid only
with `--artifact`.

## Non-goals

This slice does not add model integrations, a finding graph, a marketplace,
global model rankings, hidden chain-of-thought storage, or action authority.
