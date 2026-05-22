# Route Stability Evidence Map

Status: **reviewer evidence map for the LS Nash-style route stability proxy**.

This document maps the route-stability evidence surface into one reviewer-facing
view. It does not introduce a stronger claim than the existing Route Stability
Sample Contract. It explains how the files, tests, CI surface, and non-claims fit
together.

## Scope

The route-stability evidence surface answers one narrow question:

```text
For the deterministic local PR-review probe, does the full cooperative route beat
the single-route baseline, participant ablations, and a bad-ordering counterfactual?
```

Boundary:

```text
Nash-style route stability proxy, not a formal proof of Nash equilibrium.
```

## Primary Claim

The current checked-in route-stability sample is reviewer-useful only if this
chain stays intact:

```text
schema
-> checked-in sample
-> negative fixture
-> deterministic generator
-> regression test
-> CI summary
-> CI artifact
-> explicit non-claims
```

A reviewer should treat the sample as evidence only inside this chain.

## Evidence Map

| Evidence surface | File / path | What it proves | Reviewer check |
| --- | --- | --- | --- |
| Reviewer contract | `docs/ROUTE_STABILITY_SAMPLE_CONTRACT.md` | Defines the contract, files, local checks, CI behavior, artifact path, and non-claims. | Read first; verify that the contract and file paths below are in sync. |
| Evidence map | `docs/ROUTE_STABILITY_EVIDENCE_MAP.md` | Shows how all route-stability artifacts connect into a single reviewer chain. | Use as the top-level navigation map. |
| JSON Schema | `schemas/route_stability_sample.schema.json` | Defines the structural contract for a route-stability sample. | Confirm required fields and fixed values such as `demo` and `metric_version`. |
| Checked-in sample | `examples/route-stability/nash_route_stability_sample.json` | Provides the canonical current stable sample for reviewers. | Confirm it validates against the schema and matches stable demo fields. |
| Negative fixture | `python/tests/fixtures/route-stability/invalid_metric_version.json` | Proves malformed route-stability artifacts are rejected. | Confirm the test rejects wrong `metric_version` and unknown top-level fields. |
| Deterministic generator | `scripts/run_nash_route_stability_demo.py` | Produces the route-stability payload from the deterministic local probe. | Run with `--json` and compare stable core fields through the test. |
| Regression test | `python/tests/test_nash_route_stability.py` | Pins schema validity, negative fixture rejection, and sample-vs-demo consistency. | Run the pytest command below. |
| CI workflow | `.github/workflows/cognitive_trail_contract.yml` | Runs the route-stability regression path and generates the CI artifact. | Inspect workflow paths, summary text, and uploaded artifact list. |
| CI artifact | `reports/trails/ci/nash_route_stability.json` | Provides the generated route-stability JSON inside the CI evidence bundle. | Download the `cognitive-trail-report-${{ github.sha }}` artifact from Actions. |
| Reviewer packet | `docs/GRANT_REVIEWER_PACKET_2026.md` | Places the route-stability contract inside the grant-review evidence chain. | Verify it presents the contract as a separate evidence artifact. |
| Ecosystem index | `docs/ECOSYSTEM_REVIEWER_INDEX.md` | Places the route-stability contract in the broader LS / ProofPath / CML / LTP map. | Verify direct navigation to the contract is present. |
| README evidence surface | `README.md` | Surfaces the contract in the public landing path. | Verify English and Russian evidence bullets both include the contract. |

## Local Verification Path

Install dependencies:

```bash
python -m pip install jsonschema pytest
```

Run the route-stability regression test:

```bash
PYTHONPATH=.:python:python/modules python -m pytest python/tests/test_nash_route_stability.py
```

Generate the current local payload:

```bash
python scripts/run_nash_route_stability_demo.py --json
```

Generate the reviewer artifact path locally:

```bash
mkdir -p reports/trails/ci
python scripts/run_nash_route_stability_demo.py --json > reports/trails/ci/nash_route_stability.json
```

## What Must Stay True

For this evidence surface to remain reviewer-useful:

```text
1. The checked-in sample must validate against schemas/route_stability_sample.schema.json.
2. The negative fixture must be rejected by the same schema.
3. The checked-in sample must match deterministic demo --json output for stable core fields.
4. The CI workflow must run the route-stability regression path when relevant files change.
5. The CI workflow must generate reports/trails/ci/nash_route_stability.json.
6. Reviewer-facing docs must preserve the interpretation boundary.
```

## Current Deterministic Values

Current full cooperative route:

```text
pr_review>local>gonka>mimo
```

Current deterministic local result:

```text
full route reward:       0.7863
single baseline reward:  0.1207
coalition gain:          +0.6656
best counterfactual:     pr_review>local>gonka = 0.5613
stability margin:        +0.2250
decision:                stable_candidate
```

Participant marginal contributions:

```text
local: +0.3226
gonka: +0.2913
mimo:  +0.2250
```

## Failure Modes This Map Catches

| Failure mode | Expected detection surface |
| --- | --- |
| Sample shape drifts | JSON Schema validation fails. |
| Metric version drifts silently | Negative fixture and schema checks expose version mismatch behavior. |
| Extra undeclared fields become accepted | Negative fixture rejection fails. |
| Demo output changes but sample is not updated | Sample-vs-demo stable-field regression fails. |
| CI stops generating reviewer artifact | Workflow summary or artifact path check fails. |
| Reviewer docs overclaim the result | Non-claim boundary review fails. |

## Non-Claims

This evidence map does not claim:

```text
formal Nash equilibrium;
global route optimality;
global ranking of participants;
statistical sufficiency;
production-grade governance;
a reusable route without human authority;
that one deterministic probe generalizes to all PR reviews.
```

The positive claim is narrower:

```text
The repository now exposes a small, inspectable, regression-tested evidence chain
for one Nash-style route-stability proxy around a deterministic PR-review route.
```

## Reviewer Use

A reviewer can use this file as a checklist:

```text
1. Open the contract.
2. Inspect the schema and sample.
3. Confirm the negative fixture exists.
4. Run the route-stability test.
5. Generate the demo payload.
6. Inspect the CI workflow and artifact path.
7. Confirm public docs preserve the non-claim boundary.
```

If any item fails, the route-stability sample should be treated as incomplete or
stale until the evidence chain is repaired.
