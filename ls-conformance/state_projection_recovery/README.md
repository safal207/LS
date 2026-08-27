# State Projection Recovery Conformance v0.1

This fixture tests whether a runtime can reconstruct **derived project/index/live projections** from intact durable thread state without mutating conversation content.

External failure-class evidence: `openai/codex#26990`.

Related LS work: #930, #757, #597.

## Boundary

```text
durable conversation/thread state
  != persisted project/index projection
  != live sidebar/task projection
```

A missing or stale projection is not evidence that the durable conversation is gone.

## Recovery pipeline

```text
authoritative durable state
  -> schema/capability discovery
  -> Windows path normalization
  -> project-membership reconstruction
  -> generation/staleness checks
  -> live hydration reconciliation
  -> redacted report
```

The evaluator is vendor-neutral. It does not require `thread-workspace-root-hints` or any other single vendor field.

## Invariants

- durable thread existence is independent from live UI visibility;
- a stale in-memory generation must not overwrite a richer durable generation;
- project/index repair must not change conversation-content digests;
- optional schema fields may be absent without implying data loss;
- normal and Windows verbatim paths (`\\?\C:\...`) normalize to the same project root;
- ambiguous project membership fails closed;
- a second recovery pass must be idempotent.

## Verdicts

- `RECOVERED_PROJECTION`
- `NO_CHANGES_REQUIRED`
- `BLOCK_STALE_GENERATION`
- `BLOCK_CONTENT_MUTATION`
- `UNRESOLVED_AMBIGUOUS_PROJECT`
- `INCONCLUSIVE_MISSING_DURABLE_EVIDENCE`

## Run

From repository root:

```bash
python ls-conformance/state_projection_recovery/run_fixture.py \
  ls-conformance/state_projection_recovery/fixtures/cases.json
```

Run tests:

```bash
python -m unittest \
  ls-conformance/state_projection_recovery/test_state_projection_recovery.py
```

The CLI prints only redaction-safe counts, capabilities, verdicts, and invariant results. Synthetic fixture paths and IDs stay inside fixture input and are not emitted in the report.

## Fixture families

1. collapsed persisted projection while durable threads remain intact;
2. stale generation attempting to overwrite a richer projection;
3. healthy persisted state with broken live hydration;
4. schema variant without `thread-workspace-root-hints`;
5. Windows verbatim-path equivalence;
6. ambiguous project-root match;
7. attempted conversation-content mutation during projection repair;
8. idempotent second recovery.

## Non-goals

- editing a real Codex state database;
- publishing local paths, prompts, titles, tokens, or raw session files;
- treating LS output as runtime execution authority;
- claiming adoption by OpenAI or any other vendor.

This is a conformance oracle: implementations may use different storage schemas as long as the observable invariants hold.
