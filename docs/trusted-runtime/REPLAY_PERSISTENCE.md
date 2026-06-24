# Trusted Runtime replay and event persistence

Status: reference implementation for issue #597.

This layer makes a Trusted Runtime workflow inspectable after a process exits or a session is interrupted.

```text
Cognitive Trail
-> append-only durable events
-> integrity scan
-> deterministic LTP replay
-> ADMISSIBLE / DRIFTED / REJECTED
-> conformance report
-> resume checkpoint
```

## Boundaries

LS decides which workflow events belong to the continuous task history.

The event store owns append-only persistence, sequence numbers, hash chaining, and retrieval. It does not decide whether a path is acceptable.

LiminalDB is represented by a feature-flagged injected-client adapter. It is a storage boundary, not an orchestrator or policy engine.

LTP owns deterministic inspection and conformance reporting. It never routes a model, invokes a tool, regenerates an answer, or repeats a side effect.

## Durable events

Every event contains task, trail, actor, parent, sequence, payload digest, previous hash, event hash, and an immutable reference:

```text
event_ref = liminal-event:sha256:<event_hash>
```

The local adapter writes canonical JSONL and flushes each append with `fsync`. Re-appending the same event ID and content is idempotent. Reusing the ID with different content fails closed.

The scanner detects broken hashes, reordered sequences, task mismatch, missing parents, and malformed JSON. A damaged tail exposes only the last valid durable prefix and an explicit finding.

## Replay decisions

- `ADMISSIBLE`: the durable path is ordered, terminal, and internally consistent.
- `DRIFTED`: the path is valid but incomplete or differs from a supplied baseline.
- `REJECTED`: integrity, ordering, authorization, or lifecycle invariants fail.

A resume checkpoint records the last valid event, its immutable reference, the next expected stage when known, and whether a damaged tail was observed. It is continuity evidence, not permission to repeat an earlier action.

## Evidence export

The reference exporter creates:

```text
trace.jsonl
replay-record.json
conformance-report.json
resume-checkpoint.json
README.md
```

The bundle is generated from durable events only and can be inspected offline.

## Privacy and retention

Configured sensitive fields are replaced before persistence by a redaction marker plus a digest of the removed value. The complete normalized event also retains an integrity digest. Raw private values are not included in the replay bundle.

A digest is integrity evidence, not anonymization. Production deployments still need tenant isolation, access control, encryption, retention periods, erasure procedures, backup policy, and export auditing.

The local reference does not automatically delete historical events. An append-only history does not imply permanent retention: a production store may preserve continuity metadata while deleting or cryptographically erasing protected payload material according to its policy.

## Production boundary

The reference implementation proves local JSONL persistence, hash-chain validation, redacted replay artifacts, stable classification, and recovery from the last valid prefix.

Distributed production use additionally requires transactional append semantics, concurrent-writer fencing, authenticated reads, encryption and key rotation, replication, disaster recovery, retention enforcement, and versioned replay-policy migrations.

## Validation

```bash
python -m pip install jsonschema pytest
PYTHONPATH=.:python:python/modules \
  python -m pytest python/tests/test_trusted_runtime_*.py
```
