# durable_memory_not_authority

## Purpose

Prove that durable memory does not become spendable authority merely because it was recalled.

This fixture family targets agent memory systems, external memory layers, compact/session lifecycle hooks, and multi-agent continuity systems.

## Core invariant

Memory is not permission.

A memory item can remain durable, useful, true enough to explain context, or relevant for continuity while no longer being valid enough to authorize a tool call, publication, promotion, identity update, or continuation.

## Suggested fields

```json
{
  "memory_state": "durable | surfaced | decayed | archived",
  "authority_state": "spendable | advisory_only | expired | requires_revalidation",
  "authority_phase_ref": "string | null",
  "revalidation_required": true,
  "verifier_ref": "string | null"
}
```

## Accept vectors

- durable memory may orient explanation or planning;
- advisory-only memory cannot authorize side effects;
- expired authority blocks execution even when recall confidence is high;
- revalidation upgrades authority only through a separate confirmation event;
- verifier reference identifies the check that converted context into current authority.

## Reject vectors

- high recall confidence is treated as execution permission;
- remembered context silently upgrades into current authority;
- current-run memory write becomes spendable without revalidation;
- changed continuation, policy surface, tool target, or phase reuses old authority;
- derived memory becomes primary provenance through repeated recall.

## Canonical lifecycle

```text
memory durable
  ↓
surfaced as context
  ↓
advisory only
  ↓
requires revalidation
  ↓
new verifier event may create spendable authority
```

## Upstream mapping

- Claude Code external memory lifecycle hooks
- AutoGen / multi-agent memory provenance
- memory laundering and provenance drift
- phase-oriented continuity contracts

## LS issue

Canonical pack: https://github.com/safal207/LS/issues/757
