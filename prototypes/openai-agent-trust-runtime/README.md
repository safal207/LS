# LS Agent Trust Runtime v0.1

> **An open-source trust and continuity layer for teams built with the OpenAI Agents SDK.**

OpenAI Agents SDK provides agents, handoffs, tools, sessions, tracing, and human-in-the-loop primitives. This prototype adds a narrow missing contract around them:

```text
who delegated what
→ which agent was allowed to answer
→ what evidence supports the result
→ whether the task was recovered or superseded
→ whether a proposed external effect has explicit human authority
```

It is deliberately small. It is not another general agent framework and it does not execute merges, deployments, payments, messages, or other protected effects.

## Demo flow

```text
Human
  ↓ dispatch receipt
Coordinator Agent
  ↓ dispatch receipt
Developer Agent
  ↓ dispatch receipt
QA Agent
  ↓ dispatch receipt
Safety Reviewer
  ↓ evidence-bound result receipt
Protected effect gate
  ├── no result-bound human approval → BLOCK
  └── explicit approval receipt → ALLOW decision only
```

The live example uses official OpenAI Agents SDK handoffs with typed handoff input. Each handoff also has a parent-side authority allowlist, so validly shaped model output cannot expand its own authority. The trust runtime records an append-only hash-chained ledger alongside the SDK run.

## What v0.1 proves

- every delegation has a deterministic dispatch receipt;
- only the named child agent can submit the terminal result;
- model-requested handoff authority must fit the parent's allowlist;
- a completed result requires evidence references;
- recovery preserves the original task, constraints, and authority scope;
- recovered work supersedes the stale dispatch;
- terminal work cannot be reopened as recovery;
- an effect outside the delegated scope is blocked;
- protected effects require a separate human approval bound to the exact completed result;
- mutation inside the observed ledger sequence is detectable;
- an `ALLOW` decision is still not effect execution.

## Quickstart

```bash
cd prototypes/openai-agent-trust-runtime
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
pytest
ls-agent-trust-demo --dry-run
```

The dry run makes no API calls and prints the full receipt ledger.

## Live OpenAI Agents SDK run

```bash
export OPENAI_API_KEY='...'
ls-agent-trust-demo \
  --goal 'Design a safe fix for a duplicate payment callback and its regression tests.'
```

By default, the final `merge` proposal is blocked because model output is not human authority.

To record an explicit demo approval receipt after the completed result exists:

```bash
ls-agent-trust-demo --approve-merge
```

This changes only the trust decision. **The prototype never calls GitHub merge APIs.**

## Why this is different from tracing alone

Tracing answers: **what happened during the agent run?**

LS receipts additionally answer:

- was this exact child agent authorized to return this task;
- did its requested authority stay inside the parent's explicit grant;
- was the result evidence-bound;
- did recovery preserve the original constraints and authority;
- was the dispatch superseded after a crash or replacement;
- was the requested effect inside the declared authority scope;
- did a human separately approve this exact completed result and effect?

The design complements, rather than replaces, OpenAI Agents SDK tracing.

## Files

```text
src/ls_agent_trust/runtime.py      deterministic trust core
src/ls_agent_trust/openai_demo.py OpenAI Agents SDK integration
tests/test_runtime.py              adversarial contract tests
docs/architecture.md               component and data-flow map
docs/threat-model.md               explicit threats and non-claims
OPENAI_SHOWCASE.md                 short public submission draft
```

## Current boundary

v0.1 is a prototype, not a production authorization system. It has:

- in-memory state;
- one-process execution;
- evidence references rather than evidence-content verification;
- no identity provider or cryptographic human signature;
- no durable queue;
- no external effect adapters;
- no external ledger checkpoint, so a valid suffix truncation cannot be detected.

Those omissions are intentional. The first public question is narrower:

> Can an agent-team handoff remain verifiable, recoverable, and bounded by human authority without making the Agents SDK harder to use?

## Positioning

**OpenAI makes agent teams more capable. LS makes their coordination verifiable, recoverable, and bounded by human authority.**

## References

- OpenAI Agents SDK: <https://openai.github.io/openai-agents-python/>
- Handoffs: <https://openai.github.io/openai-agents-python/handoffs/>
- Tracing: <https://openai.github.io/openai-agents-python/tracing/>
- Sessions: <https://openai.github.io/openai-agents-python/sessions/>

Apache-2.0. Advisory only; no autonomous effect authority.
