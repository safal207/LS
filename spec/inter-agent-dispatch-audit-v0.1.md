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

- The initial dispatch explicitly declares `parent_dispatch_id: null`.
- The initial operation is `spawn_agent`.
- Every follow-up references a strictly earlier dispatch in the same sender/recipient chain.
- Dispatch sequence numbers are contiguous and deterministic.
- Dispatch and result timestamps use the dependency-free v0.1 RFC3339 profile and a known UTC offset.
- The profile accepts `Z`, lowercase `z`, and `+00:00` as known UTC forms.
- The profile rejects non-zero offsets for audit-record semantics and rejects unknown `-00:00` offsets.
- Leap-second `:60` forms are rejected fail-closed unless a future version introduces a maintained trusted leap-second authority.
- Content and result digests use the full `sha256:` plus 64 lowercase hexadecimal format.
- The exact authorized content matches its stored digest.
- The complete fixture is validated against the checked-in Draft 2020-12 schema.
- A model-generated summary cannot replace mechanically dispatched exact content.
- UI visibility alone is insufficient; at least one supported machine-readable audit surface must exist.
- A completed result binds the complete effective dispatch sequence in order.

## Required negative vectors

All fourteen v0.1 vectors are normative conformance requirements. Each case is bound to one exact error contract in both the checked-in Draft 2020-12 schema and the runtime validator.

| Case | Required error code |
| --- | --- |
| `missing_authorized_exact_content` | `AUTHORIZED_EXACT_CONTENT_MISSING` |
| `ui_only_without_machine_readable_audit` | `AUDIT_SURFACE_MISSING` |
| `missing_followup_parent_link` | `PARENT_DISPATCH_MISSING` |
| `ambiguous_followup_order` | `DISPATCH_SEQUENCE_INVALID` |
| `result_omits_effective_followup` | `RESULT_DISPATCH_BINDING_INCOMPLETE` |
| `authorized_content_changed_without_digest_update` | `CONTENT_DIGEST_MISMATCH` |
| `missing_root_parent_key` | `ROOT_PARENT_MISSING` |
| `self_parent_followup` | `PARENT_DISPATCH_MISSING` |
| `invalid_root_operation` | `ROOT_OPERATION_INVALID` |
| `invalid_dispatch_timestamp` | `TIMESTAMP_INVALID` |
| `invalid_leap_second_timestamp` | `TIMESTAMP_INVALID` |
| `malformed_result_digest` | `RESULT_DIGEST_INVALID` |
| `missing_required_result_id` | `SCHEMA_VALIDATION_FAILED` |
| `malformed_content_digest` | `CONTENT_DIGEST_INVALID` |

Removing any required case, reassigning its expected error code, or keeping the name while substituting an unrelated mutation is non-conformant. Future versions may add cases, but v0.1 consumers must enforce this complete fourteen-case set.

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

The validator remains dependency-free. It enforces the JSON Schema keyword subset used by this artifact, validates semantic and causal invariants, applies every declared negative mutation, and requires the exact expected error code to be observed for every required vector.
