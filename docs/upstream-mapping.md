# LS Upstream Mapping

This document maps real upstream threads and ecosystem failure reports to the LS conformance fixture families and architectural concepts they most closely match.

The purpose is not to claim ownership over those upstream ideas. The purpose is to make LS a compact **translation layer** between different agent ecosystems, so the same structural failure can be recognized even when each project uses different local language.

---

## Mapping table

| Upstream thread / repo | LS fixture / concept | Why it maps |
| --- | --- | --- |
| `openai/codex#28495` | `missed_terminal_event_reconciliation` | External client misses a committed terminal turn event and needs a bounded recovery path via sequence detection + authoritative state pull. |
| `openai/codex#29627` | `pending_approval_not_missing_authority` | Pending manual approval must remain a durable authority state rather than collapsing into “missing approval”. |
| `crewAIInc/crewAI#5888` | `credential_bound_tool_authority` | Tool authority should be bound to a credential / digest / route / phase boundary, with fail-closed enforcement before upstream execution. |
| `crewAIInc/crewAI#6030` | `credential_bound_tool_authority` + `sealed_completeness_tail_drop` | Governance outcomes, argument commitment, credential verification, and positive deny records converge on pre-upstream authority enforcement and explicit completeness of terminal records. |
| `openai/codex` external JSON-RPC client recovery work | `agent_hook_axis_independence` + `missed_terminal_event_reconciliation` | Observation, authority, and durable client state must stay separate; reconnect alone is not correctness. |
| Claude / external memory lifecycle discussions | `durable_memory_not_authority` + `phase_valid_authority` | Recalled memory can be durable and useful while still not being valid spendable authority without revalidation. |
| AutoGen / multi-agent memory provenance discussions | `memory_laundering_reject` + `durable_memory_not_authority` | Repetition, summarization, or re-surfacing must not silently upgrade derived memory into primary provenance or permission. |

---

## Short reading guide

### If the upstream problem is about missed runtime events
Start with:
- [`ls-conformance/missed_terminal_event_reconciliation`](../ls-conformance/missed_terminal_event_reconciliation/README.md)
- [`ls-conformance/agent_hook_axis_independence`](../ls-conformance/README.md)

### If the upstream problem is about memory being treated as permission
Start with:
- [`ls-conformance/durable_memory_not_authority`](../ls-conformance/durable_memory_not_authority/README.md)
- `phase_valid_authority` in [LS Conformance Pack v0.1 #757](https://github.com/safal207/LS/issues/757)

### If the upstream problem is about governance, approval, or tool authority
Start with:
- [`ls-conformance/credential_bound_tool_authority`](../ls-conformance/credential_bound_tool_authority/README.md)
- `pending_approval_not_missing_authority` in [LS Conformance Pack v0.1 #757](https://github.com/safal207/LS/issues/757)

---

## Why this file exists

Without a mapping layer, each ecosystem looks like it is solving a different problem:

- one project says “manual approval timeout bug”;
- another says “missing terminal event reconciliation”;
- another says “credentialed proxy enforcement”;
- another says “memory lifecycle drift”.

LS treats those not as isolated incidents, but as repeated failures of a few deeper boundaries:

- observation vs authority
- memory vs permission
- credential vs receipt
- durable history vs phase-valid spendable state
- live push notifications vs authoritative pull recovery

The mapping table is meant to keep that translation explicit.
