# Outcome Verification Center fixtures

These suites define the executable OVC v0.1 contract.

Implementation tracking: issue `#692`.

## Run

```bash
python -m pip install jsonschema==4.23.0

python tools/run_outcome_verification_fixtures.py \
  schemas/outcome-verification-v0.1.schema.json \
  fixtures/outcome-verification/mandatory-v0.1.json \
  fixtures/outcome-verification/precedence-v0.1.json
```

The runner validates each verification object against the published Draft 2020-12 schema, executes the deterministic evaluator, compares frozen outputs, and checks all safety invariants.

## Covered outcomes

- expected state verified;
- failed execution verified against unchanged pre-state;
- unexpected but coherent final state verified;
- receipt-only evidence rejected as insufficient;
- delayed consistency returns `REOBSERVE`;
- evidence missing after the deadline returns `ABSTAIN`;
- partial and contradictory outcomes return `INVESTIGATE`;
- identity mismatch, untrusted issuer, replay, invalid time, and scope mismatch return `REJECT`.

## Executable precedence

```text
REJECT > INVESTIGATE > REOBSERVE > ABSTAIN > VERIFIED
```

## Safety invariants

Every result includes:

```json
{
  "execution_authorized": false,
  "retroactive_authorization_created": false,
  "downstream_learning_gate_required": true
}
```

Only `VERIFIED` results have `experience_eligible: true`.
