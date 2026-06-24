# Replay and Event Persistence v0.1

Status: **local deterministic LS reference contract**  
Implementation issue: [#597](https://github.com/safal207/LS/issues/597)  
Epic: [#599](https://github.com/safal207/LS/issues/599)

## Purpose

This layer turns a completed or partial Trusted Action Pipeline into a durable, inspectable event stream that can be replayed without rerunning models, tools, or protected effects.

```text
Trusted Action Pipeline events
  -> append-only JSONL store
  -> integrity scan
  -> deterministic replay
  -> ADMISSIBLE | DRIFTED | REJECTED
  -> conformance report
  -> optional resume checkpoint
```

## Responsibility boundary

LS owns event interpretation, continuity, replay classification, checkpoint creation, and reusable artifacts.

An LTP-style adapter may inspect execution paths. A LiminalDB-style adapter may persist events. This contract does not claim implementation, adoption, or endorsement by either external system.

Storage never grants authorization and replay never repeats execution.

## Durable event

Each persisted event binds:

- trail ID;
- stable event ID;
- contiguous sequence number;
- event type and timestamp;
- parent event ID;
- original source-payload digest;
- redacted payload and redacted-payload digest;
- previous event digest;
- current event digest.

The event stream is a per-trail SHA-256 chain.

## Append semantics

### New event

A new event is redacted, hashed, appended to JSONL, flushed, and fsynced.

### Identical duplicate

Re-appending the same event ID with the same event type, timestamp, and source-payload digest is idempotent. No second line is written.

### Conflicting duplicate

Reusing an event ID for different event bytes fails closed with `EVENT_ID_CONFLICT`. The existing stream remains unchanged.

## Privacy and redaction

Sensitive keys are recursively replaced by:

```text
[REDACTED]
```

The v0.1 fixture policy covers:

- credentials;
- private task content;
- prompts;
- raw model output;
- payment data;
- secrets;
- tokens.

The redacted payload remains verifiable through its own digest. The original unredacted source payload is not persisted; only its SHA-256 digest is retained as an integrity reference.

## Integrity scan

Before semantic replay, LS verifies:

1. valid JSON objects;
2. supported event schema version;
3. trail binding;
4. contiguous sequence;
5. previous-event hash binding;
6. parent-event binding;
7. event digest;
8. redacted payload digest.

Any reordered, malformed, tampered, or hash-broken stream is rejected.

A corrupted tail still exposes the last valid durable prefix for inspection, but the overall replay classification remains `REJECTED` and automatic resume is forbidden.

## Replay classifications

### `ADMISSIBLE`

The durable path is intact and semantically valid.

A terminal path returns:

```json
{
  "classification": "ADMISSIBLE",
  "completion_state": "COMPLETE",
  "resume_allowed": false
}
```

A valid partial prefix returns:

```json
{
  "classification": "ADMISSIBLE",
  "completion_state": "PARTIAL",
  "resume_allowed": true
}
```

with a deterministic checkpoint pointing to the next expected stage.

### `DRIFTED`

The stream is internally valid, but one or more source-payload digests differ from the supplied replay baseline. Replay reports the drift without rerunning the workflow.

### `REJECTED`

Used for integrity failures, append conflicts, invalid stage order, or semantically impossible paths such as authorization or execution after a non-ALLOW decision.

## Canonical stage order

```text
TASK_ACCEPTED
ORIENTATION_COORDINATED
RECOGNITION_ALLOWED
EVIDENCE_ALLOWED
AUTHORIZATION_VERIFIED
EXECUTION_COMMITTED
EXECUTION_COMPLETED
ARTIFACT_EXPORTED
```

A prefix of this order may be resumable. A permutation is not.

## Resume checkpoint

A checkpoint binds:

- trail ID;
- last valid event ID and sequence;
- next expected stage;
- valid-prefix chain head;
- whether automatic resume is allowed;
- deterministic checkpoint reference.

Only an integrity-valid partial path may set `resume_allowed: true`.

## Conformance report

The report records:

- classification and stable reason code;
- completion state;
- integrity result and valid-prefix length;
- chain head;
- checkpoint reference;
- append outcome;
- persisted-event and redaction counts;
- privacy status;
- explicit zero model, tool, and effect calls;
- deterministic report reference.

## Frozen conformance vectors

1. clean complete replay → `ADMISSIBLE`;
2. changed baseline → `DRIFTED`;
3. execution after evidence `BLOCK` → `REJECTED`;
4. valid partial prefix → resumable checkpoint;
5. reordered stream → `REJECTED`;
6. post-persistence event mutation → `REJECTED`;
7. corrupted tail → `REJECTED` with valid-prefix evidence;
8. recursive sensitive-field redaction;
9. identical duplicate append → idempotent;
10. conflicting duplicate event ID → `REJECTED`.

## Security invariants

1. Replay never calls a model.
2. Replay never calls a tool.
3. Replay never invokes a protected effect.
4. Replay does not grant execution authority.
5. Corrupted streams cannot become admissible.
6. A non-ALLOW event cannot be followed by authorization or execution.
7. Raw sensitive fixture values cannot enter persisted or exported replay evidence.
8. Conflicting event IDs fail closed.
9. Only an integrity-valid partial prefix may resume automatically.

## Production boundary

The reference implementation proves local JSONL append, fsync-backed persistence, deterministic hash-chain validation, privacy redaction, classification, and resume from a valid prefix.

Distributed production use additionally requires:

- transactional append or compare-and-set semantics;
- concurrent-writer fencing;
- authenticated tenant-scoped reads;
- encryption at rest and in transit;
- enforced retention, erasure, backup, and disaster-recovery policies;
- replay-policy and schema migrations;
- operational monitoring of partial and rejected streams.

This contract does not claim distributed transactional storage or universal recovery guarantees.

## Relationship to draft PR #622

Draft PR #622 contains valuable earlier LTP/LiminalDB design evidence but is a conflict-blocked 128-commit stack. This contract rebuilds only replay and append-only persistence on modern `main` after the Commit-Before-Effect contract merged in PR #691.

## Conformance

Run:

```bash
python tools/validate_replay_persistence_v0_1.py
```

The machine-readable result is written to:

```text
artifacts/replay-persistence-v0.1-result.json
```
