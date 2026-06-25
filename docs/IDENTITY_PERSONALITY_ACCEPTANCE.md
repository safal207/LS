# Identity → Personality Acceptance Path

## Purpose

This focused acceptance path proves that LS can turn repeated verified
experience into governed runtime personality without collapsing evidence,
identity governance, and execution authority into one step.

It complements the broader Identity Control Plane acceptance from #648/#650.
That path proves durable timeline publication, signed catalog generations, and
viewer integrity. This path proves the newer semantic continuation:

```text
3x VerifiedEpisode v0.2
  -> LessonAggregation v0.2
  -> review-only IdentityUpdateProposal
  -> independent approval
  -> profile patch
  -> durable patch commit
  -> profile activation
  -> AgentPersonalityProjection
  -> bounded runtime Markdown
```

## Core guarantees

### Evidence remains evidence

A single episode cannot modify identity. Two episodes cannot modify identity.
Three source-backed supporting episodes may create only a review-only proposal.

`failed` and `contradicting` episodes retain their own roles:

- failure remains visible but does not increase support;
- contradiction blocks proposal creation;
- expired and superseded episodes remain inspectable but do not count as current
  influence.

### Governance remains separate

The proposing runtime and approving human are different actors.

The lifecycle remains:

```text
proposal -> approval -> patch -> durable commit -> activation
```

No proposal applies itself. No patch activates before its commit. Replay cannot
reapply the same application ID.

### Personality remains downstream

The active profile receives one explicitly namespaced governed trait:

```text
working_tendencies.test_before_claim
```

`AgentPersonalityProjection` reads that active profile in the explicit
`project:ls` context. The projection carries the exact active profile reference,
application reference, aggregation/proposal/approval references, and supporting
episode references.

The projection cannot:

- approve or apply identity;
- create a profile patch;
- authorize execution;
- grant or deny tools;
- bypass governance;
- expand scope.

### Rollback invalidates runtime personality

Rollback creates a new profile version instead of deleting history. Because the
old projection is bound to the prior active profile reference, validation marks
it `STALE` after rollback.

## Run

From the repository root:

```bash
PYTHONPATH=.:python:python/modules \
  python scripts/run_identity_personality_acceptance.py \
  --output /tmp/identity-personality-acceptance.json \
  --markdown-output /tmp/identity-personality.md
```

The acceptance function itself is side-effect free. Files are written only by
the explicit CLI output arguments, so repeated in-memory execution cannot mutate
identity state or silently reapply an application.

Inspect the JSON:

```bash
python -m json.tool /tmp/identity-personality-acceptance.json > /dev/null
```

Inspect the bounded runtime adapter:

```bash
cat /tmp/identity-personality.md
```

The Markdown is suitable for delivery through `AGENTS.md`, `CLAUDE.md`, or a
system-prompt adapter. It is not the identity source of truth.

## Reviewer checks

1. `aggregation.status` is `READY_FOR_REVIEW`.
2. `aggregation.support_count` is exactly `3`.
3. The proposal has `approval_required=true` and `applied=false`.
4. The proposer and approver actors differ.
5. The application increments profile version from `1` to `2` exactly once.
6. The projection is bound to profile v2 and contains
   `working_tendencies.test_before_claim`.
7. The projected item preserves aggregation, proposal, approval, and episode
   references.
8. The projection source refs include the exact profile and application refs.
9. Every acceptance and projection authority effect is `false`.
10. Repeating the same input produces the same deterministic IDs.
11. Reapplying the same application fails closed.
12. A contradictory episode produces `CONFLICTED` and no proposal.
13. Rollback creates profile v3 and marks the old projection `STALE`.

## CI

The dedicated workflow runs on Python 3.9 and 3.11 and verifies:

- Ruff;
- compilation;
- focused pytest coverage;
- aggregation, proposal, and projection JSON Schemas;
- one-command JSON output;
- bounded Markdown generation.

## Non-goals

This acceptance does not:

- replace the signed catalog/dashboard acceptance;
- approve identity automatically;
- infer personality from free-form prose;
- treat repetition as proof;
- turn personality language into authority;
- treat a prompt file as durable identity state.

## Principle

> Experience may propose a change. Governance may apply it. Runtime personality
> may express it. None of those stages may impersonate the authority of another.
