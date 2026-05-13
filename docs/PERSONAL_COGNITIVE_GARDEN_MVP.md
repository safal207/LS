# Personal Cognitive Garden MVP

## Purpose

This document defines the first practical MVP flow for turning an AI session into a reviewed Personal Cognitive Garden update.

The goal is not to build a full personal development platform immediately.

The goal is to make one interaction produce a structured, reviewable, consent-aware graph update.

## Core flow

```text
1. A person has an AI session.
2. LS summarizes the session into candidate development signals.
3. An agent proposes a PersonalCognitiveGardenUpdate.
4. LS classifies the update into one node family.
5. The update remains proposed until review.
6. The person or governance layer accepts, rejects, revises, or defers it.
7. Only accepted updates may become durable graph state.
```

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
- a growth-path suggestion.

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

These defaults prevent an agent from silently turning a conversation into long-term identity, memory, employment, reputation, or action state.

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
- authorize external actions from a graph proposal alone.

## Reviewer summary

The MVP converts this claim:

> Every AI session should compound into human development.

Into this inspectable mechanism:

```text
session summary
-> proposed PersonalCognitiveGardenUpdate
-> human/governance review
-> accepted graph state
```

That is the smallest useful bridge from LS as an oversight runtime to LS as human development infrastructure.
