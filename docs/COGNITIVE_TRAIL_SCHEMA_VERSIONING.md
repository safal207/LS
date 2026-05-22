# Cognitive Trail Schema Versioning

Status: **working local research MVP**.

This note defines how the LS Cognitive Trail Run schema should evolve without
breaking reviewer evidence, checked-in examples, CI artifacts, or generated
runtime reports.

Current schema version:

```text
cognitive_trail_run.v0.1
```

Current schema file:

```text
schemas/cognitive_trail_run.schema.json
```

Current contract:

```text
docs/COGNITIVE_TRAIL_RUN_CONTRACT.md
```

## Why Versioning Matters

A Cognitive Trail Run is not only an internal data structure. It is a reviewer
artifact.

It may appear in:

- checked-in examples;
- generated runtime JSON reports;
- Markdown reviewer reports;
- GitHub Actions artifacts;
- grant packets;
- technical reviews;
- future benchmark datasets.

Therefore, schema changes must preserve the ability to explain what an old
artifact meant at the time it was generated.

## Current Contract Boundary

The current schema is intentionally strict:

```text
additionalProperties: false
schema_version: cognitive_trail_run.v0.1
```

This means unknown fields are rejected unless the schema is explicitly updated.
That is useful for reviewer trust because every accepted field has a defined
meaning.

## Current Required Fields

Every `cognitive_trail_run.v0.1` artifact requires:

```text
schema_version
task_id
task_type
status
input_ref
route
evidence
result
contribution_summary
repeatability
```

These fields define the durable reviewer contract:

```text
task
-> input reference
-> route of roles and actors
-> evidence
-> measured result
-> contribution attribution
-> repeatability decision
```

## Version Naming

Use this format:

```text
cognitive_trail_run.vMAJOR.MINOR
```

Examples:

```text
cognitive_trail_run.v0.1
cognitive_trail_run.v0.2
cognitive_trail_run.v1.0
```

Guidance:

- `v0.x` means the contract is still research-MVP / pre-stable.
- `v1.0` should be used only after examples, validator behavior, generator
  behavior, and reviewer docs are stable enough to be cited externally.

## Non-Breaking Changes

A change is usually non-breaking if old valid `v0.1` artifacts still validate
without modification.

Examples:

- Add a new optional enum value only when old enum values still work.
- Clarify documentation without changing schema semantics.
- Add validator warnings that do not fail existing valid examples.
- Improve Markdown rendering without changing JSON shape.
- Improve generator defaults while preserving generated contract shape.

Because the schema uses `additionalProperties: false`, adding a new optional
field to the schema is technically non-breaking for old artifacts, but it still
requires documentation and tests because it changes the reviewer vocabulary.

## Breaking Changes

A change is breaking if an old valid artifact may fail validation or be
interpreted differently.

Examples:

- Rename or remove a required field.
- Change the meaning of `lift`, `positive_lift`, `top_role`, or `top_actor`.
- Change reward semantics without preserving old interpretation.
- Require a field that old examples do not contain.
- Remove an enum value used by checked-in examples.
- Change route ordering semantics.
- Change whether `needs_more_runs` or `should_repeat_route` means what it meant
  in previous artifacts.

Breaking changes require a new `schema_version`.

## When to Bump to v0.2

Bump to `cognitive_trail_run.v0.2` when the contract is still experimental but
needs a meaningful shape change.

Examples:

- Add human-review outcome labels.
- Add fixture-corpus identifiers.
- Add role-ablation results.
- Add CI/test outcome signals to the result object.
- Add a structured benchmark-run metadata block.
- Add explicit migration metadata.

Expected process:

```text
update schema
-> add migration note
-> update validator
-> update generator
-> add v0.2 example
-> keep v0.1 examples valid or intentionally archived
-> update quickstart and evidence snapshot
```

## When to Bump to v1.0

Bump to `cognitive_trail_run.v1.0` only when LS can commit to a stable public
contract.

Suggested threshold:

