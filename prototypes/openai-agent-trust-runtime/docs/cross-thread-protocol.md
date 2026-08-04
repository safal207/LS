# CrossThread Protocol v0.1

## Purpose

CrossThread Protocol adds a typed trust layer on top of existing cross-thread transport. It is designed for durable AI-agent sessions that can list, read, send, fork, resume, and archive peer threads.

The central distinction is:

```text
message delivered
!= statement verified
!= state accepted
!= action authorized
!= action executed
```

## Objects

### `CrossThreadEvent`

A typed message with:

- stable event, trajectory, continuation, source, and target identity;
- an explicit event type and subject;
- structured payload;
- evidence references and a verification claim;
- an authority declaration;
- monotonic sequence and optional supersession link.

### `CapabilityGrant`

A receiver-side grant that constrains:

- source and target thread pair;
- allowed event types;
- maximum authority;
- audit-read access;
- target consent;
- expiration and revocation.

### `DecisionReceipt`

The receiver records one deterministic disposition:

- `ACCEPTED`;
- `DEFERRED`;
- `REJECTED`.

The receipt includes the reason, evidence verdicts, and accepted state version.

### `EvidenceChecker`

Evidence is not trusted because a sender labels it verified. The receiver must use an explicit checker. The bundled `InMemoryEvidenceStore` is only a deterministic demo and test fixture.

## Receiver pipeline

```text
receive
-> verify registered source and target identity
-> verify active capability and target consent
-> cap declared authority
-> inspect verification status and evidence
-> reject stale or conflicting state
-> accept / defer / reject
-> record disposition in a hash-chained audit
-> send any proposed action through normal local approval and sandbox policy
```

## State rules

`STATE_UPDATE`, `RESULT`, and `COMPLETION` are state-bearing. They require:

- `verification_status = VERIFIED`;
- at least one evidence reference;
- a configured checker;
- all evidence verdicts passing;
- a sequence newer than the current accepted state.

Questions, observations, and proposals may be accepted as advisory input without becoming verified shared state.

## Authority rules

An event can declare three independent capabilities:

- `may_inform`;
- `may_request_action`;
- `may_authorize_execution`.

The declaration must be a subset of the receiver-issued capability grant. The reference runtime never performs an external effect. Even an accepted action request is recorded as a request for local policy evaluation only.

## Audit boundary

The local audit is append-only and hash-chained. It detects mutation, insertion, and reordering within the observed sequence. It cannot detect valid suffix truncation without an external checkpoint.

## Security non-claims

v0.1 does not provide:

- cryptographic agent or human identity;
- transport authentication or confidentiality;
- evidence truth beyond the configured checker;
- distributed consensus;
- exactly-once external effects;
- transactional binding between a decision and a real effect adapter;
- prompt-injection prevention;
- host compromise resistance.

## Relationship to Codex issue #36843

This implementation is the executable reference fixture proposed in `openai/codex#36843`. It is intentionally separate from basic cross-thread messaging and can be adapted to other agent frameworks.
