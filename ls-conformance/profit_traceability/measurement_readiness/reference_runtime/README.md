# Attribution Reference Runtime V0

Deterministic local web-to-POS attribution specimen for Roby's Revenue Measurement Readiness V0.

This is **not** a production Roby's integration and does not authorize an offer experiment, profit claim, or `SCALE` decision.

## Algorithm

1. Validate strict event and order fields.
2. Reject malformed campaign tokens and unknown fields.
3. Deduplicate identical `eventId` and `orderId` records.
4. Reject conflicting duplicate identifiers.
5. Match an order to the latest preceding event with the same token inside the configured TTL.
6. Mark equally recent competing events as ambiguous.
7. Separate matched, expired, unmatched, and ambiguous orders.
8. Calculate attributable gross revenue, variable costs, and gross contribution before acquisition and experiment costs using exact decimal arithmetic.
9. Keep `profitDecision.ready = false`; Profit Traceability remains the authority for the later business decision.

## Run

```bash
python ls-conformance/profit_traceability/measurement_readiness/reference_runtime/attribute.py \
  ls-conformance/profit_traceability/measurement_readiness/reference_runtime/fixtures/reference_input.json

python -m unittest discover \
  -s ls-conformance/profit_traceability/measurement_readiness/reference_runtime/tests -v
```

The reference input deterministically produces `fixtures/reference_output.json`.

## Boundary

This runtime proves deterministic attribution only. It does not provide acquisition costs, experiment costs, causal proof, or authorization to run or scale an offer.
