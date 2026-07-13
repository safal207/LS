# Inter-Agent Dispatch Audit v0.1

## Purpose

Define a small vendor-neutral conformance boundary for encrypted multi-agent runtimes where an authorized operator must be able to reconstruct the exact parent-to-subagent instruction chain without restoring unconditional plaintext rollout storage.

This artifact is architecture and test feedback only. It does not claim Codex adoption or prescribe an internal implementation.

## Contract boundary

The following surfaces are independent:

```text
streaming observability
!= lifecycle interception
!= inter-agent causal audit
```

A runtime can stream agent output and expose lifecycle hooks while still failing to preserve the exact input that caused a subagent result.

The security and audit requirements are also independent:

```text
confidentiality at rest
!= authorized operator observability
!= causal audit completeness
```

Encrypted or redacted default storage is compatible with an explicit, access-controlled audit surface.

## Canonical record

The fixture models:

1. one root-to-child `spawn_agent` instruction;
2. one later `followup_task` message;
3. one completed child result;
4. encrypted payload storage;
5. an authorized exact-content view;
6. a machine-readable JSON audit surface;
7. a result bound to the complete ordered dispatch sequence.

Every dispatch carries:

- a stable dispatch identifier;
- operation type;
- sender and recipient thread identifiers;
- sequence and timestamp;
- parent dispatch linkage;
- encrypted storage mode;
- a digest of the exact content;
- an authorized exact-content view.

## Required invariants

- The initial dispatch has no parent.
- Every follow-up references an earlier dispatch in the same sender/recipient chain.
- Dispatch sequence numbers are contiguous and deterministic.
- The exact authorized content matches its stored digest.
- A model-generated summary cannot replace mechanically dispatched exact content.
- UI visibility alone is insufficient; at least one supported machine-readable audit surface must exist.
- A completed result binds the complete effective dispatch sequence in order.

## Negative vectors

The v0.1 fixture must reject:

- missing authorized exact content;
- UI-only visibility without a machine-readable audit surface;
- missing follow-up parent linkage;
- ambiguous or duplicated dispatch ordering;
- a result that omits an effective follow-up;
- exact content changed without a corresponding digest update.

## Files

- `fixtures/operational-continuity/inter-agent-dispatch-audit/dispatch_chain_v0.1.json`
- `fixtures/operational-continuity/inter-agent-dispatch-audit/schema-v0.1.json`
- `tools/validate_inter_agent_dispatch_audit_v0_1.py`

## Validation

Run:

```bash
python tools/validate_inter_agent_dispatch_audit_v0_1.py \
  fixtures/operational-continuity/inter-agent-dispatch-audit/dispatch_chain_v0.1.json \
  fixtures/operational-continuity/inter-agent-dispatch-audit/schema-v0.1.json
```

The validator is dependency-free. It validates the canonical record, applies every declared negative mutation, and requires the expected error code to be observed for each vector.