- at least one small public PR-review fixture corpus exists;
- multiple checked-in examples pass validation;
- generator behavior is stable;
- validator semantics are documented;
- CI uploads JSON and Markdown artifacts;
- non-claims are stable;
- schema migration expectations are clear;
- reviewers can reproduce the evidence path without private context.

## Migration Rules

When a new schema version is introduced, add a migration section to this file.

Each migration section should include:

```text
from version
to version
why the change exists
field-level changes
compatibility impact
migration example
validator behavior
status of old examples
```

Template:

```md
## Migration: cognitive_trail_run.v0.1 -> cognitive_trail_run.v0.2

Reason:

Field changes:

Compatibility:

Example before:

Example after:

Validator behavior:

Old examples:
```

## Compatibility Expectations

The repository should keep reviewer confidence by following these rules:

1. Do not silently reinterpret old artifacts.
2. Do not overwrite old examples to look like new ones unless the task is clearly
   a migration PR.
3. Keep at least one canonical example for each still-documented version.
4. If old examples are deprecated, mark them explicitly rather than deleting the
   interpretation history.
5. Validator failures should explain whether the problem is schema shape,
   semantic consistency, or version mismatch.

## Validator Expectations

Current validator path:

```text
scripts/validate_cognitive_trail_runs.py
```

Current behavior validates:

- JSON parseability;
- Draft 2020-12 schema validity;
- artifact schema compliance;
- lift consistency;
- positive_lift consistency;
- contiguous route steps;
- top_role present in route;
- top_actor present in route;
- contribution summary matching result fields.

Future validator behavior should be explicit about versions.

Recommended future behavior:

```text
schema_version == cognitive_trail_run.v0.1 -> validate with v0.1 schema + v0.1 semantics
schema_version == cognitive_trail_run.v0.2 -> validate with v0.2 schema + v0.2 semantics
unknown schema_version -> fail with clear message
```

## Generator Expectations

Current generator path:

```text
scripts/generate_pr_review_trail_run.py
```

The generator should never emit a new schema version accidentally.

A schema-version bump should require an intentional code change near the
version constant, plus tests proving the generated output validates against the
intended schema.

Expected rule:

```text
Changing generated schema_version requires updating schema, tests, docs, examples, and validator behavior in the same PR or commit series.
```

## Documentation Expectations

When schema semantics change, update at least:

```text
docs/COGNITIVE_TRAIL_RUN_CONTRACT.md
docs/COGNITIVE_TRAIL_EVIDENCE_SNAPSHOT.md
docs/COGNITIVE_TRAIL_REVIEWER_QUICKSTART.md
docs/COGNITIVE_TRAIL_PR_REVIEW_BENCHMARK_NOTE.md
```

If the change affects contributor work, update:

```text
docs/COGNITIVE_TRAIL_CONTRIBUTOR_TASKS.md
```

If the change affects grant/reviewer positioning, update:

```text
docs/GRANT_REVIEWER_PACKET_2026.md
docs/ECOSYSTEM_REVIEWER_INDEX.md
```

## Example: Safe Optional Extension

A safe optional extension might add human-review outcome labels.

Possible new field:

```text
human_review_outcome
```

Possible values:

```text
accepted_finding
rejected_finding
needs_follow_up
false_positive
not_reviewed
```

Because this changes reviewer interpretation and benchmark strength, it should
probably be introduced as `cognitive_trail_run.v0.2`, even if it is optional.

## Example: Breaking Reward Change

If `baseline_reward`, `cooperative_reward`, or `lift` changes from heuristic
score to a different scoring model, do not reuse `v0.1` semantics.

Bad:

```text
same schema_version, new reward meaning
```

Good:

```text
new schema_version
migration note
updated benchmark note
old examples preserved
new examples added
```

## Non-Claims

This versioning note does not claim:

- that `v0.1` is production-stable;
- that the current schema is statistically sufficient;
- that the current reward semantics are final;
- that the current schema can support every future Cognitive Trail use case;
- that a version bump proves the benchmark is stronger.

It only defines how schema evolution should remain inspectable.

## One-Line Rule

```text
A Cognitive Trail schema version may evolve, but reviewer evidence must remain interpretable, reproducible, and explicitly bounded.
```
