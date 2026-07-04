# Roby's Revenue Experiment Readiness V0

## Purpose

Turn the blocked Profit Traceability candidate into a concrete measurement implementation plan without treating `REQUEST_MORE_EVIDENCE` as authorization to run the revenue experiment.

```text
REQUEST_MORE_EVIDENCE
  -> measurement plan
  -> privacy-safe campaign token
  -> verified web/POS join
  -> baseline evidence
  -> new immutable economic candidate
  -> new independent economic decision
```

## Parent binding

The readiness bundle is not a free-standing copy of identifiers. It is validated against the merged parent fixture:

```text
ls-conformance/profit_traceability/fixtures/robys_menu_to_visit.blocked.json
```

The validator requires exact agreement on:

- parent bundle id;
- product id;
- economic candidate id;
- decision id;
- candidate binding and digest;
- `REQUEST_MORE_EVIDENCE` verdict.

Only the fixed repository-relative locator above is accepted. Absolute paths and traversal with `..` are rejected.

## Current truthful state

The reference fixture is `INSTRUMENTATION_REQUIRED / BLOCKED`:

- no Roby's repository or exact head SHA is attached;
- no durable `campaign_token` implementation exists;
- no POS export contract is verified;
- no baseline export exists;
- no cost-source evidence exists.

No offer experiment, profit claim, or `SCALE` decision is authorized.

## Measurement contract

The plan requires:

- a non-PII campaign token;
- a 24-hour token TTL matching the attribution window;
- a `visit_intent_created` web event;
- POS fields `order_id`, `ordered_at`, `campaign_token`, `gross_revenue`, `currency`, and `variable_cost`;
- deduplication by `event_id` and `order_id`;
- a seven-day baseline;
- evidence for instrumentation, join integrity, baseline export, and cost sources.

Every evidence object is bound to the exact implementation id and 40-character head SHA. A readiness decision is bound to the exact plan and, after instrumentation, to the verified implementation.

## Reference attribution runtime

[`reference_runtime`](./reference_runtime/README.md) provides an executable standard-library implementation of the required web-event to POS-order join.

V0 is bound to the approved measurement plan, accepts only `BASELINE` mode and the 24-hour attribution window, and rejects noncanonical money formats or unsafe identifiers.

It deterministically classifies orders as matched, expired, unmatched, or ambiguous and calculates attributable gross revenue, variable costs, and gross contribution before acquisition and experiment costs.

The runtime remains a local conformance specimen. It is not connected to the real Roby's website or POS and never marks a profit decision as ready.

## Promotion rules

`READY_FOR_BASELINE` requires:

1. verified exact-head implementation;
2. no unresolved blockers;
3. instrumentation test evidence;
4. join-integrity evidence;
5. exact plan and implementation bindings;
6. complete snapshot reconstruction with no unknown plan references.

`BASELINE_COMPLETE` additionally requires:

1. baseline export evidence;
2. cost-source evidence.

After baseline completion, a new immutable economic candidate and independent decision are required before any offer experiment can run.

## Validate

```bash
python -m pip install -r ls-conformance/profit_traceability/requirements.txt
python ls-conformance/profit_traceability/measurement_readiness/validate.py \
  ls-conformance/profit_traceability/measurement_readiness/fixtures/robys_menu_to_visit.instrumentation_required.json
python -m unittest discover \
  -s ls-conformance/profit_traceability/measurement_readiness/tests -v

python ls-conformance/profit_traceability/measurement_readiness/reference_runtime/attribute.py \
  ls-conformance/profit_traceability/measurement_readiness/reference_runtime/fixtures/reference_input.json
python -m unittest discover \
  -s ls-conformance/profit_traceability/measurement_readiness/reference_runtime/tests -v
```

The readiness regression suite contains 15 positive and negative tests. The attribution runtime adds 19 tests covering complete deterministic output, decision-bound baseline authority, deduplication, ambiguity, TTL boundaries, canonical decimal money handling, and fail-closed input validation.
