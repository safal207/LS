# Route Stability Fixture Interpretation

Status: **reviewer-facing interpretation note for route-stability fixtures**.

This note explains how to read current and future route-stability fixtures in LS.
It does not change the schema, tests, reward calculation, or claim boundary.

## Boundary

```text
Nash-style route stability proxy, not a formal proof of Nash equilibrium.
```

A fixture is useful only as bounded reviewer evidence. It should not be read as a
global route ranking, global participant ranking, or production governance claim.

## Current Fixtures

| Fixture | Expected behavior | Reviewer meaning |
| --- | --- | --- |
| `examples/route-stability/nash_route_stability_sample.json` | Accepted by schema and pinned against deterministic demo output for stable fields. | Shows the current PR-review route-stability sample is reproducible for the checked-in deterministic probe. |
| `python/tests/fixtures/route-stability/invalid_metric_version.json` | Rejected by schema. | Shows that unsupported metric versions and undeclared fields do not silently enter reviewer evidence. |
| `python/tests/fixtures/route-stability/missing_full_route_reward.json` | Rejected by schema. | Shows that incomplete route evidence is blocked when a required route field is missing. |

## Current Stable Candidate Sample

The current accepted sample represents one deterministic local PR-review probe:

```text
full route:          pr_review>local>gonka>mimo
reward:              0.7863
single baseline:     0.1207
coalition gain:      +0.6656
best counterfactual: pr_review>local>gonka = 0.5613
stability margin:    +0.2250
decision:            stable_candidate
```

Reviewer interpretation:

```text
For this local deterministic probe, the full cooperative route beats the single
baseline, participant ablations, and a bad-ordering counterfactual.
```

This does not imply that the same route is globally optimal or statistically
sufficient.

## Negative Fixture Meaning

A negative fixture should prove that invalid evidence is rejected before it enters
reviewer discussion.

Current negative behavior:

```text
wrong metric_version       -> rejected by schema
unknown top-level field    -> rejected by schema
missing full_route.reward  -> rejected by schema
```

Future negative fixtures should cover:

```text
unsupported stability.decision values;
unsupported route.kind values;
missing interpretation boundary;
invalid or inconsistent reward fields.
```

## Future Fixture Types

The next useful fixture set should include:

| Fixture type | Expected decision | Reviewer meaning |
| --- | --- | --- |
| Stable candidate | `stable_candidate` | Full route beats the defined baseline and counterfactuals inside one bounded deterministic probe. |
| Not stable yet | `not_stable_yet` | Full route does not clear the route-stability threshold; reviewer should not treat the route as repeatable evidence yet. |
| Missing-field negative | rejected | Schema blocks incomplete evidence packets. |
| Unsupported-decision negative | rejected | Schema blocks undeclared decisions from entering reviewer evidence. |

## Interpretation Checklist

Before citing a fixture as evidence, a reviewer should check:

```text
1. Does the fixture validate or fail intentionally?
2. Is the expected decision documented?
3. Is the interpretation boundary present?
4. Does a regression test cover the fixture?
5. Does the evidence map explain where the fixture fits?
6. Are non-claims preserved?
```

## Non-Claims

This fixture note does not claim:

```text
formal Nash equilibrium;
global route optimality;
global participant ranking;
statistical sufficiency;
production-grade governance;
that one deterministic probe generalizes to all PR reviews.
```
