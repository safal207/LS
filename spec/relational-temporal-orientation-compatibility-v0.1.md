# RTOC compatibility mapping v0.1

Status: Draft

## User ↔ agent

| Source concept | RTOC field |
|---|---|
| user identity | `relationship.participants[].actor_id` with role `principal` |
| agent identity | `relationship.participants[].actor_id` with role `delegate` |
| user grant | `authority_edges[]` |
| grant scope | `authority_edges[].scope_digest` |
| revoked or replaced permission | `authority_edges[].state` |
| user boundary or consent rule | `boundaries[]` |
| shared task intent | `shared_orientation.shared_intent_digest` |
| completed communication or delegated effect | `completed_history.completed_relational_effect_keys[]` |
| unresolved promise | `commitments[]` |

A past grant remains historical evidence after revocation, but it cannot support a current `RESUME` verdict.

## Agent ↔ agent

| Source concept | RTOC field |
|---|---|
| coordinator agent | participant role such as `coordinator` |
| receiving agent | participant role such as `executor` |
| delegated capability | `authority_edges[]` |
| accepted transfer of responsibility | `handoff.state = accepted` |
| incomplete transfer | `handoff.state = incomplete` |
| branch, repository, task, or object scope | `authority_edges[].scope_digest` |
| shared target | `shared_orientation.shared_target_state_digest` |
| already completed delegated effect | `completed_history.completed_relational_effect_keys[]` |

An agent-agent handoff requires both a valid delegation edge and an accepted handoff when the proposed action declares that requirement.

## Separation of concerns

```text
relationship event memory
        ↓
RTOC relational validity
        ↓
RESUME / REVALIDATE / ABSTAIN / REJECT
        ↓
downstream consent / policy / approval / effect gates
```

Retrieval of a relationship event does not prove that it is current. A current relational verdict does not grant execution permission.

## Conformance fixtures

- user-agent coverage: `fixtures/relational-temporal-orientation/mandatory-v0.1.json`;
- agent-agent coverage: `fixtures/relational-temporal-orientation/agent-agent-v0.1.json`;
- precedence coverage: `fixtures/relational-temporal-orientation/precedence-v0.1.json`.
