# LS Orientation Triad v0.1

Status: Implementation candidate

## Purpose

The Orientation Triad composes three independent LS orientation results:

1. Temporal Orientation Center (TOC): where is the actor in its trajectory?
2. Relational Temporal Orientation Center (RTOC): where are the participants in their shared relationship trajectory?
3. Precise Action Temporal Orientation Center (PATOC): what exact action is the correct next transition now?

The triad answers:

> Do temporal position, relational applicability, and exact action identity agree on one coordinated action candidate?

The triad is not an authorization engine, policy engine, consent engine, or tool runtime.

## Core invariant

No center can substitute for another:

- temporal coherence does not prove relational authority;
- relational coherence does not prove exact action correctness;
- exact action correctness does not grant execution permission.

A coordinated action candidate exists only when:

- TOC returns `RESUME`;
- RTOC returns `RESUME`;
- PATOC returns `EXECUTE_CANDIDATE`;
- all center versions are supported;
- all centers preserve the non-authorization invariant;
- workspace, trajectory, continuation, relationship, actor, and action bindings agree.

## Input contract

Each upstream center result is paired with deterministic bindings recovered from the validated input that produced that result.

```yaml
OrientationTriadInput:
  triad_version: orientation-triad-v0.1

  toc:
    center_version: temporal-orientation-v0.1
    verdict: RESUME | REVALIDATE | ABSTAIN | REJECT
    reason_code: string
    execution_authorized: boolean
    downstream_gates_required: boolean
    bindings:
      workspace_id: string
      trajectory_id: string
      continuation_id: string
      action_digest: string

  rtoc:
    center_version: relational-temporal-orientation-v0.1
    verdict: RESUME | REVALIDATE | ABSTAIN | REJECT
    reason_code: string
    execution_authorized: boolean
    downstream_gates_required: boolean
    bindings:
      relationship_id: string
      actor_id: string
      action_digest: string

  patoc:
    center_version: precise-action-temporal-orientation-v0.1
    verdict: EXECUTE_CANDIDATE | WAIT | REVALIDATE | ABSTAIN | REJECT
    reason_code: string
    execution_authorized: boolean
    downstream_gates_required: boolean
    bindings:
      workspace_id: string
      trajectory_id: string
      continuation_id: string
      relationship_id: string
      actor_id: string
      action_digest: string
```

Bindings MUST come from validated structured state, not free-form model summaries.

## Output contract

```yaml
OrientationTriadResult:
  triad_version: orientation-triad-v0.1
  verdict: COORDINATED_ACTION_CANDIDATE | WAIT | REVALIDATE | ABSTAIN | REJECT
  reason_code: string
  coordinated_action_digest: string | null
  execution_authorized: false
  downstream_gates_required: true
  checks: array
```

`COORDINATED_ACTION_CANDIDATE` means only that all three orientation layers agree on the same action candidate.

## Fail-closed checks

1. all three center results are present;
2. all center versions are supported;
3. every upstream result has `execution_authorized: false`;
4. every upstream result has `downstream_gates_required: true`;
5. TOC and PATOC workspace bindings match;
6. TOC and PATOC trajectory bindings match;
7. TOC and PATOC continuation bindings match;
8. RTOC and PATOC relationship bindings match;
9. RTOC and PATOC actor bindings match;
10. TOC, RTOC, and PATOC action digests match;
11. upstream verdicts are composed by normative precedence.

## Verdict mapping

### REJECT

Returned for an unsupported version, upstream authorization-invariant violation, binding mismatch, or any upstream `REJECT` verdict.

### REVALIDATE

Returned when no reject condition exists and any center returns `REVALIDATE`.

### WAIT

Returned when no reject or revalidation condition exists and PATOC returns `WAIT`.

### ABSTAIN

Returned when no stronger condition exists and a center result or required binding is missing, ambiguous, or abstaining.

### COORDINATED_ACTION_CANDIDATE

Returned only for:

```text
TOC   = RESUME
RTOC  = RESUME
PATOC = EXECUTE_CANDIDATE
all bindings agree
all non-authorization invariants hold
```

## Normative precedence

```text
REJECT > REVALIDATE > WAIT > ABSTAIN > COORDINATED_ACTION_CANDIDATE
```

Within one verdict family, stable reason ordering is part of the conformance contract.

## Stable reason codes

### REJECT

- `UPSTREAM_AUTHORIZATION_INVARIANT_VIOLATION`
- `UNSUPPORTED_CENTER_VERSION`
- `WORKSPACE_BINDING_MISMATCH`
- `TRAJECTORY_BINDING_MISMATCH`
- `CONTINUATION_BINDING_MISMATCH`
- `RELATIONSHIP_BINDING_MISMATCH`
- `ACTOR_BINDING_MISMATCH`
- `ACTION_BINDING_MISMATCH`
- `TOC_REJECTED`
- `RTOC_REJECTED`
- `PATOC_REJECTED`

### REVALIDATE

- `TOC_REVALIDATION_REQUIRED`
- `RTOC_REVALIDATION_REQUIRED`
- `PATOC_REVALIDATION_REQUIRED`

### WAIT

- `PATOC_WAIT_REQUIRED`

### ABSTAIN

- `MISSING_CENTER_RESULT`
- `TOC_ABSTAINED`
- `RTOC_ABSTAINED`
- `PATOC_ABSTAINED`

### COORDINATED_ACTION_CANDIDATE

- `TRIAD_ORIENTATION_VALID`

## Examples

### User-agent action

TOC binds the active user task continuation, RTOC binds the active user-to-agent delegation, and PATOC binds the exact tool call. A revoked delegation causes `REJECT` even when TOC and PATOC are otherwise positive.

### Agent-agent action

TOC binds the shared task continuation, RTOC binds an accepted handoff from coordinator to executor, and PATOC binds the exact action assigned to the receiving agent. An actor mismatch causes `REJECT`.

## Downstream boundary

```text
TOC + RTOC + PATOC
        ↓
Orientation Triad
        ↓
coordinated action candidate
        ↓
consent / policy / approval / effect gates
        ↓
execution receipt
        ↓
post-action verification
        ↓
new orientation state
```

Every result MUST preserve:

```json
{
  "execution_authorized": false,
  "downstream_gates_required": true
}
```
