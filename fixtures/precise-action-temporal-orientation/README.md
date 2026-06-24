# Precise Action Temporal Orientation Center fixtures

These suites define the executable PATOC v0.1 contract.

## Run

```bash
python -m pip install jsonschema==4.23.0

python tools/run_precise_action_temporal_orientation_fixtures.py \
  schemas/precise-action-temporal-orientation-v0.1.schema.json \
  fixtures/precise-action-temporal-orientation/mandatory-v0.1.json \
  fixtures/precise-action-temporal-orientation/precedence-v0.1.json
```

The runner:

1. materializes each case from `base_case`;
2. applies deterministic dotted-path overrides;
3. validates the orientation against the published Draft 2020-12 JSON Schema;
4. executes the deterministic evaluator;
5. compares verdict, reason code, and the non-authorization invariant with frozen expectations.

## Covered behavior

- exact action returns `EXECUTE_CANDIDATE`;
- pending approval, missing event, future schedule, or incomplete predecessor returns `WAIT`;
- stale parameters or target state returns `REVALIDATE`;
- missing parameters or verification contract returns `ABSTAIN`;
- wrong actor, wrong target, parameter substitution, immutable-field mutation, invalid sequence, or completed replay returns `REJECT`.

## Executable precedence

```text
REJECT > REVALIDATE > WAIT > ABSTAIN > EXECUTE_CANDIDATE
```

Mixed-fault fixtures freeze:

- wrong actor plus target-state drift → `REJECT / WRONG_ACTOR`;
- target-state drift plus approval pending → `REVALIDATE / TARGET_STATE_DRIFT`;
- approval pending plus missing verification contract → `WAIT / APPROVAL_PENDING`.

## Output invariant

Every result includes:

```json
{
  "execution_authorized": false,
  "downstream_gates_required": true
}
```

PATOC identifies the exact action candidate. Consent, policy, approval, and effect gates remain downstream.
