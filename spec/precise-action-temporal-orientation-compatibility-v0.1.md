# PATOC compatibility mapping v0.1

Status: Draft

## Upstream TOC mapping

| TOC source | PATOC destination |
|---|---|
| `location.workspace_id` | `context.workspace_id` |
| `location.trajectory_id` | `context.trajectory_id` |
| `location.continuation_id` | `context.continuation_id` |
| active target-state evidence | `expected_transition.current_state_digest` |
| allowed next action digest | authoritative `expected_action_digest` |

PATOC assumes the supplied TOC snapshot has already produced a valid temporal continuation candidate. PATOC does not reinterpret a stale continuation as a valid action context.

## Upstream RTOC mapping

| RTOC source | PATOC destination |
|---|---|
| relationship identifier | `context.relationship_id` |
| allowed actor | `action_identity.actor_id` |
| active delegation scope | exact action target and parameter scope |
| allowed action digest | `action_identity.action_digest` |
| active boundaries | authoritative parameter and target constraints |

PATOC assumes the supplied RTOC snapshot has already established current relational applicability. A historical grant or relationship memory cannot be converted directly into an exact action candidate.

## Concrete tool-call mapping

| Tool-call concept | PATOC field |
|---|---|
| tool/action name | `action_identity.action_type` |
| canonical action hash | `action_identity.action_digest` |
| caller | `action_identity.actor_id` |
| resource or object | `action_identity.target_id` |
| canonical arguments hash | `parameters.parameter_digest` |
| full arguments | `parameters.exact_arguments` |
| protected arguments | `parameters.immutable_fields` |
| workflow position | `temporal_position.sequence_index` |
| required earlier calls | `dependencies.previous_action_ids` |
| external event receipts | `dependencies.required_event_ids` |
| approval receipts | `dependencies.required_approval_ids` |
| idempotency key | `side_effect_control.side_effect_key` |
| expected result | `expected_transition.expected_state_digest` |
| required receipt | `verification` |

## Fail-closed boundary

```text
validated TOC context
        +
validated RTOC context when applicable
        ↓
PATOC exact-action evaluation
        ↓
EXECUTE_CANDIDATE / WAIT / REVALIDATE / ABSTAIN / REJECT
        ↓
downstream consent / policy / approval / effect gates
```

`EXECUTE_CANDIDATE` never means that the tool call has permission to execute.

## GitHub example

For the sequence:

1. create branch;
2. update file on that branch;
3. open pull request;

PATOC binds the exact repository, branch, path, content digest, sequence index, side-effect key, and expected receipt. Updating `main`, changing the path, or skipping the branch-creation predecessor is not an equivalent action.
