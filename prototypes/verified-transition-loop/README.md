# Verified Transition Loop (VTL) v0.2

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

VTL does not grant authority, deploy software, merge code, change IAM, send messages, or perform payments. It produces deterministic receipts that a separately authorized executor may consume.

## v0.2 authorization binding

An authorization receipt now binds:

- the transition ID and intent ID;
- the exact transition proposal digest;
- the evidence digest;
- verifier and executor identities;
- the final authorization verdict.

Post-action verification accepts an observed outcome through `verify_authorized_outcome()` only when the authorization receipt is intact, is `AUTHORIZE`, and still binds the exact proposal being verified.

This closes the v0.1 gap where a post-action verdict could be evaluated without carrying the exact pre-action authorization receipt forward.

## Evidence gate

A transition is eligible for `AUTHORIZE` only when all required evidence is explicit and current:

- mission is aligned;
- exact source/artifact is bound;
- required tests passed;
- approval is current and unexpired;
- at least one evidence reference is retained;
- verifier and executor identities are distinct.

Missing evidence yields `HOLD`. Contradictory, failed, expired, or mismatched evidence yields `BLOCK`.

## Post-action verification

Expected invariants are checked against the independently observed post-state:

- all expected invariants hold and state matches -> `COMMIT`;
- failed invariant with rollback path -> `ROLLBACK`;
- failed invariant with retry-only path -> `RETRY`;
- missing evidence, binding mismatch, invalid authorization, or no safe recovery path -> `ESCALATE`.

The observed outcome is stored separately from the pre-action authorization decision.

## Deployment Transition Demo

v0.2 adds a deterministic, **side-effect-free** deployment demo:

```text
AI coding agent
  -> proposes deploy(candidate commit)
  -> exact commit + tests + approval are checked
  -> AUTHORIZE
  -> simulated deployment
  -> independent observer checks commit/artifact/health
```

Healthy path:

```text
AUTHORIZE -> simulated deploy -> health_ok -> COMMIT
```

Failure/recovery path:

```text
AUTHORIZE
  -> simulated deploy
  -> health invariant fails
  -> ROLLBACK
  -> rollback becomes a new evidence-gated transition
  -> simulated restore of last verified commit
  -> independent recovery verification
  -> COMMIT
```

The rollback is intentionally modeled as a **second verified transition**, rather than treating `ROLLBACK` as magic authority to mutate state.

Run it:

```bash
python -m pip install -e .
vtl-deployment-demo
```

The CLI prints only deterministic decision/final-state metadata and states explicitly that no side effect was performed.

## Deterministic evidence

Receipts and the append-only evidence ledger use canonical JSON plus SHA-256. The demo records intent, proposal, authorization, observed outcome, recovery intent, recovery authorization, and recovery outcome into one replay-verifiable chain.

## Development

```bash
python -m pip install -e '.[dev]'
pytest
```

## Current boundary

v0.2 is a reference transition protocol and simulation oracle. It has no production deployment adapter, credential, GitHub write capability, cloud API, IAM capability, payment capability, or automatic merge path.

A future real executor must remain separately authorized and independently reviewed.
