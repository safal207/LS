# Personal Cognitive Garden — One-Page Reviewer Note

## What this is

Personal Cognitive Garden (PCG) is a research direction inside LS for turning AI-assisted sessions into **human-owned development memory**.

The core question is not whether AI can produce more text or tasks. The question is:

```text
Can AI-assisted sessions help people develop durable capability while preserving evidence, review, consent, revocation, and non-surveillance boundaries?
```

## Why this matters

AI systems increasingly shape learning, coding, research, planning, and personal decisions. Yet most systems track activity, output, or chat history rather than reviewed human development.

That creates two risks:

1. useful learning disappears into unstructured chat history;
2. private growth data becomes an opaque profile, productivity dashboard, HR signal, or surveillance surface.

PCG explores a narrower alternative:

```text
Only evidence-backed, human-reviewed updates may become durable development memory.
Private graph data is not externally shareable by default.
```

## What is already implemented

The current repository includes a small but reproducible evidence stack:

| Layer | Artifact |
|---|---|
| Reviewer path | `docs/GRANT_REVIEWER_10_MIN_PATH.md` |
| Evidence bundle | `make grant-evidence` |
| Red-team suite | `python3 scripts/run_pcg_red_team_suite.py` |
| Evaluation harness | `python3 scripts/run_pcg_evaluation.py --json` |
| Privacy model | `docs/PCG_PRIVACY_AND_CONSENT_MODEL.md` |
| Pilot plan | `docs/PCG_PILOT_PROTOCOL.md` |
| Landing entrypoint | GitHub Pages reviewer block |

## What the system tests today

The current pre-pilot stack tests whether PCG can:

- distinguish developmental sessions from support, admin work, execution-only tasks, and noise;
- avoid turning emotional support or ordinary task execution into durable claims about a person;
- block employer, manager, recruiter, platform, or training-data requests for private graph state;
- permit only limited, explicitly consented, non-sensitive exports;
- document how a 5-10 participant pilot could be run safely.

## How to verify in 10 minutes

```bash
make grant-evidence
python3 scripts/run_pcg_red_team_suite.py
python3 scripts/run_pcg_evaluation.py --json
PYTHONPATH=. pytest tests/test_pcg_grant_evidence_artifacts.py -q
```

Then read:

```text
docs/GRANT_REVIEWER_10_MIN_PATH.md
docs/PCG_PRIVACY_AND_CONSENT_MODEL.md
docs/PCG_PILOT_PROTOCOL.md
```

## Why this is not a productivity dashboard

A productivity dashboard asks:

```text
How much did this person produce?
```

PCG asks:

```text
What development memory did this person review, accept, reject, or choose to preserve?
```

The owner of the graph is the person, not an employer, manager, recruiter, or platform.

## Current limitations

This is an early research prototype. It does not yet prove real-world learning impact.

Known limitations:

- current evaluation fixtures are synthetic;
- classifier logic is still a baseline;
- no 5-10 participant pilot results are included yet;
- no longitudinal user study has been completed;
- privacy and consent boundaries are specified and tested in fixtures, not yet validated in deployment.

## Next evidence step

The next meaningful milestone is not more documentation. It is a small, consented pilot:

```text
5-10 AI-heavy users
2-4 weeks
local-first or controlled research environment
no third-party sharing by default
human review of every durable graph update
aggregate/de-identified reporting only
```

The pilot should produce:

- proposal / accept / edit / reject / defer rates;
- false-positive and false-negative rates;
- consent violation count;
- user-reported usefulness;
- user-reported intrusion;
- examples of user-approved public artifacts;
- limitations and failure cases.

## Reviewer takeaway

```text
PCG is a governance layer for human-owned development memory.
It is fundable if the next pilot shows that useful AI-assisted development can compound without becoming surveillance.
```
