# OpenAI Showcase draft

## Project name

LS Agent Trust Runtime

## One-line description

An open-source trust and continuity layer that makes OpenAI Agents SDK handoffs evidence-bound, recoverable, and explicitly separated from human authority.

## What we built

We built a minimal four-role software-change workflow using OpenAI Agents SDK:

```text
Coordinator → Developer → QA → Safety Reviewer
```

Every typed handoff creates a deterministic dispatch receipt recording the parent, child, exact task, constraints, and proposed authority scope. A completed result can only come from the named child and must include evidence references. If an agent is replaced after interruption, the replacement must preserve the original task, constraints, and authority scope; the old dispatch is superseded and late work is rejected.

The demo also separates recommendation from authority. A Safety Reviewer may recommend `merge`, but the protected-effect gate blocks it until a separate human approval receipt is recorded against that exact completed result. Pre-approval is rejected. Even after approval, the prototype emits only an `ALLOW` decision and never executes a merge.

An append-only SHA-256 hash chain makes mutation within the observed local ledger sequence detectable. The prototype explicitly does not claim suffix-truncation detection without an external checkpoint. Adversarial tests cover agent substitution, evidence-free completion, stale recovery output, recovery scope escalation, premature approval, missing approval, and record mutation.

## Why it matters

OpenAI Agents SDK already provides excellent orchestration, handoffs, sessions, tracing, and human-in-the-loop primitives. LS explores a complementary contract for long-running teams:

> Can we prove who delegated what, preserve constraints and freshness across recovery, and keep model conclusions separate from spendable human authority?

## Built with

- OpenAI Agents SDK typed handoffs
- Python 3.11
- Pydantic
- pytest

## Suggested Agents SDK Discussion title

**Show and tell: evidence-bound handoffs, recovery lineage, and human authority gates**

## Discussion opening

We built a small Apache-2.0 prototype around the OpenAI Agents SDK rather than another orchestration framework. Typed handoff callbacks emit deterministic LS dispatch receipts. Terminal results are bound to the named child and require evidence. Recovery preserves constraints and authority while superseding stale work. Protected effects such as merge and deploy require a separate human approval receipt bound to the exact completed result, while the SDK remains responsible for agent execution and tracing.

We would value feedback on three questions:

1. Is a custom trace processor the best place to correlate SDK trace/span IDs with external dispatch receipts?
2. Which extension point best represents a resumable handoff whose predecessor must become stale?
3. Would a small vendor-neutral receipt schema be useful to the SDK ecosystem, or should this remain application-level policy?
