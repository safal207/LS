# LS Unified Transition ID Design

_Status: design proposal_

This document proposes a shared `episode_id` / `transition_id` convention across LS runtime artifacts.

## Problem

LS now records related artifacts across many subsystems:

- raw agent output,
- gateway decisions,
- council cycles,
- contribution ledgers,
- receiver resonance,
- relational self updates,
- emotional memory entries,
- emotional continuity updates,
- attachment bond evolution,
- profile-write decisions,
- action evidence gate decisions,
- shared / collective self changes,
- benchmark and trace artifacts.

These artifacts may describe the same real-world event, but without a shared identifier the replay chain becomes weak.

A reviewer should be able to ask:

```text
For this final output, memory write, profile update, held action, or rejected action:
- what raw output caused it?
- which gateway mode was selected?
- what council cycle reviewed it?
- what evidence gate decision was made?
- did it update emotional or attachment state?
- did it touch shared or collective self state?
- what trace proves the transition?
```

A unified ID convention makes that possible.

## Core proposal

Use two related identifiers:

| Identifier | Scope | Meaning |
|---|---|---|
| `episode_id` | Interaction bundle | A coherent user / agent / task episode that may contain multiple transitions |
| `transition_id` | State/output/action event | One attempted or committed governed change |

Recommended format:

```text
episode_id:    ep_<utc_compact>_<short_random>
transition_id: tr_<utc_compact>_<short_random>
```

Example:

```text
ep_20260508T181200Z_8f3a2c
tr_20260508T181205Z_a91e44
```

IDs should be:

- stable once emitted,
- unique enough for local-first operation,
- safe for filenames and logs,
- human-scannable,
- and present in every major artifact.

## Episode vs transition

One episode may contain many transitions.

Example:

```text
episode: external coding agent proposes a change

transition 1: raw output becomes shaped final response
transition 2: agent proposes profile write
transition 3: evidence gate holds profile write
transition 4: council records repair recommendation
transition 5: emotional memory records post-repair tone
```

```text
episode_id = ep_...
  ├─ transition_id = tr_...answer_delivery
  ├─ transition_id = tr_...profile_write_attempt
  ├─ transition_id = tr_...evidence_hold
  ├─ transition_id = tr_...council_repair
  └─ transition_id = tr_...emotional_update
```

## Transition lifecycle

A transition should move through a traceable lifecycle:

```text
proposed
  → inspected
  → governed
  → committed | held | rejected
  → projected into derived memory/state if allowed
```

A minimal transition artifact:

```json
{
  "transition_id": "tr_20260508T181205Z_a91e44",
  "episode_id": "ep_20260508T181200Z_8f3a2c",
  "transition_type": "profile_write_attempt",
  "source": "external_agent_gateway",
  "status": "held",
  "reason": "missing_operator_confirmation",
  "created_at": "2026-05-08T18:12:05Z",
  "actor": "external_agent",
  "operator_required": true,
  "evidence_refs": ["trace:...", "artifact:..."],
  "related_ids": {
    "gateway_decision_id": "...",
    "council_cycle_id": "...",
    "action_evidence_decision_id": "..."
  }
}
```

## Transition types

Initial recommended transition types:

| Type | Meaning |
|---|---|
| `answer_delivery` | Raw output became final output or was held/repaired |
| `memory_write_attempt` | Agent/system attempted to persist memory |
| `profile_write_attempt` | Agent/system attempted to update operator profile |
| `action_attempt` | Agent/system attempted an external action |
| `council_decision` | Council completed a structured decision round |
| `relational_self_update` | RelationalSelf snapshot changed |
| `emotional_memory_update` | EmotionalMemory entry was created |
| `attachment_bond_update` | AttachmentBond evolved |
| `emotional_continuity_update` | Emotional continuity state changed |
| `shared_self_projection` | SharedRelationalSelf was exported or updated |
| `collective_self_merge` | CollectiveRelationalSelf was merged |
| `fellowship_vote` | Fellowship proposal/vote updated collective state |
| `rollback_or_repair` | A previous transition was rolled back or repaired |
| `benchmark_artifact` | Replay/evaluation artifact generated |

## Status values

Recommended status values:

| Status | Meaning |
|---|---|
| `proposed` | Transition was requested but not yet inspected |
| `inspected` | Runtime/gateway/council inspected it |
| `allowed` | Governance allowed it |
| `committed` | State/action/output was actually committed |
| `held` | Transition is paused pending confirmation/evidence |
| `rejected` | Transition is explicitly disallowed |
| `rolled_back` | Transition was reverted |
| `partially_rolled_back` | Transition was partially reverted |
| `superseded` | A later transition replaced it |
| `audit_only` | Recorded for trace but did not affect state |

