# Verified Transition Loop (VTL) v0.1

VTL treats the **verified state transition**, not the agent, as the primary unit of execution.

```text
Intent
  -> Transition Proposal
  -> Evidence Gate
  -> AUTHORIZE | HOLD | BLOCK
  -> external executor
  -> Observed Outcome
  -> invariant verification
  -> COMMIT | RETRY | ROLLBACK | ESCALATE
```

## Core invariant

**The verifier cannot be the executor of the transition it verifies.**

VTL does not grant authority, deploy software, merge code, change IAM, or perform payments. It produces deterministic receipts that a separately authorized executor may consume.

## v0.1 evidence gate

A transition is eligible for `AUTHORIZE` only when all required evidence is explicit and current:

- mission is aligned;
- exact source/artifact is bound;
- required tests passed;
- approval is current and unexpired;
- at least one evidence reference is retained;
- verifier and executor identities are distinct.

Missing evidence yields `HOLD`. Contradictory, failed, expired, or mismatched evidence yields `BLOCK`.

## Post-action verification

The observed outcome is recorded separately from the pre-action authorization decision. Expected invariants are checked against the observed post-state:

- all expected invariants hold and state matches -> `COMMIT`;
- failed invariant with rollback path -> `ROLLBACK`;
- failed invariant with retry-only path -> `RETRY`;
- missing evidence, binding mismatch, or no safe recovery path -> `ESCALATE`.

## Deterministic evidence

Receipts and the append-only evidence ledger use canonical JSON plus SHA-256. The ledger is tamper-evident and can be replay-verified.

## Development

```bash
python -m pip install -e '.[dev]'
pytest
```

## First integration target

The first product-shaped adapter should sit immediately before a software deployment boundary:

```text
AI coding agent proposes deploy(commit X)
-> VTL checks mission + exact commit + tests + approval
-> authorized executor performs deploy
-> independent observer supplies health/artifact evidence
-> VTL commits or requests rollback
```

The demo remains side-effect-free until a separately reviewed executor adapter is introduced.
