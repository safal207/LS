# Session Continuity Repair Layer

## Thesis

When context breaks, agents hallucinate.

When relational context breaks, humans hallucinate meaning.

LS should restore the last shared orientation point before continuing.

Core line:

> A system becomes safer when it can detect rupture, return to the last shared orientation point, and continue through repair instead of hallucinated continuity.

## Problem

A session is not just a message exchange. It is a temporary shared world:

```text
what are we doing?
where did we stop?
what kind of session is this?
what did each side understand?
what is still unresolved?
what should not be silently inferred?
```

If the session breaks and the system continues anyway, the missing context is filled by prediction.

For agents, this becomes task hallucination:

```text
missing PR
-> invented change set
-> wrong next step
```

For humans, this becomes relational hallucination:

```text
missing emotional context
-> inferred rejection or blame
-> defensive reaction
```

The problem is not only a bad answer. The problem is false continuity.

## Definition

The Session Continuity Repair Layer is an LS runtime layer that detects when a session loses shared orientation and forces a repair step before continuation.

It tracks:

- expected session type;
- actual response type;
- last shared point;
- missing context;
- inferred continuity;
- rupture type;
- hallucination risk;
- repair prompt;
- next safe action;
- governance decision.

## Position inside LS

```text
Claude / Codex / external agent / human message
-> LS gateway
-> continuity check
-> rupture / hallucination-risk detection
-> repair decision
-> final output or hold
-> optional Personal Cognitive Garden proposal
-> human review before durable memory
```

This layer does not replace Claude, Codex, or any other model.

It creates a portable, reviewable, local-first contract around continuity and repair.

## Core concepts

### Last shared point

The most recent point that both the human and the system can safely treat as shared context.

Examples:

```text
The user asked to continue after PR review, but the PR itself was not provided.
The user asked for emotional support, but the system moved into problem-solving.
The agent proposed a repo action without evidence of the current branch or diff.
```

### Session rupture

A rupture occurs when the system no longer has enough context to continue safely, or when the response type no longer matches the expected session type.

Example rupture types:

```text
missing_pr_context
session_type_mismatch
unanswered_signal
emotional_misread
identity_boundary_confusion
premature_solution
missing_acknowledgement
unverified_inference
abrupt_topic_shift
task_jump_without_anchor
```

### Relational hallucination

A relational hallucination is a meaning inferred from missing context and old pattern pressure rather than evidence.

Human example:

```text
Fact: no reply for two hours.
Missing context: why.
Inferred story: they do not care.
Reaction: anger / withdrawal / panic.
```

Agent example:

```text
Fact: user said “continue”.
Missing context: previous PR/diff not available.
Inferred story: the agent assumes the next task.
Reaction: edits wrong files or invents state.
```

## Runtime decisions

| Decision | Meaning |
|---|---|
| `continue` | Shared context is sufficient. Continue normally. |
| `validate_context` | Context is probably enough, but expose assumptions or ask one confirming question. |
| `repair_before_continue` | A rupture is detected; restore orientation before continuing. |
| `hold_until_context` | Required artifact/context is missing; do not continue. |
| `human_review` | The rupture affects identity, relationships, safety, money, employment, or durable memory. |

## Repair prompts

Repair prompts should not shame the user or agent. They should restore orientation.

Examples:

```text
I may have lost the shared context. What was the last valid point we agreed on?
```

```text
I should not continue from an inferred PR state. Please attach the PR or restate the exact change set.
```

```text
I think I moved into problem-solving while you needed support. Do you want presence, analysis, or next steps?
```

```text
Before I act, I need to separate facts from inferred meaning.
```

## Codex / Claude co-work use case

Codex and Claude can already ask for missing context. That is useful, but it is still model behavior.

LS should make it a runtime artifact:

```text
model says: “I need the PR”
LS records: missing_pr_context, high hallucination risk, repair_before_continue
```

This makes the state portable across agents:

```text
Codex detects missing PR
-> LS records rupture
-> Claude sees repair event
-> next agent does not invent continuity
```

## Personal Cognitive Garden relationship

Personal Cognitive Garden answers:

```text
what development signal should become a human-reviewed graph proposal?
```

Session Continuity Repair answers:

```text
can this session safely continue, or did it lose shared orientation?
```

Together:

```text
session continuity
+ repair before hallucinated continuation
+ human-owned development graph
= safer AI-assisted growth and co-work
```

## MVP flow

```text
agent draft
-> classify expected session type
-> classify actual response type
-> compare against last shared point
-> detect rupture
-> score hallucination risk
-> emit repair prompt
-> hold / repair / continue
-> optionally propose PCG update after human review
```

## Safety invariant

> A session may continue only when the system can identify the last shared orientation point or explicitly repair the missing context.

## Product line

Short version:

```text
LS is a session continuity and repair layer for AI co-work.
```

Expanded version:

```text
LS routes Claude, Codex, and other agents through a local-first gateway that detects session rupture, blocks hallucinated continuation, restores the last shared orientation point, and only then allows safe continuation or human-reviewed memory updates.
```

## Reviewer summary

The layer turns a common model behavior — asking for missing context — into a portable, auditable runtime contract.

The key contribution is not another chat model. It is continuity governance:

```text
detect rupture
-> prevent hallucinated continuation
-> repair shared orientation
-> continue with evidence
```
