# Personal Cognitive Garden Demo Script

## Purpose

This is a short demo script for explaining the Personal Cognitive Garden and Human Capital Compounding direction in 60 seconds.

The goal is to show that LS does not simply remember AI conversations. LS distinguishes ordinary sessions from sessions that increase a person's durable capability.

## 60-second spoken script

> Most AI products give answers, but the answers disappear into chat history.
>
> LS asks a different question: did this AI session actually improve the person's ability to act?
>
> Here is a simple example. A founder has a strategy session with an AI agent. LS summarizes the session, classifies it as `capital_compounding`, identifies a skill delta like `strategic_product_framing`, and proposes a Personal Cognitive Garden update.
>
> The update does not become permanent automatically. It stays proposed until the person reviews it.
>
> After approval, LS adds it to the person's human-owned cognitive garden as a goal, skill, evidence link, and practice loop.
>
> So the system is not just memory. It is a governed way to turn useful AI sessions into human skill capital.

## Demo flow

```text
AI session
-> session summary
-> development classification
-> skill delta
-> capital effect
-> practice needed
-> human review
-> accepted Personal Cognitive Garden update
```

## What to show on screen

### 1. Session summary

Show:

```text
examples/personal_cognitive_garden/session_summary.json
```

Say:

> This is the source session. It is not automatically durable identity or skill state.

### 2. Proposed update

Show:

```text
examples/personal_cognitive_garden/proposed_update.json
```

Highlight:

```json
"session_development_class": "capital_compounding"
```

Then highlight:

```json
"human_skill_delta": [
  "strategic_product_framing",
  "architecture_boundary_setting",
  "human_capital_positioning"
]
```

Say:

> LS identifies the skill or judgment being developed. Not every session gets this classification.

### 3. Governance boundary

Highlight:

```json
"status": "proposed",
"requires_human_review": true,
"durable_state_allowed": false,
"external_action_allowed": false
```

Say:

> The agent may propose growth, but it cannot silently rewrite the person's long-term graph.

### 4. Accepted graph state

Show:

```text
examples/personal_cognitive_garden/accepted_graph_state.json
```

Highlight:

```json
"reviewed_by": "human:owner",
"decision": "accept"
```

Say:

> Only after review does the update become durable graph state.

## Investor version

> Companies are adopting AI agents, but they cannot tell which interactions actually grow employee capability and which are just chat noise. LS turns AI sessions into governed skill-capital signals with review, evidence, and privacy boundaries.

## Grant / AI safety version

> LS provides a traceable and consent-aware mechanism for agent memory and human-development claims. Agent outputs do not become durable personal state without evidence, review, and governance.

## Founder / personal-use version

> Your AI sessions should not disappear. LS helps you see which conversations made you sharper, what skill improved, what evidence was created, and what practice loop should come next.

## Key invariant

> A session may inform memory, but only developmental sessions should compound human capital.

## One-line close

> LS turns useful AI sessions into reviewed, human-owned skill capital.
