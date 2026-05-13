# Page 2 — The New Mechanism: Skill-Capital Signals

## Big idea

AI sessions should not disappear into chat history. Useful sessions should become reviewed skill-capital signals.

The Personal Cognitive Garden introduces a simple mechanism:

```text
AI session
-> development classification
-> skill delta
-> evidence
-> human review
-> accepted graph update
```

## Not every session develops the person

One of the most important design choices is restraint.

LS does not assume that every AI session creates growth.

A session may be:

```text
neutral
administrative
emotional_support
decision_clarification
skill_building
capital_compounding
execution
noise
```

This matters because AI can feel productive even when nothing durable changed.

A friendly conversation may be useful, but not developmental. A code-generation session may create output, but not necessarily skill. A strategy session may clarify a decision, but not always create a new capability.

## What counts as skill capital?

A session begins to count as skill capital when there is evidence that something durable changed in the person or their development path.

Examples:

- a clearer architectural decision;
- a new debugging pattern;
- a stronger risk-framing ability;
- a reusable testing heuristic;
- a more precise product narrative;
- a practice loop the person can repeat;
- evidence that can be reviewed later.

## The graph

The Personal Cognitive Garden stores development as a human-owned graph.

The graph can include:

```text
goals
skills
decisions
constraints
evidence
reflections
growth paths
```

But agents do not silently rewrite this graph.

They propose updates.

The person reviews them.

Only accepted updates become durable state.

## Example

A raw AI session may produce this developmental effect:

```json
{
  "session_development_class": "capital_compounding",
  "development_effect": {
    "is_developmental": true,
    "human_skill_delta": [
      "risk_framing",
      "product_positioning",
      "governance_boundary_design"
    ],
    "capital_effect": "The session improved the person's ability to explain a product without making it sound like surveillance.",
    "practice_needed": "Add a red-team misuse scenario and explain the safe alternative.",
    "compounding_score": 0.87
  }
}
```

The important part is not the score alone.

The important part is the chain:

```text
claim
-> evidence
-> review
-> accepted or rejected state
```

## Why this is different from AI memory

AI memory usually asks:

```text
What should the assistant remember about the user?
```

The Personal Cognitive Garden asks:

```text
What did this session actually develop in the person, and should that claim be accepted into their private graph?
```

That shift changes the product.

It is not just personalization.

It is governed human development state.

## Transition

But once we create a graph of goals, skills, weaknesses, reflections, and growth paths, a new risk appears.

Who owns that graph?

Who can see it?

Can a company use it to rank people?

That is where the safety boundary becomes central.

[Next → Page 3 — The Safety Boundary: Growth Without Surveillance](03-anti-surveillance-boundary.md)

[Back ← Page 1](01-hidden-cost.md) · [Index](README.md)
