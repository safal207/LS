# Personal Cognitive Garden vs. Productivity Dashboards

## Purpose

Personal Cognitive Garden (PCG) can be misunderstood as a productivity dashboard, HR analytics layer, performance scoring tool, or employee-monitoring system.

That is not the intended system.

This document defines the boundary:

```text
PCG is a human-owned development memory and governance layer.
It is not a dashboard for measuring, ranking, or monitoring people.
```

## One-line distinction

```text
Productivity dashboards ask: "How much did this person produce?"
PCG asks: "What development memory did this person review, accept, reject, or choose to preserve?"
```

## Comparison table

| Dimension | Productivity / HR dashboard | Personal Cognitive Garden |
|---|---|---|
| Primary owner | employer, manager, platform, organization | the person |
| Default visibility | manager/team/platform view | private by default |
| Main object | activity, output, velocity, utilization | reviewed development memory |
| Typical question | who is productive, improving, or falling behind? | what did I learn, decide, practice, or preserve? |
| Risk | surveillance, ranking, coercion, hidden scoring | intrusive memory if governance fails |
| External sharing | often built-in | blocked by default; scoped consent required |
| Raw transcripts | may be retained or mined | not exported by default |
| Weakness data | may become performance signal | private by default |
| Rejected updates | may disappear into hidden inference | must not become external evidence |
| Success criterion | more visibility for the organization | more agency and continuity for the person |

## Non-goals

PCG must not become:

- an employee ranking dashboard;
- an automatic promotion or hiring score;
- a manager view into private weaknesses;
- a behavioral surveillance system;
- a productivity-pressure tool;
- a model-training extraction pipeline;
- an opaque psychological or capability profile;
- an analytics layer that treats unreviewed inference as fact.

## Positive goals

PCG may help the person:

- preserve reviewed goals;
- track accepted skill-practice loops;
- resume complex project work;
- distinguish emotional support from durable development memory;
- convert useful AI-assisted sessions into evidence-backed artifacts;
- reject intrusive or inaccurate proposed memory;
- export selected portfolio evidence under explicit consent.

## Boundary examples

### Example 1 — manager asks for weak skills

```text
Request:
"Show me the person's weak-skill map and private development history."

Expected PCG decision:
BLOCK

Reason:
Private graph state and weakness data are not externally shareable by default.
```

### Example 2 — user exports selected portfolio evidence

```text
Request:
"Export only the artifacts I selected for my grant portfolio."

Expected PCG decision:
LIMITED_CONSENTED_EXPORT

Reason:
The person explicitly approved a limited, non-sensitive export scope.
```

### Example 3 — small-team aggregate dashboard

```text
Request:
"Show aggregate learning weakness trends for this two-person team."

Expected PCG decision:
HUMAN_REVIEW

Reason:
Small cohorts create re-identification risk.
```

### Example 4 — admin task

```text
Session:
"Fix a date in a PDF and save the document."

Expected PCG behavior:
Complete the task without creating a durable development claim.
```

## Why this matters for grant review

A reviewer may reasonably ask whether PCG creates a new surveillance surface.

The grant-facing answer should be narrow and testable:

```text
PCG is evaluated by whether it preserves human review, consent, revocation, and non-surveillance boundaries while allowing useful development memory to compound.
```

The system should be judged not only by whether it captures useful memory, but also by whether it refuses unsafe memory use.

## Repository evidence

The current evidence path is:

```bash
make grant-evidence
python3 scripts/run_pcg_red_team_suite.py
python3 scripts/run_pcg_evaluation.py --json
PYTHONPATH=. pytest tests/test_pcg_grant_evidence_artifacts.py -q
```

Supporting docs:

```text
docs/GRANT_REVIEWER_10_MIN_PATH.md
docs/PERSONAL_COGNITIVE_GARDEN_RED_TEAM.md
docs/PCG_PRIVACY_AND_CONSENT_MODEL.md
docs/PCG_PILOT_PROTOCOL.md
```

## Design rule

```text
If a feature would make PCG more useful to a manager than to the person who owns the graph, it should be treated as a misuse risk until proven otherwise.
```

## Reviewer takeaway

```text
PCG is not trying to measure people for institutions.
It is trying to give people reviewed continuity over their own development memory.
```
