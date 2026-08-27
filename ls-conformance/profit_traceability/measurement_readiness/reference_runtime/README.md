# Attribution Reference Runtime V0

Deterministic local web-to-POS attribution specimen for Roby's Revenue Measurement Readiness V0.

This is **not** a production Roby's integration and does not authorize an offer experiment, profit claim, or `SCALE` decision.

## Authority boundary

V0 is bound to:

- product `PROD-ROBYS-WEB`;
- measurement plan `MPLAN-ROBYS-MENU-TO-VISIT-001`;
- `BASELINE` mode only;
- the approved 24-hour attribution window.

`EXPERIMENT` mode or a different TTL requires a new immutable economic candidate and an independent decision.

## Algorithm

1. Validate strict event and order fields.
2. Reject malformed campaign tokens, unsafe identifiers, and unknown fields.
3. Require canonical non-negative decimal strings with at most two decimal places.
4. Deduplicate identical `eventId` and `orderId` records.
5. Reject conflicting duplicate identifiers.
6. Match an order to the latest preceding event with the same token inside the approved 24-hour TTL.
7. Mark equally recent competing events as ambiguous.
8. Separate matched, expired, unmatched, and ambiguous orders.
9. Calculate attributable gross revenue, variable costs, and gross contribution before acquisition and experiment costs using exact decimal arithmetic.
10. Keep `profitDecision.ready = false`; Profit Traceability remains the authority for the later business decision.

## Run

```bash
python ls-conformance/profit_traceability/measurement_readiness/reference_runtime/attribute.py \
  ls-conformance/profit_traceability/measurement_readiness/reference_runtime/fixtures/reference_input.json

python -m unittest discover \
  -s ls-conformance/profit_traceability/measurement_readiness/reference_runtime/tests -v
```

The reference input deterministically produces `fixtures/reference_output.json`.

## Boundary

This runtime proves deterministic baseline attribution only. It does not provide acquisition costs, experiment costs, causal proof, or authorization to run or scale an offer.
