# Threat model

## Protected properties

The prototype aims to preserve five narrow properties:

1. **delegation integrity** — a result is bound to the exact task and named child agent;
2. **evidence presence** — completed work cannot be recorded without an evidence reference;
3. **recovery freshness** — a superseded worker cannot submit late terminal work or gain wider authority;
4. **authority separation** — model output is not permission to perform a protected effect;
5. **ledger integrity** — mutation of the observed local event sequence is detectable.

## Threats covered in v0.1

| Threat | Control |
|---|---|
| A different agent claims another agent's task | Child-agent identity check on result submission |
| Agent returns `COMPLETED` with no support | Evidence-reference requirement |
| Model requests more handoff authority than its parent grants | Parent-side allowlist; out-of-grant authority fails closed |
| Crashed agent responds after replacement | Supersession lineage; old dispatch becomes stale |
| Recovery weakens constraints or expands authority | Replacement must preserve task, constraints, and authority scope |
| A completed task is reopened as recovery | Terminal dispatches cannot be superseded |
| Agent recommends an undelegated effect | Authority-scope check |
| Human approval is recorded before evidence exists | Approval requires an exact completed result receipt |
| Approval for one result is reused with another | Approval is bound to dispatch, result receipt, and effect |
| Agent recommends merge/deploy/payment and treats that as permission | Separate human approval receipt |
| Result receipt from another task is replayed | Exact dispatch/result binding |
| Ledger event is edited or reordered | Offset and SHA-256 hash chain |
| Same dispatch returns multiple terminal answers | One terminal result per dispatch |

## Threats not yet covered

### Forged agent identity

Agent names are application labels. v0.1 does not cryptographically attest a process, model, container, or service identity.

### Forged human approval

The approver is a string label. A production implementation requires authentication and signed approval claims with expiry and revocation.

### Malicious evidence content

Evidence references are strings. The runtime checks presence and binding, not whether the referenced artifact is true, complete, malware-free, or produced by the claimed tool.

### Host compromise

An attacker controlling the Python process can alter memory before records are emitted. The hash chain detects later mutation, not malicious creation at source.

### Ledger suffix truncation

Without an externally stored final hash or signed checkpoint, a valid prefix of the ledger still verifies. v0.1 therefore cannot prove that the observed ledger includes the latest emitted record.

### Durable distributed execution

The in-memory registry is not a database, consensus system, or exactly-once queue. Process loss discards state.

### Model prompt injection

Typed handoff input and authority allowlists narrow metadata shape and scope but do not solve prompt injection in source documents or tool outputs. Tool guardrails and content isolation remain necessary.

### External effect race

The runtime returns a decision but has no transactional link to an effect adapter. Production code must bind approval, idempotency key, effect request, and execution receipt in one durable protocol.

## Safety stance

The prototype fails closed for unknown dispatches, stale dispatches, mismatched results, missing evidence, handoff authority escalation, recovery authority changes, out-of-scope effects, premature approval, and missing human approval.

It does not claim that every safe-looking result is correct. It only prevents several unsafe state transitions from being represented as authorised success.
