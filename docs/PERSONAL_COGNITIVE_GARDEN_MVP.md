# Personal Cognitive Garden MVP

## Purpose

This document defines the first practical MVP flow for turning an AI session into a reviewed Personal Cognitive Garden update.

The goal is not to build a full personal development platform immediately.

The goal is to make one interaction produce a structured, reviewable, consent-aware graph update.

Important distinction:

> Not every session develops the person. Not every agent improves the person.

LS should classify whether a session actually compounds human skill capital before it becomes part of the development graph.

## Core flow

```text
1. A person has an AI session.
2. LS summarizes the session into candidate signals.
3. LS classifies the session's developmental value.
4. An agent proposes a PersonalCognitiveGardenUpdate.
5. LS classifies the update into one node family.
6. LS records the development effect: skill delta, capital effect, practice needed, and compounding score.
7. The update remains proposed until review.
8. The person or governance layer accepts, rejects, revises, or defers it.
9. Only accepted updates may become durable graph state.
```

## Human capital compounding rule

A session may be useful without being developmental.

Examples:

- administrative sessions can organize work without increasing durable capability;
- emotional-support sessions can stabilize the person without directly building a skill;
- execution sessions can complete tasks without teaching a reusable pattern;
- noisy sessions should not be treated as growth;
- developmental sessions should increase skills, judgment, execution capacity, or reusable assets.

Core invariant:

> A session may inform memory, but only developmental sessions should compound human capital.

Human capital here means the person's own accumulated capability:

- skills;
- judgment;
- execution capacity;
- ability to learn with agents;
- decision quality;
- reusable patterns;
- portfolio evidence;
- reputation-backed artifacts.

It must not mean employer ownership of the person's private inner graph.

## Input

A session summary:

```text
examples/personal_cognitive_garden/session_summary.json
```

The session summary is not durable identity state. It is only source material.

## Proposed update

A proposed update:

```text
examples/personal_cognitive_garden/proposed_update.json
```

A proposed update may contain:

- a goal hypothesis;
- a skill-gap hypothesis;
- a decision record;
- a constraint;
- an evidence link;
- a reflection;
- a growth-path suggestion;
- a human skill delta;
- a capital effect assessment;
- a practice loop needed to make the skill durable.

It must remain advisory until review.

## Accepted graph state

An accepted graph-state example:

```text
examples/personal_cognitive_garden/accepted_graph_state.json
```

Only accepted updates may become durable graph state.

## Schema

The update contract is defined here:

```text
schemas/personal-cognitive-garden-update.v0.1.json
```

## Session development classes

| Class | Meaning |
|---|---|
| `neutral` | Useful context, but no clear growth signal. |
| `administrative` | Scheduling, organization, or coordination. |
| `emotional_support` | Stabilization or encouragement; may matter, but should not automatically count as skill capital. |
| `decision_clarification` | Improves decision quality or tradeoff clarity. |
| `skill_building` | Builds a specific capability through explanation, practice, or feedback. |
| `capital_compounding` | Creates reusable skill, judgment, portfolio, reputation, or execution leverage. |
| `execution` | Completes a task; may produce evidence, but is not automatically developmental. |
| `noise` | Should not update the growth graph. |

## Node families

| Family | Meaning |
|---|---|
| `goal` | What the person wants to become, build, learn, repair, or protect. |
| `skill` | A capability being developed or needing practice. |
| `decision` | A decision, rationale, and later outcome. |
| `constraint` | Time, energy, money, family context, risk, values, access, or policy limits. |
| `evidence` | Proof of progress: PRs, tests, demos, sent messages, notes, reports, calls, or completed actions. |
| `reflection` | Human-reviewed insight about patterns, strengths, blind spots, fatigue, or conflicts. |
| `growth_path` | Suggested next step, experiment, practice loop, or review checkpoint. |

## Development effect fields

Each update includes a `development_effect` object:

- `is_developmental` — whether this update plausibly grows human capability;
- `human_skill_delta` — skills or judgment areas affected;
- `capital_effect` — how the update may increase durable capability or leverage;
- `practice_needed` — concrete next practice needed to make the insight durable;
- `compounding_score` — advisory score from 0 to 1;
- `assessment_notes` — optional caveats.

The compounding score is not a psychological truth claim. It is a local prioritization signal.

## Governance rule

Core invariant:

> Proposal first, authorization second, commit third.

Agents may propose updates.

The person or governance layer decides whether the update becomes durable state.

## Safe defaults

- `status`: `proposed`
- `requires_human_review`: `true`
- `durable_state_allowed`: `false`
- `external_action_allowed`: `false`
- `sharing_scope`: `private`

These defaults prevent an agent from silently turning a conversation into long-term identity, memory, skill capital, employment, reputation, or action state.

## MVP commands, later

A future CLI can implement this flow:

```bash
python -m ls.pcg propose examples/personal_cognitive_garden/session_summary.json \
  --schema schemas/personal-cognitive-garden-update.v0.1.json \
  --out examples/personal_cognitive_garden/proposed_update.json

python -m ls.pcg review examples/personal_cognitive_garden/proposed_update.json \
  --accept \
  --reviewed-by human:owner \
  --out examples/personal_cognitive_garden/accepted_graph_state.json
```

The first implementation can be deterministic and local-only.

## Non-goals

This MVP does not claim to:

- infer psychological truth;
- know the person better than they know themselves;
- replace coaching, therapy, management, or human judgment;
- expose private development memory to employers;
- create a shared consciousness or global brain;
- count every session as growth;
- treat agent improvement as human improvement;
- authorize external actions from a graph proposal alone.

## Reviewer summary

The MVP converts this claim:

> Every developmental AI session should compound into human-owned skill capital.

Into this inspectable mechanism:

```text
session summary
-> development classification
-> proposed PersonalCognitiveGardenUpdate
-> human/governance review
-> accepted graph state
```

That is the smallest useful bridge from LS as an oversight runtime to LS as human development infrastructure.
