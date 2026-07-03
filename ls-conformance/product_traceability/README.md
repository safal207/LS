# product_traceability

## Purpose

Prove that a product hypothesis does not become active product state merely because code was implemented or a test passed.

This fixture family connects a real Roby's mobile-web observation to the LS governance pattern:

```text
ProductSignal
  -> ProductHypothesisCandidate
  -> independent ProductDecision
  -> ProductRecord
  -> ProductSnapshot
```

The first specimen covers a dark flicker visible only during the first downward scroll on a cold mobile load.

## Core invariants

- An observation is not a confirmed root cause.
- Experiment approval is not product adoption.
- Implementation is not outcome.
- Verification is not user value.
- A decision must bind the exact immutable hypothesis content.
- A durable record status must be authorized by its decision verdict.
- `ADOPTED` requires an `APPROVE_EXPERIMENT` decision, verified exact-head implementation, and confirmed outcome evidence.
- An `ADOPTED` record must reference the exact implementation and outcome it promotes.
- A snapshot must preserve its durable record and exactly reflect active and unresolved state.
- `REQUEST_MORE_EVIDENCE` must not fabricate implementation, outcome, or a durable product record.

## Current truthful state

The reference fixture intentionally stops at `EXPERIMENT_APPROVED`:

- the signal exists;
- the hypothesis is content-bound by SHA-256;
- an independent reviewer approved a bounded experiment;
- no implementation is attached;
- no evidence is attached;
- no successful outcome is claimed;
- no active product state is changed.

## Validate

Install the validator dependencies, including support for schema formats:

```bash
python -m pip install -r ls-conformance/product_traceability/requirements.txt
python ls-conformance/product_traceability/validate.py ls-conformance/product_traceability/fixtures/robys_first_scroll_flicker.pending.json
python -m unittest discover -s ls-conformance/product_traceability/tests -v
```

Plain `jsonschema` installation is not sufficient for this fixture family because missing optional format dependencies may cause malformed timestamps to be accepted.

## Promotion rule

A product record may become `ADOPTED` only when all of the following are present:

1. the governing verdict is `APPROVE_EXPERIMENT`;
2. exact repository and 40-character head SHA;
3. implementation status `VERIFIED`;
4. `implementationRef` bound to that implementation;
5. before/after cold-cache evidence;
6. mobile regression evidence;
7. LCP and CLS guardrail evidence;
8. a `CONFIRMED` outcome referencing those evidence objects;
9. `outcomeRef` bound to that outcome;
10. snapshot source and active references that include the adopted record.

## Architectural boundary

Shared governance semantics:

```text
candidate -> decision -> durable record -> snapshot -> supersession
```

Product-domain semantics:

- user impact;
- target segment;
- falsification condition;
- experiment metric;
- UX, performance, and business evidence.

This specimen tests a domain adapter boundary. It does not claim that the current Route Registry runtime is already universal.
