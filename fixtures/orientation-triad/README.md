# LS Orientation Triad v0.1 fixtures

These suites define the executable composition contract for TOC + RTOC + PATOC.

## Run

```bash
python -m pip install jsonschema==4.23.0

python tools/run_orientation_triad_fixtures.py \
  schemas/orientation-triad-v0.1.schema.json \
  fixtures/orientation-triad/mandatory-v0.1.json \
  fixtures/orientation-triad/precedence-v0.1.json
```

The runner materializes each case from `base_case`, applies deterministic dotted-path overrides, validates the triad input against the published Draft 2020-12 JSON Schema, executes the composition evaluator, and compares frozen outputs.

## Positive composition

A coordinated action candidate requires:

```text
TOC   = RESUME
RTOC  = RESUME
PATOC = EXECUTE_CANDIDATE
```

All workspace, trajectory, continuation, relationship, actor, and action bindings must agree.

Both user-agent and agent-agent candidates are covered.

## Blocking behavior

- any upstream `REJECT` blocks the triad;
- any upstream `REVALIDATE` requires revalidation unless a reject exists;
- PATOC `WAIT` blocks action until its condition is satisfied;
- any upstream `ABSTAIN` prevents a candidate unless a stronger verdict exists;
- unsupported center versions fail closed;
- any upstream claim of execution authorization is rejected;
- cross-center binding mismatches are rejected.

## Executable precedence

```text
REJECT > REVALIDATE > WAIT > ABSTAIN > COORDINATED_ACTION_CANDIDATE
```

Mixed-fault fixtures freeze:

- TOC reject plus PATOC wait → `REJECT / TOC_REJECTED`;
- RTOC revalidate plus PATOC wait → `REVALIDATE / RTOC_REVALIDATION_REQUIRED`;
- PATOC wait plus TOC abstain → `WAIT / PATOC_WAIT_REQUIRED`;
- actor binding mismatch plus RTOC revalidate → `REJECT / ACTOR_BINDING_MISMATCH`.

## Non-authorization invariant

Every output includes:

```json
{
  "execution_authorized": false,
  "downstream_gates_required": true
}
```

A coordinated action candidate is still only a candidate for downstream consent, policy, approval, and effect gates.
