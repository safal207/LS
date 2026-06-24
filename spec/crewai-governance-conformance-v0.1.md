# CrewAI Governance Conformance Profile v0.1

Status: Draft interoperability profile

## Purpose

This profile maps LS safe-continuation outcomes to the vendor-neutral `GovernanceDecision` contract proposed in CrewAI PR #6030.

The goal is not to make CrewAI depend on LS. The goal is to provide small, framework-neutral fixtures that any implementation can consume as contract tests.

## Required continuation bindings

A resumable governance decision SHOULD bind at least:

- `intent_digest` — digest of the exact intended action;
- `target_state_digest` — digest of the authoritative state against which the decision was issued;
- `continuation_id` — stable identifier for the paused/resumed execution;
- `approval_id` or equivalent authorization identity when approval is required.

`params_hash` is useful but does not replace these bindings. Two calls can have identical parameters while belonging to different intents, target states, approvals, or continuations.

## Outcome mapping

| LS outcome | CrewAI PR #6030 decision | Mapping status |
|---|---|---|
| `RESUME` | `allow` | exact |
| `REVALIDATE` | `revise` | exact |
| `REJECT` | `deny` | exact |
| `ABSTAIN` | no equivalent | unrepresentable |

### Why `require_approval` is not a generic `ABSTAIN`

`require_approval` states that human approval is the missing condition. `ABSTAIN` states that the system lacks sufficient authoritative evidence to decide. Missing causal dependencies, unavailable current state, or an unverifiable continuation may not be repairable by human approval alone.

A framework that needs lossless mapping SHOULD add a neutral `defer` decision, meaning:

> Do not execute. The decision is unresolved until named evidence or state becomes available. No approval is implied.

## Mandatory fixtures

1. `resume_same_intent` — all continuation bindings match; expected `RESUME` / `allow`.
2. `target_state_drift` — authoritative target state changed; expected `REVALIDATE` / `revise`.
3. `superseded_approval` — checkpoint approval is no longer current; expected `REJECT` / `deny`.
4. `incomplete_dependency_chain` — a required causal dependency is unavailable; expected `ABSTAIN`; current CrewAI mapping is unrepresentable and the recommended decision is `defer`.

## Conformance requirements

An implementation claiming support for this profile MUST:

- preserve the three required continuation bindings without mutation;
- compare checkpoint bindings with current authoritative state before execution;
- reject superseded authorization;
- avoid converting missing evidence into implicit permission;
- report lossy or unrepresentable mappings explicitly;
- never map `ABSTAIN` to `allow`.

## Scope

This is a vendor-neutral conformance draft, not a CrewAI standard. CrewAI may adopt the fixtures directly, adapt them to its own test layout, or use them as external interoperability vectors.
