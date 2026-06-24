# Relational Temporal Orientation Center fixtures

These suites define the executable v0.1 relationship-orientation contract.

## Run

```bash
python -m pip install jsonschema==4.23.0

python tools/run_relational_temporal_orientation_fixtures.py \
  schemas/relational-temporal-orientation-v0.1.schema.json \
  fixtures/relational-temporal-orientation/mandatory-v0.1.json \
  fixtures/relational-temporal-orientation/agent-agent-v0.1.json \
  fixtures/relational-temporal-orientation/precedence-v0.1.json
```

The runner materializes each case from the suite's `base_case`, applies deterministic dotted-path overrides, validates the resulting orientation against the published JSON Schema, executes the reference evaluator, and compares the verdict and reason code with the frozen expectation.

## Covered boundaries

- valid user-agent delegation returns `RESUME`;
- valid agent-agent delegation plus accepted handoff returns `RESUME`;
- revoked delegation returns `REJECT`;
- an action attempted by the wrong actor returns `REJECT`;
- shared-intent drift returns `REVALIDATE`;
- an active-boundary mismatch returns `REJECT`;
- incomplete handoff returns `ABSTAIN`;
- completed relational-effect replay returns `REJECT`;
- disputed trust returns `REVALIDATE`;
- unresolved commitment precondition returns `ABSTAIN`;
- `RESUME` never grants execution permission.

## Executable precedence

```text
REJECT > REVALIDATE > ABSTAIN > RESUME
```

The mixed-fault suite freezes two portable requirements:

- revoked authority plus shared-intent drift returns `REJECT / AUTHORITY_REVOKED`;
- shared-intent drift plus incomplete handoff returns `REVALIDATE / SHARED_INTENT_DRIFT`.

## Output invariant

Every evaluator result includes:

```json
{
  "execution_authorized": false,
  "downstream_gates_required": true
}
```

Relational orientation determines whether a shared continuation is coherent. Consent, policy, approval, and effect gates remain downstream.
