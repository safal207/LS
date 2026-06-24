# Precise Action Temporal Orientation Center v0.1 implementation record

Issue: `#671`

Status: Pull request candidate

Implemented:

- normative specification and TOC/RTOC compatibility mapping;
- Draft 2020-12 JSON Schema;
- deterministic evaluator;
- fixture materializer, schema validator, and frozen-output runner;
- fixtures for all five verdict families;
- exact parameters and immutable-field validation;
- sequence, timing, dependency, event, approval, precondition, and replay checks;
- expected-transition and verification-contract checks;
- mixed-fault executable precedence;
- GitHub Actions conformance workflow;
- explicit non-authorization invariant on every result.

Local pre-PR validation covered 19 cases with zero schema or expected-output failures.

Normative precedence:

```text
REJECT > REVALIDATE > WAIT > ABSTAIN > EXECUTE_CANDIDATE
```

The issue should remain open until CI or an independent read-only execution confirms the committed branch.
