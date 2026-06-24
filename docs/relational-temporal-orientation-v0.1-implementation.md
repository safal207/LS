# Relational Temporal Orientation Center v0.1 implementation record

Issue: `#670`

Status: Implementation candidate

Implemented:

- JSON Schema: `schemas/relational-temporal-orientation-v0.1.schema.json`;
- deterministic evaluator: `tools/evaluate_relational_temporal_orientation.py`;
- fixture materializer, schema validator, and expected-output runner: `tools/run_relational_temporal_orientation_fixtures.py`;
- mandatory user-agent suite;
- agent-agent accepted-handoff suite;
- mixed-fault precedence suite;
- CI workflow;
- user-agent and agent-agent compatibility mapping;
- explicit non-authorization invariant on every verdict.

Local pre-landing validation covered 13 cases with zero schema or expected-output failures.

Normative precedence:

```text
REJECT > REVALIDATE > ABSTAIN > RESUME
```

The issue remains open until a visible repository CI run or independent read-only execution confirms the committed artifacts.
