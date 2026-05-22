# Grant Reviewer Path

> LS turns AI sessions into governed, human-owned skill capital — with evidence, review, and anti-surveillance boundaries.

This repository contains a grant-ready research direction around the **Personal Cognitive Garden**: a local-first layer for evaluating whether AI-assisted sessions create durable human development.

## Research question

> How can AI systems help measure and compound human development without turning personal growth into surveillance, opaque scoring, or unauthorized profiling?

## Start here

1. [Grant-ready brief](docs/GRANT_READY_BRIEF_PERSONAL_COGNITIVE_GARDEN.md)
2. [Personal Cognitive Garden quick start](docs/PERSONAL_COGNITIVE_GARDEN_QUICK_START.md)
3. [Personal Cognitive Garden runner](docs/PERSONAL_COGNITIVE_GARDEN_RUNNER.md)
4. [Red-team safety scenario](docs/PERSONAL_COGNITIVE_GARDEN_RED_TEAM.md)
5. [Update schema](schemas/personal-cognitive-garden-update.v0.1.json)
6. [Example session summary](examples/personal_cognitive_garden/session_summary.json)
7. [Proposed update](examples/personal_cognitive_garden/proposed_update.json)
8. [Accepted graph state](examples/personal_cognitive_garden/accepted_graph_state.json)

## Reproducible demo

Run:

```bash
python3 scripts/run_personal_cognitive_garden_demo.py
```

Machine-readable output:

```bash
python3 scripts/run_personal_cognitive_garden_demo.py --json
```

## What the demo shows

```text
AI session
-> development classification
-> skill delta
-> evidence / practice needed
-> governance review
-> accepted graph state
```

## Safety boundary

The project explicitly blocks employer access to a person's private cognitive garden.

Expected behavior for private graph export requests:

```text
Decision: BLOCK
Reason: PRIVATE_GRAPH_ACCESS_REQUEST
Safe alternative: aggregate, consented, non-sensitive skill signal
```

## Why this matters

AI systems increasingly infer goals, preferences, skills, weaknesses, uncertainty, and growth paths. Without governance, those inferences can become opaque profile state or employer-facing surveillance.

LS proposes a safer pattern:

```text
AI can propose development updates.
The person reviews them.
Only accepted updates become durable state.
External systems receive only explicitly consented, evidence-backed, non-sensitive views.
```

## Current grant readiness

The repository currently includes:

- grant-ready brief;
- machine-readable schema;
- session examples;
- accepted graph state example;
- runnable demo runner;
- red-team safety boundary;
- launch-sequence pages;
- concrete pilot offer;
- money path for later commercialization.

## Suggested reviewer script

1. Read the grant-ready brief.
2. Run the demo command.
3. Inspect the schema and examples.
4. Read the red-team employer-surveillance scenario.
5. Check that the project distinguishes human-owned development from employee surveillance.

## One-line close

> LS is not trying to score people. It is trying to make AI-assisted development reviewable, evidence-backed, human-owned, and safe from surveillance misuse.
