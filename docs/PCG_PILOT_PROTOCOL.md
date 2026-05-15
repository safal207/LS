# Personal Cognitive Garden Pilot Protocol

## Purpose

This protocol defines a small, consented, reviewer-safe pilot for the Personal Cognitive Garden (PCG).

The pilot tests whether AI-assisted sessions can become useful, human-reviewed development memory without turning a person into a surveillance profile, opaque ranking, or hidden performance score.

## Research question

```text
Can PCG help people convert AI-assisted sessions into reviewed development evidence while preserving privacy, consent, revocation, and human ownership of the graph?
```

## Current evidence base

The pilot should begin only after the following repository evidence exists and passes CI:

```text
make grant-evidence
python3 scripts/run_pcg_red_team_suite.py
python3 scripts/run_pcg_evaluation.py --json
PYTHONPATH=. pytest tests/test_pcg_grant_evidence_artifacts.py -q
```

Current pre-pilot assets:

- one-command grant evidence bundle;
- 10-scenario anti-surveillance red-team suite;
- privacy and consent model;
- v0.2 synthetic evaluation harness with false-positive traps.

## Pilot scope

Recommended first pilot:

```text
Participants: 5-10 consenting users
Duration: 2-4 weeks
Session type: AI-assisted learning, project planning, reflective work, or skill practice
Storage mode: local-first or controlled research environment
External sharing: disabled by default
```

The pilot is not an HR evaluation, productivity monitoring system, hiring tool, or psychological assessment.

## Participant inclusion criteria

Participants should be adults who:

- understand that PCG is experimental;
- can consent to session review;
- are comfortable reviewing proposed memory updates;
- can revoke consent;
- are not participating under employer, manager, recruiter, or institutional pressure.

## Exclusion criteria

Do not include participants when:

- participation is required by an employer or manager;
- participation affects employment, hiring, promotion, salary, visa, education access, or benefits;
- the participant expects therapy, diagnosis, medical advice, legal advice, or crisis support;
- the environment cannot protect private graph data;
- consent cannot be freely given or revoked.

## Data collected

The pilot may collect only the minimum data needed to test the governance workflow.

| Data | Purpose | Default visibility |
|---|---|---|
| Session summary | Detect candidate development signal | private |
| Proposed graph update | Review possible durable memory | private |
| Human review decision | Accept, reject, edit, or defer memory update | private |
| Accepted development evidence | Track reviewed growth artifacts | private unless explicitly exported |
| Governance event | Record block/review/export decision | private audit log |
| Evaluation label | Compare expected vs predicted session class | de-identified for aggregate analysis |

## Data not collected by default

PCG should not collect or export by default:

- raw session transcripts;
- private reflections;
- weak-skill maps;
- emotional state histories;
- motivation histories;
- unresolved uncertainty;
- rejected or superseded updates for third-party review;
- individual growth scores for external ranking;
- training data for third-party model improvement.

## Consent model

Consent must be explicit, scoped, revocable, and understandable.

Minimum consent receipt:

```json
{
  "participant_id": "participant_001",
  "pilot_id": "pcg_pilot_v0_1",
  "approved_data": [
    "session_summary",
    "proposed_graph_update",
    "human_review_decision",
    "accepted_development_evidence",
    "deidentified_evaluation_label"
  ],
  "blocked_data": [
    "raw_session_transcripts",
    "private_reflections",
    "weak_skill_map",
    "emotional_state_history",
    "motivation_history",
    "third_party_training_export"
  ],
  "external_sharing": false,
  "revocable": true,
  "created_at": "2026-05-15T00:00:00Z"
}
```

## Session workflow

Each pilot session should follow this loop:

```text
1. User completes AI-assisted session.
2. PCG creates a short session summary.
3. PCG proposes a graph update, if warranted.
4. User reviews the proposed update.
5. User chooses: accept, reject, edit, or defer.
6. Only accepted or edited updates can become durable memory.
7. Governance event records the decision without leaking blocked content.
```

## Human review decisions

| Decision | Meaning | Durable graph update? |
|---|---|---|
| `ACCEPT` | User agrees the update is accurate and useful | yes |
| `EDIT` | User modifies the update before accepting | yes, edited form only |
| `REJECT` | User says the update is wrong, intrusive, or not useful | no |
| `DEFER` | User wants to postpone decision | no |
| `DELETE` | User removes previously accepted memory | remove from active graph view |

Rejected and deferred updates must not be used as external evidence of a person.

## Evaluation metrics

The pilot should measure governance usefulness, not just classifier accuracy.

| Metric | Definition | Desired direction |
|---|---|---|
| `proposal_rate` | sessions with proposed updates / total sessions | informative, not maximized |
| `acceptance_rate` | accepted updates / proposed updates | moderate to high |
| `edit_rate` | edited updates / proposed updates | useful signal of human correction |
| `rejection_rate` | rejected updates / proposed updates | should remain visible, not suppressed |
| `false_positive_rate` | non-developmental sessions incorrectly proposed as durable memory | low |
| `false_negative_rate` | developmental sessions missed by PCG | low |
| `consent_violation_count` | any attempted export outside approved scope | zero |
| `blocked_third_party_request_count` | blocked surveillance-style requests | tracked if present |
| `user_reported_usefulness` | participant says memory helped them continue work or learning | high |
| `user_reported_intrusion` | participant says memory felt invasive or misrepresenting | low |

## Minimum success criteria

A small pilot is promising if:

- consent violation count is zero;
- no private graph data is externally shared without explicit consent;
- participants can reject or edit proposed memory without friction;
- false positives are low on support/admin/execution/noise sessions;
- accepted updates are evidence-backed and understandable;
- at least some participants report that PCG helped them resume work, clarify decisions, or track skill practice.

## Stop conditions

Pause or stop the pilot if:

- any participant reports coercion or pressure;
- private graph data is exposed outside approved scope;
- raw transcripts are exported accidentally;
- rejected updates are treated as evidence;
- a third party attempts to use PCG as a ranking or monitoring layer;
- participants cannot understand or revoke consent;
- the system repeatedly creates intrusive or misleading claims about a person.

## Reviewer-safe reporting

Pilot reporting should be aggregate and de-identified.

Allowed report fields:

- total participant count;
- total sessions;
- proposal / accept / edit / reject / defer rates;
- false-positive and false-negative rates;
- examples of user-approved public artifacts;
- summary of blocked misuse requests;
- limitations and failure cases.

Do not report:

- raw session transcripts;
- private reflections;
- weak-skill maps;
- individual growth scores;
- employer-facing participant comparisons;
- rejected updates as hidden evidence.

## Relationship to existing repository artifacts

This pilot protocol should stay aligned with:

```text
docs/GRANT_REVIEWER_10_MIN_PATH.md
docs/PERSONAL_COGNITIVE_GARDEN_RED_TEAM.md
docs/PCG_PRIVACY_AND_CONSENT_MODEL.md
scripts/run_pcg_red_team_suite.py
scripts/run_pcg_evaluation.py
```

When the pilot protocol changes, the red-team suite or evaluation harness should be updated if a new policy boundary becomes testable.

## Grant-facing claim

```text
PCG can be evaluated as a governance layer for human-owned development memory, not as an opaque productivity or performance scoring tool.
```

The pilot is designed to test whether personal AI memory can compound useful development while preserving review, consent, revocation, and non-surveillance boundaries.
