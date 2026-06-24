# Temporal Orientation Center fixtures

This directory contains the v0.1 conformance suites for LS temporal orientation.

## Run

```bash
python tools/validate_temporal_orientation_schema.py \
  schemas/temporal-orientation-v0.1.schema.json \
  fixtures/temporal-orientation/mandatory-v0.1.json \
  fixtures/temporal-orientation/additional-v0.1.json \
  fixtures/temporal-orientation/precedence-v0.1.json

python tools/evaluate_temporal_orientation.py \
  fixtures/temporal-orientation/mandatory-v0.1.json \
  --check-expected

python tools/evaluate_temporal_orientation.py \
  fixtures/temporal-orientation/additional-v0.1.json \
  --check-expected

python tools/evaluate_temporal_orientation.py \
  fixtures/temporal-orientation/precedence-v0.1.json \
  --check-expected
```

Each command exits with status `0` only when the inputs satisfy the published schema and every fixture produces its frozen verdict and reason code.

## Covered boundaries

- a new continuation inside the same trajectory can return `RESUME`;
- valid current orientation returns `RESUME`;
- stale continuation returns `REJECT`;
- revoked approval returns `REJECT`;
- completed side-effect replay returns `REJECT`;
- retrieval miss does not turn authoritative replay state into permission;
- target-state drift returns `REVALIDATE`;
- incomplete dependency chain returns `ABSTAIN`;
- same-workspace intent substitution returns `REJECT`;
- `RESUME` preserves downstream policy and effect gates.

## Executable precedence

The mixed-fault suite freezes the normative priority:

```text
REJECT > REVALIDATE > ABSTAIN > RESUME
```

It currently proves that:

- stale continuation plus target-state drift returns `REJECT / CONTINUATION_MISMATCH`;
- target-state drift plus incomplete dependency chain returns `REVALIDATE / TARGET_STATE_DRIFT`.

These rows make evaluator order part of the portable contract rather than an incidental implementation detail.

## Output invariant

Every result includes:

```json
{
  "verdict": "RESUME | REVALIDATE | ABSTAIN | REJECT",
  "reason_code": "STABLE_MACHINE_CODE",
  "execution_authorized": false,
  "downstream_gates_required": true
}
```

A temporal continuation verdict never grants global execution permission.
