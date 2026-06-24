# LS Relational Temporal Orientation Center v0.1

Status: Draft

## Purpose

The Relational Temporal Orientation Center (RTOC) answers:

> Where are these participants in their relationship now, given the history of roles, delegation, commitments, trust, boundaries, handoffs, and superseding events?

The existing Temporal Orientation Center answers where an agent is in its own trajectory. RTOC answers where multiple actors are in a shared relational trajectory.

RTOC is not a social graph, chat history, reputation score, or authorization engine. It is a deterministic projection from evidence-backed relationship events into a current relational orientation verdict.

## Core invariant

A relationship fact may be historically true and still be invalid now.

Safe coordinated continuation requires current agreement across:

- participant identity;
- relationship epoch;
- active roles;
- shared intent;
- active delegation edges;
- open and fulfilled commitments;
- current boundaries;
- trust state;
- handoff completeness;
- completed relational effects.

## Proposed state

```yaml
RelationalTemporalOrientationState:
  relationship_version: relational-temporal-orientation-v0.1

  relationship:
    relationship_id: string
    relationship_type: user_agent | agent_agent | team | organization
    relationship_epoch: string
    participants:
      - actor_id: string
        role: string
        participation_state: active | suspended | exited

  temporal_frame:
    as_of: timestamp
    established_at: timestamp
    last_mutual_confirmation_at: timestamp | null
    invalidated_at: timestamp | null

  shared_orientation:
    shared_intent_digest: string
    shared_target_state_digest: string
    shared_context_digest: string | null

  authority_edges:
    - grant_id: string
      grantor: string
      grantee: string
      capability: string
      scope_digest: string
      state: active | revoked | expired | superseded
      valid_from: timestamp
      invalidated_at: timestamp | null

  commitments:
    - commitment_id: string
      debtor: string
      creditor: string
      obligation_digest: string
      state: open | fulfilled | superseded | cancelled | disputed

  boundaries:
    - boundary_id: string
      owner: string
      rule_digest: string
      state: active | superseded | revoked

  trust:
    state: confirmed | conditional | disputed | revoked
    evidence_refs: [string]

  handoff:
    handoff_id: string | null
    from_actor: string | null
    to_actor: string | null
    state: absent | proposed | accepted | rejected | incomplete

  completed_history:
    completed_relational_effect_keys: [string]
    superseded_grants: [string]
    resolved_commitments: [string]

  next_relational_transition:
    verdict: RESUME | REVALIDATE | ABSTAIN | REJECT
    reason_code: string
    allowed_actor_id: string | null
    allowed_action_digest: string | null
```

## Inputs

A conformant RTOC evaluator consumes:

1. recovered relational state;
2. current authoritative relationship state;
3. proposed actor and action;
4. evidence references for delegation, commitment, boundary, trust, and handoff claims.

Free-form summaries, model agreement, semantic similarity, and recency alone MUST NOT establish current relational authority.

## Verdicts

- `RESUME`: the shared relational continuation invariant passed;
- `REVALIDATE`: the relationship still exists, but shared intent, role, target, trust, boundary, or delegation state drifted;
- `ABSTAIN`: evidence is insufficient to determine the current relationship state or handoff responsibility;
- `REJECT`: participant mismatch, revoked authority, violated boundary, duplicate relational effect, invalid relationship epoch, or another unsafe relational condition was detected.

`RESUME` MUST NOT grant downstream execution permission.

Every result MUST preserve:

```json
{
  "execution_authorized": false,
  "downstream_gates_required": true
}
```

## Required checks

Checks are evaluated fail-closed:

1. relationship and participant identity completeness;
2. relationship epoch match;
3. participant membership and active role;
4. proposed actor match;
5. active delegation grant and scope match;
6. boundary compatibility;
7. completed relational-effect replay;
8. shared-intent and target-state drift;
9. trust-state requirements;
10. commitment preconditions;
11. handoff completeness;
12. proposed action digest match.

## Normative precedence

```text
REJECT > REVALIDATE > ABSTAIN > RESUME
```

Mixed-fault fixtures MUST make this precedence executable.

## Initial reason codes

### REJECT

- `RELATIONSHIP_EPOCH_MISMATCH`
- `ACTOR_RELATIONSHIP_MISMATCH`
- `ROLE_NOT_ACTIVE`
- `AUTHORITY_REVOKED`
- `AUTHORITY_SCOPE_MISMATCH`
- `RELATIONAL_BOUNDARY_VIOLATION`
- `RELATIONAL_EFFECT_ALREADY_COMPLETED`
- `TRUST_REVOKED`
- `ACTION_DIGEST_MISMATCH`

### REVALIDATE

- `SHARED_INTENT_DRIFT`
- `SHARED_TARGET_STATE_DRIFT`
- `ROLE_CHANGED`
- `AUTHORITY_SUPERSEDED`
- `BOUNDARY_CHANGED`
- `TRUST_DISPUTED`

### ABSTAIN

- `MISSING_RELATIONSHIP_EVIDENCE`
- `INCOMPLETE_HANDOFF`
- `AMBIGUOUS_RESPONSIBILITY`
- `UNRESOLVED_COMMITMENT_PRECONDITION`

### RESUME

- `RELATIONAL_ORIENTATION_VALID`

## Initial conformance fixtures

1. `valid_user_agent_delegation_resume`
2. `revoked_delegation_rejected`
3. `delegation_to_actor_a_used_by_actor_b_rejected`
4. `shared_intent_drift_revalidate`
5. `boundary_violation_rejected`
6. `incomplete_agent_handoff_abstain`
7. `completed_relational_effect_replay_rejected`
8. `disputed_trust_revalidate`
9. `open_commitment_precondition_abstain`
10. `resume_does_not_grant_execution_permission`
11. `revoked_authority_precedes_shared_intent_drift`
12. `shared_intent_drift_precedes_incomplete_handoff`

## Relationship to other LS layers

### Temporal Orientation Center

TOC evaluates an actor's individual trajectory. RTOC evaluates the shared relational trajectory. Safe coordinated continuation may require both verdicts to pass.

```text
individual temporal orientation
              +
relational temporal orientation
              ↓
coordinated continuation candidate
              ↓
downstream policy / approval / effect gates
```

### CML

CML may provide causal evidence explaining why delegation, trust, boundaries, roles, or commitments changed. RTOC consumes verified relationship events and projects the current state.

### LTP / communication layers

Communication history may provide evidence, but messages are not automatically authoritative relationship state. Supersession, confirmation, actor identity, and validity must be explicit.

### Osaznanie / agent identity

RTOC allows an agent to preserve not only "who I have been" but also "who we have been to each other," while keeping trust, privacy, and authority evidence-bound.

## Non-goals

- inferring emotions as authoritative facts;
- assigning universal social reputation;
- replacing consent, authorization, or policy engines;
- treating past intimacy or access as permanent permission;
- letting one participant unilaterally manufacture mutual confirmation;
- using model-written relationship summaries as the source of truth.

## Acceptance criteria

- JSON Schema for `relational-temporal-orientation-v0.1`;
- deterministic reference evaluator;
- stable verdict and reason codes;
- fixtures for all four verdict families;
- executable mixed-fault precedence;
- explicit separation between relationship memory, relational validity, and execution permission;
- compatibility mapping for user-agent and agent-agent relationships;
- CI validation and frozen expected outputs.
