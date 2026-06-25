# credential_bound_tool_authority

## Purpose

Prove that a spendable credential is distinct from an audit receipt, and that constrained tool calls cannot reach upstream execution without a valid credential bound to the exact call.

This fixture family targets governance middleware, MCP proxy/gateway enforcement, tool-call authorization, and runtime policy systems.

## Core invariant

Credential is not receipt.

- credential = spendable enforcement material for this specific call;
- decision / receipt / outcome record = audit and replay evidence;
- constraint evaluation = pre-upstream boundary, not something the application tool should rediscover.

## Required bindings

A valid credential should be bound to at least:

- tool name;
- normalized argument commitment;
- tenant / actor / subject;
- constraint profile;
- decision id;
- authority phase;
- expiry / validity window;
- attestation or verifier reference where applicable.

## Accept vectors

- valid credential + matching tool name, argument commitment, tenant, constraint profile, decision id, and phase reaches the gateway;
- downstream verifier can validate without a proxy round trip;
- allow path records credential reference plus signed decision/outcome evidence;
- deny path emits a positive `GovernanceOutcome`, not absence of response;
- application tool remains unaware of authorization internals.

## Reject vectors

- upstream tool sees an uncredentialed constrained call;
- changed arguments reach upstream under the old credential;
- wrong tenant, wrong profile, stale phase, replayed credential, expired credential, or attestation-unbound credential reaches upstream;
- audit receipt is treated as a spendable credential;
- valid credential for one route, phase, tool, tenant, or argument commitment is reused for another;
- fail-closed denial produces no concrete outcome record.

## Minimal fixture

```text
valid constrained call
  ↓
credential verifies
  ↓
call reaches gateway

same call with one bound field changed
  ↓
credential check fails
  ↓
upstream tool is not reached
  ↓
positive GovernanceOutcome explains the failed binding
```

## Upstream mapping

- crewAI governance middleware
- MCP proxy/gateway authorization
- credential-bound tool authority
- positive deny/fail-closed outcome records

## LS issue

Canonical pack: https://github.com/safal207/LS/issues/757
