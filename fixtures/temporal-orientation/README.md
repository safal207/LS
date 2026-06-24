# Temporal Orientation Center fixtures

This directory contains the mandatory v0.1 conformance suite for LS temporal orientation.

## Run

```bash
python tools/evaluate_temporal_orientation.py \
  fixtures/temporal-orientation/mandatory-v0.1.json \
  --check-expected
```

The command exits with status `0` only when every fixture produces its frozen verdict and reason code.

## Covered boundaries

- valid current orientation returns `RESUME`;
- stale continuation returns `REJECT`;
- revoked approval returns `REJECT`;
- completed side-effect replay returns `REJECT`;
- target-state drift returns `REVALIDATE`;
- incomplete dependency chain returns `ABSTAIN`;
- same-workspace intent substitution returns `REJECT`;
- `RESUME` preserves downstream policy and effect gates.

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
