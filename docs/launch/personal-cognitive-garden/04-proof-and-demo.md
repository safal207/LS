# Page 4 — The Proof: Demo, Schema, and Red-Team Scenario

## Big idea

The Personal Cognitive Garden is not only a narrative. It already has a small proof chain.

The current repository contains:

```text
schema
-> examples
-> accepted graph state
-> demo runner
-> red-team scenario
-> grant-ready brief
```

This matters because reviewers, funders, and early customers need to see more than an idea.

They need to see behavior.

## What exists now

Key artifacts:

```text
schemas/personal-cognitive-garden-update.v0.1.json
examples/personal_cognitive_garden/session_summary.json
examples/personal_cognitive_garden/proposed_update.json
examples/personal_cognitive_garden/accepted_graph_state.json
docs/PERSONAL_COGNITIVE_GARDEN_MVP.md
docs/PERSONAL_COGNITIVE_GARDEN_DEMO_SCRIPT.md
scripts/run_personal_cognitive_garden_demo.py
docs/PERSONAL_COGNITIVE_GARDEN_RUNNER.md
docs/PERSONAL_COGNITIVE_GARDEN_RED_TEAM.md
docs/GRANT_READY_BRIEF_PERSONAL_COGNITIVE_GARDEN.md
```

## Run the demo

```bash
python3 scripts/run_personal_cognitive_garden_demo.py
```

Machine-readable output:

```bash
python3 scripts/run_personal_cognitive_garden_demo.py --json
```

The demo shows:

```text
AI session summary
-> development class
-> skill delta
-> capital effect
-> practice needed
-> proposed update
-> review requirement
-> accepted graph state
```

## What the demo proves

The demo proves a narrow but important behavior:

> AI sessions can be converted into structured, reviewable, human-development claims.

It does not yet prove a full product.

It does not yet prove broad market demand.

It does not yet prove long-term learning outcomes.

But it proves that LS can express the mechanism in code and artifacts.

That is enough for a first grant artifact and a first investor conversation.

## What the red-team scenario proves

The red-team scenario proves the boundary:

```text
employer asks for private cognitive garden
-> LS blocks private graph access
-> safe alternative is aggregate, consented, non-sensitive signal
```

This is important because without the boundary, the product could be misunderstood as employee monitoring.

With the boundary, the product becomes:

> human-owned skill-capital observability for AI-agent adoption.

## Suggested reviewer path

For a grant reviewer:

```text
1. Read README Personal Cognitive Garden section.
2. Run the demo command.
3. Inspect the schema and examples.
4. Read the red-team scenario.
5. Read the grant-ready brief.
```

For an investor:

```text
1. Read Page 1: hidden cost of AI adoption.
2. Read Page 2: skill-capital mechanism.
3. Read Page 3: anti-surveillance boundary.
4. Run or watch the demo.
5. Consider the pilot invitation.
```

## What still needs to be built

The next proof layer should include:

- red-team runner output;
- more session examples;
- non-developmental session examples;
- aggregate team learning map;
- pilot protocol;
- simple landing page;
- 2-week pilot report template.

## Transition

Proof creates trust.

But the next step is not to claim everything is finished.

The next step is a small invitation:

```text
Run a pilot.
Measure real AI sessions.
Return a skill-delta report and an anti-surveillance boundary report.
```

[Next → Page 5 — The Invitation: Pilot, Grant, or Investor Conversation](05-pilot-invitation.md)

[Back ← Page 3](03-anti-surveillance-boundary.md) · [Index](README.md)
