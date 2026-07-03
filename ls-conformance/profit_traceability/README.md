# profit_traceability

## Purpose

Prove that product activity, revenue, and a successful implementation do not automatically become profit.

This fixture family extends Product Traceability with an economic evidence chain:

```text
EconomicSignal
  -> EconomicHypothesisCandidate
  -> independent EconomicDecision
  -> BusinessOutcome
  -> UnitEconomicsRecord
  -> ProfitRecord
  -> ProfitSnapshot
```

## Core invariants

- Revenue is not profit.
- Attribution is not causation.
- Experiment approval is not a profitable business model.
- A durable economic record status must be authorized by its decision verdict.
- All monetary values in one economics record use one currency and must be finite.
- Confirmed outcomes require both attribution evidence and POS/receipt revenue evidence.
- Every included cost category requires its matching evidence type; excluded costs must be zero.
- Net contribution equals attributable revenue minus variable, acquisition, and experiment costs.
- `SCALE` requires `APPROVE_EXPERIMENT`, a confirmed business outcome, exact unit-economics binding, and positive confirmed net contribution.
- `REQUEST_MORE_EVIDENCE` cannot fabricate an outcome, unit economics, or durable profit record.
- A snapshot must preserve durable records and exactly represent active and unresolved state.

## First truthful specimen

The Roby's menu-to-visit candidate asks whether a clearer map call-to-action and a time-bounded combo offer can create positive net contribution.

The fixture deliberately returns `REQUEST_MORE_EVIDENCE` because the current system has no:

- measured baseline conversion;
- durable web-action to order attribution;
- attributable revenue evidence;
- variable-cost and acquisition-cost evidence;
- confirmed contribution margin.

Therefore no business outcome, unit-economics record, durable profit record, or active profit state is created.

## Validate

```bash
python -m pip install -r ls-conformance/profit_traceability/requirements.txt
python ls-conformance/profit_traceability/validate.py ls-conformance/profit_traceability/fixtures/robys_menu_to_visit.blocked.json
python -m unittest discover -s ls-conformance/profit_traceability/tests -v
```

## Relationship to Product Traceability

Product Traceability answers:

```text
Did the product change solve the intended user problem?
```

Profit Traceability answers:

```text
Did the confirmed product outcome create attributable positive economics?
```

This is a stacked domain specimen over Product Traceability V0. It does not claim that profit can be guaranteed or that attribution alone proves causation.
