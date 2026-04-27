# Personal AI Operating Layer

## Core idea

LS can be understood not only as an oversight runtime, but as a **personal AI operating layer**.

That means:

- you can connect different agents and models,
- but their output does not reach you raw,
- it first passes through your own layer of memory, quality, coordination, and review.

The goal is simple:

> do not adapt yourself to every new agent; make agents pass through your own system so they adapt to you.

## What this gives the operator

- one stable center of context across many agents;
- continuity across sessions and tool changes;
- response shaping before low-quality output reaches the user;
- the ability to hold, repair, or escalate weak outputs instead of accepting them as-is;
- better visibility into tension, drift, and structural mismatch through coordination, relational, and harmonic signals.

## Mission

Build a system through which AI passes before it becomes an answer, action, or decision, so it is more aligned, more human, more stable, and more useful in the operator's own logic, rhythm, and quality.

## Vision

Different agents may exist outside the system, but the operator should still have one center.

In LS, that center is a personal layer of:

- memory,
- meaning,
- coordination,
- quality,
- and review.

Instead of letting each new model redefine the workflow, LS turns many agents into one governable environment around the operator.

## Product principles

1. AI should adapt to the operator, not the operator to AI.
2. Raw output is not the product; reviewed and shaped output is.
3. Memory, continuity, and tone matter as much as raw capability.
4. Weak, risky, or misaligned output should be visible before it becomes action.
5. The system should work as a layer above agents, not as one more isolated agent.

## Agent gateway pattern

The product pattern is now live in the runtime:

1. An external agent receives a task.
2. The raw result is routed through LS.
3. LS inspects memory, coherence, coordination, relational risk, and harmonic state.
4. LS chooses one of several modes:
   - `pass_through`
   - `shape_response`
   - `repair_before_send`
   - `hold_or_escalate`
5. The operator receives the improved result together with traces and review context.

Architecture diagrams for the current internal path and the external gateway path live in:

- `docs/personal-agent-gateway-runtime.md`

## Current runtime status

This is no longer only positioning. The runtime now emits and preserves:

- `raw_agent_output` before shaping,
- `final_output` after the personal layer,
- `personal_agent_gateway` with the selected mode and bounded reason,
- gateway metrics for observability,
- gateway traces inside quality, relational episode, and relation memory artifacts.
- a V1 external-agent gateway through the `agent-gateway` CLI and `ExternalAgentGateway` Python API.
- `AgentAdapterKit` and `CodexSelfUseAdapter` so agents can connect through a simpler request/response contract.
- an LRI-inspired `operator_identity_governance` signal that warns when agents may freeze identity, cross authorship boundaries, or write memory without continuity.

The gateway now runs on full context before delivery:

- alignment/playbook support,
- coordination advisory,
- harmonic state,
- relational policy,
- relation-memory evidence for repeated bad patterns.

## Why Harmonic State Model matters

The harmonic layer adds structure on top of raw risk scores.

Instead of only saying "this is fragile", LS can say:

- what kind of tension exists,
- whether the current center is still viable,
- whether the scene needs stabilization, translation, reframing, defense, or repair,
- and what transition should happen next.

That makes the personal layer better at both response shaping and architectural diagnostics.

## Why LRI matters

Living Relational Identity is useful to LS because the system is becoming a layer that agents pass through before they reach the operator.

That creates a new safety question:

> how do we make agents adapt to the operator without turning the operator into a fixed, optimized profile?

LS should use LRI as identity governance, not as a separate runtime to copy wholesale:

- continuity protects the operator from silent profile rewrites;
- authority boundaries prevent agents from deciding for the operator;
- drift warnings show when optimization starts pushing against agency;
- memory consent keeps persistence from becoming capture.

The first runtime version is intentionally small: adapter responses now expose `operator_identity_governance` so integrations can see identity-boundary risk alongside gateway mode.

## Near-term roadmap

The next product steps are:

1. compare raw agent output with post-LS output in more dashboards and review surfaces;
2. package the adapter kit as a plugin/MCP surface for Codex, local tool runners, browser agents, and custom scripts;
3. wire `operator_identity_governance` into operator profile and memory-write approvals;
4. surface gateway mode, harmonic state, and identity-governance mode directly in dashboards and runtime views;
5. collect real operator examples to tune where shaping should stay advisory and where it should become policy.

## Short positioning

LS is a personal AI operating layer that lets agents work in the operator's logic, rhythm, and quality instead of forcing the operator to live inside the defaults of each new model.
