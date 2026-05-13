# LS Personal Cognitive Garden

## Thesis

LS should not be framed primarily as a general cognitive network.

LS should be framed as a **personal, goal-directed cognitive garden**: a local-first graph of a person's goals, skills, decisions, constraints, evidence, and growth paths, cultivated over time by the agents and models that the person chooses to connect.

Core line:

> LS helps a person grow their own cognitive graph. Agents are gardeners, not owners.

## Why this distinction matters

A general cognitive network sounds broad, vague, and easy to misunderstand. It can imply that human context is being absorbed into a shared intelligence layer.

A personal cognitive garden is more precise:

- the person owns the graph;
- the person's goals define the direction of growth;
- agents may propose updates, but do not own or authorize identity-level state;
- every session can leave useful structure behind instead of disappearing into chat history;
- the graph can support personal development, leadership, learning, work quality, and long-term self-direction.

This makes LS more human-centered, safer to explain, and more commercially legible.

## What the garden contains

The personal cognitive garden is not a bag of memories. It is a structured graph around development.

Initial node families:

- **Goals** — what the person is trying to become, build, learn, repair, or protect.
- **Skills** — capabilities being developed over time.
- **Decisions** — choices made, reasons considered, and later outcomes.
- **Constraints** — time, energy, family context, money, risk, values, access, and policy limits.
- **Evidence** — artifacts proving progress: merged PRs, demos, tests, shipped pages, sent messages, calls, notes, reports, or completed actions.
- **Reflections** — human-reviewed insights about patterns, blind spots, strengths, fatigue, conflicts, or recurring loops.
- **Growth paths** — suggested next steps, experiments, practice loops, or review checkpoints.

## Agent role

Agents do not become the garden.

Agents help cultivate it by producing bounded signals:

```text
agent/session output
  -> model contribution signal
  -> proposed cognitive graph update
  -> human/governance review
  -> accepted garden update or rejected proposal
```

Each connected model, tool, or agent can contribute:

- a clearer articulation of a goal;
- a skill-gap hypothesis;
- a decision rationale;
- an evidence link;
- a next-action suggestion;
- a contradiction or risk warning;
- a reflection prompt;
- a route recommendation for future sessions.

But these remain proposals until accepted under the relevant governance boundary.

## Relationship to MCLG

The Model Contribution Learning Graph (MCLG) measures model usefulness and turns contribution into advisory routing priors.

The Personal Cognitive Garden defines the human-owned target that those contributions serve.

In short:

```text
MCLG answers: which models helped, where, and how reliably?
PCG answers: what human-owned graph are those contributions helping grow?
```

MCLG may influence future model selection, review routing, council roles, and advisory cognitive graph updates.

It must not directly authorize personal identity writes, private memories, external actions, profile changes, or shared-state exports.

## Governance boundary

Core invariant:

> Agents may propose garden updates. The person and governance layer authorize identity-level growth.

The following changes require explicit review or a governed policy path:

- changes to long-term goals;
- changes to identity-level profile claims;
- private memory creation or sharing;
- external actions;
- corporate reporting about a person's development;
- cross-person or team-level aggregation;
- any update that could affect reputation, evaluation, employment, access, or obligations.

Safe default:

```text
proposal first, authorization second, commit third.
```

## Privacy and ownership

The garden is personal by default.

For individual use, the person should be the primary owner and reviewer of the graph.

For company use, LS should separate:

- private personal garden data;
- work-context development signals;
- aggregated team capability insights;
- explicit manager-visible artifacts;
- compliance or audit evidence.

A company may fund development infrastructure, but it should not receive unlimited access to a person's inner graph.

Enterprise value comes from better development and coordination, not from surveillance.

## Commercial positioning

The economic wedge is not another chatbot.

The wedge is:

> Every AI session should compound into human development.

Potential buyers and users:

- founders building themselves and their companies;
- engineers and QA teams improving judgment, quality, and delivery;
- executives using AI coaching with evidence and continuity;
- companies running leadership development and onboarding;
- learning platforms that need persistent skill graphs;
- agent-platform teams that need personal memory governance;
- coaching, mentoring, and creator businesses.

Positioning phrases:

- From chat history to a human development graph.
- Your AI sessions should not disappear. They should grow you.
- Personal AI memory with goals, evidence, and governance.
- Human development infrastructure for the agent era.
- A cognitive garden owned by the person, cultivated by agents.

## B2C product shape

A personal product can start with:

- a goal graph;
- a skill graph;
- session-to-insight extraction;
- human-reviewed graph updates;
- weekly growth review;
- evidence-based progress journal;
- next best growth action;
- agent contribution history.

The user experience should feel less like a database and more like a living development cockpit.

## B2B product shape

A company product can start with:

- employee growth graphs with private/public boundaries;
- onboarding maps;
- role-skill development paths;
- team capability heatmaps based on consented or aggregated data;
- coaching plans generated from evidence;
- AI-agent interaction governance;
- audit trails for development recommendations;
- manager-safe summaries rather than raw private memory.

High-value use cases:

- engineering excellence programs;
- sales enablement;
- leadership coaching;
- founder acceleration;
- AI transformation programs;
- internal academy and learning infrastructure;
- regulated-team decision training.

## Claim discipline

Do not claim:

- LS knows the person better than the person knows themselves.
- LS proves psychological truth.
- LS creates consciousness.
- LS replaces coaching, therapy, management, or human judgment.
- LS can safely expose a person's full growth graph to an employer.

Prefer:

- LS proposes structured hypotheses about growth.
- The person reviews, accepts, rejects, or corrects updates.
- The graph records development signals with provenance.
- Agents contribute, but governance decides.
- The system is designed for continuity, consent, and inspectability.

## MVP path

A minimal MVP should avoid overbuilding.

Suggested first slice:

1. Define a `PersonalCognitiveGardenUpdate` JSON artifact.
2. Extract candidate updates from a session summary.
3. Classify candidates into goal, skill, decision, constraint, evidence, reflection, or growth path.
4. Require human review before commit.
5. Store accepted updates as local-first graph records.
6. Link each update to source session, model contribution signal, and transition ID.
7. Render a simple weekly growth review.

Example artifact:

```json
{
  "garden_update_id": "pcg_update_2026_05_13_001",
  "transition_id": "transition_2026_05_13_001",
  "source_session_id": "session_2026_05_13_ls_strategy",
  "proposed_by": "agent:strategy_council",
  "node_family": "goal",
  "claim": "The user wants LS to develop personal goal-directed cognitive gardens rather than a general cognitive network.",
  "evidence": [
    "User explicitly described personal cognitive network growth as the desired direction."
  ],
  "status": "proposed",
  "requires_human_review": true
}
```

## Reviewer summary

LS is not trying to absorb people into a shared cognitive network.

LS is building the infrastructure for a person to own and grow a goal-directed cognitive graph, with agents acting as bounded contributors.

This shifts the project from generic cognition toward personal development infrastructure:

```text
human-owned graph
+ goal direction
+ agent contribution signals
+ governance and consent
+ replayable evidence
= personal cognitive garden
```

Core invariant:

> The garden belongs to the person. Agents help cultivate it. Governance decides what becomes durable state.