## Where IDs should appear

### Personal Agent Gateway

```json
{
  "episode_id": "ep_...",
  "transition_id": "tr_...",
  "raw_agent_output": "...",
  "final_output": "...",
  "gateway_mode": "repair_before_send",
  "gateway_reason": "..."
}
```

### Action Evidence Gate

```json
{
  "episode_id": "ep_...",
  "transition_id": "tr_...",
  "decision": "hold",
  "stop_reason": "missing_operator_confirmation",
  "digest": "..."
}
```

### Council cycle

```json
{
  "episode_id": "ep_...",
  "transition_id": "tr_...",
  "cycle_id": "council_...",
  "mode": "self-consistency-check"
}
```

Existing `cycle_id` values should be preserved and linked, not replaced.

### Emotional memory

```json
{
  "episode_id": "ep_...",
  "transition_id": "tr_...",
  "entry_id": "...",
  "emotional_tone": "supportive",
  "trigger_source": "council"
}
```

### Attachment bond

```json
{
  "episode_id": "ep_...",
  "transition_id": "tr_...",
  "bond_strength_before": 0.52,
  "bond_strength_after": 0.57
}
```

### Shared / collective self

```json
{
  "episode_id": "ep_...",
  "transition_id": "tr_...",
  "consent_mode": "selective",
  "provenance_refs": ["member:...", "proposal:..."]
}
```

## Replay query target

After implementation, LS should be able to answer:

```text
show episode ep_20260508T181200Z_8f3a2c
```

Expected output:

```text
Episode ep_...
  1. raw output received from external agent
  2. gateway selected repair_before_send
  3. profile write was proposed
  4. action evidence gate held it: missing_operator_confirmation
  5. council suggested repair wording
  6. emotional memory recorded supportive post-repair context
  7. final output delivered; no profile write committed
```

This is the signature LS behavior:

> not just answer replay, but transition replay.

## Compatibility strategy

Implementation should be additive:

1. If an artifact already has `cycle_id`, keep it.
2. Add optional `episode_id` and `transition_id` fields.
3. On read, tolerate missing IDs.
4. On write, generate IDs if missing.
5. Add migration helpers later only if needed.

## Minimal implementation plan

### Phase A — helper module

Add:

```text
python/modules/shared/transition_ids.py
```

Functions:

```python
def new_episode_id(now: datetime | None = None) -> str: ...
def new_transition_id(now: datetime | None = None) -> str: ...
def ensure_episode_id(payload: dict) -> str: ...
def ensure_transition_id(payload: dict) -> str: ...
```

### Phase B — gateway/evidence first

Add IDs to:

- external agent gateway responses,
- web agent gateway responses,
- action evidence gate decisions,
- profile-write policy decisions.

Why first: this is where output becomes state/action.

### Phase C — council and quality artifacts

Add IDs to:

- council cycle artifacts,
- contribution ledgers,
- receiver resonance artifacts,
- benchmark snapshots.

### Phase D — relational/emotional/attachment state

Add IDs to:

- emotional memory entries,
- emotional arc points,
- attachment arc/audit rows,
- relational self change history,
- emotional continuity updates.

### Phase E — Fellowship/federation

Add IDs to:

- shared self projections,
- fellowship proposals/votes,
- collective self merges,
- Web4/federated events.

## Tests to add

### Unit tests

- generated IDs match allowed format,
- generated IDs are unique across calls,
- helper preserves existing IDs,
- helper adds missing IDs,
- helper is deterministic with injected `now` except random suffix.

### Integration tests

- external gateway response includes `episode_id` and `transition_id`,
- action evidence gate decision includes same IDs when passed through,
- emotional memory update can link to the parent transition,
- held profile write produces replay chain with no committed profile update,
- rollback event links to original transition.

### Safety tests

- emotional/attachment updates with the same transition id do not authorize action,
- missing evidence still holds even if relational/emotional state is positive,
- shared self update requires consent even with high fellowship reputation.

## Recommendation

Use this rule:

> `episode_id` is created at the boundary where LS receives a user/external-agent
> task. `transition_id` is created whenever something tries to become output,
> memory, profile state, shared state, or action.

This keeps the design simple:

- one episode = one interaction bundle,
- one transition = one attempted or committed change.

## Why this matters

Without unified transition IDs, LS can still work.

With unified transition IDs, LS becomes much more legible as an oversight and
living-cognition runtime:

- reviewers can replay not only answers, but state transitions,
- emotional memory can be tied to actual events,
- governance decisions become audit-linked,
- action/memory/profile writes become accountable,
- Fellowship and shared-self changes preserve provenance,
- benchmark cases can prove process validity, not only output quality.

The core LS claim becomes testable:

> LS remembers not only facts, but governed transitions.
