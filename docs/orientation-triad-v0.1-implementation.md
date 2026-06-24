# Orientation Triad v0.1 implementation record

Issue: `#672`

Status: Pull request candidate

Implemented:

- explicit TOC/RTOC/PATOC input and output contract;
- Draft 2020-12 JSON Schema;
- deterministic fail-closed composition evaluator;
- stable verdict and reason-code precedence;
- cross-center workspace, trajectory, continuation, relationship, actor, and action bindings;
- upstream non-authorization invariant enforcement;
- user-agent and agent-agent examples;
- 21 mandatory fixtures;
- 4 mixed-fault precedence fixtures;
- schema validation and frozen-output runner;
- GitHub Actions conformance workflow.

Local pre-PR validation covered 25 cases with zero schema or expected-output failures.

Normative precedence:

```text
REJECT > REVALIDATE > WAIT > ABSTAIN > COORDINATED_ACTION_CANDIDATE
```

A positive triad result remains non-authorizing:

```json
{
  "execution_authorized": false,
  "downstream_gates_required": true
}
```
