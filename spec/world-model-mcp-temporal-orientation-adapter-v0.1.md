# world-model-mcp → LS Temporal Orientation Adapter v0.1

Status: Draft

## Purpose

Define a deterministic adapter from public world-model-mcp progress and constraint artifacts into `temporal-orientation-v0.1` inputs.

The adapter separates three questions:

1. Was the relevant constraint recovered?
2. Is the recovered evidence valid for the current trajectory and continuation?
3. Does the resulting temporal orientation permit `RESUME`, require `REVALIDATE` or `ABSTAIN`, or require `REJECT`?

The adapter does not grant execution permission.

## Proposed source mapping

| world-model-mcp concept | Temporal Orientation Center field |
|---|---|
| benchmark instance + arm | `location.trajectory_id` |
| resumed execution identifier | `location.continuation_id` |
| previous continuation | `location.resumed_from_continuation_id` |
| loaded task intent / directive digest | `current_frame.intent_digest` |
| current repository or task target digest | `current_frame.target_state_digest` |
| per-fact `asserted_by` | evidence provenance |
| per-fact `confirmer` | confirmation provenance |
| `confirmation_state` | confirmed-constraint eligibility |
| `valid_from` | `validity.valid_from` |
| `invalidated_at` | `validity.invalidated_at` |
| confirmed loaded constraints | `active_authority.confirmed_constraints` |
| prior completed effect record | `completed_history.completed_side_effect_keys` |
| proposed PreToolUse action | `next_transition.allowed_next_action_digest` |

## Required outputs

The adapter MUST emit:

- a schema-valid `TemporalOrientationState`;
- a separate authoritative-state object;
- a proposed-action object;
- source artifact references and digests;
- adapter warnings for missing or ambiguous source fields.

## Fail-closed rules

- missing trajectory identity → `ABSTAIN`;
- missing continuation identity for resumed work → `ABSTAIN`;
- stale or wrong-trajectory constraint remains visible but cannot authorize use;
- unconfirmed current-run memory cannot self-authorize downstream action;
- retrieval confidence is diagnostic only;
- confirmed learned constraint validity is evaluated independently from retrieval confidence;
- authoritative completed effects override a retrieval miss.

## Initial fixtures

1. confirmed constraint recovered for current trajectory and continuation;
2. confirmed constraint recovered for wrong trajectory;
3. confirmed constraint recovered for stale continuation;
4. low-reliability retrieval with valid confirmed constraint;
5. current-run unconfirmed write attempting self-authorization;
6. completed effect absent from retrieval but present in authoritative ledger;
7. target-state drift after constraint extraction;
8. missing source field produces adapter warning and fail-closed verdict.
