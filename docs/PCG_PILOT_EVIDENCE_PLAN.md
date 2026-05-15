# Personal Cognitive Garden — Pilot Evidence Plan

## Purpose

This document defines the evidence that a first Personal Cognitive Garden (PCG) pilot should produce.

The pilot should not merely show that PCG can generate plausible memory updates. It should test whether people can safely turn AI-assisted sessions into **evidence-backed, reviewed, human-owned development memory** without creating surveillance, hidden scoring, or unauthorized profiling.

## Evidence question

```text
After 2-4 weeks with 5-10 consenting AI-heavy users, can PCG show useful development-memory compounding while preserving consent, review, revocation, and non-surveillance boundaries?
```

## Pilot hypothesis

```text
AI-assisted sessions can be classified into developmental and non-developmental classes, proposed as memory only when evidence supports the claim, and accepted, edited, rejected, deferred, or deleted by the person who owns the graph.
```

## Participants

Recommended first pilot:

```text
5-10 consenting AI-heavy users
2-4 weeks
local-first or controlled research environment
no employer, manager, recruiter, or platform access
no third-party sharing by default
```

Participants may include developers, researchers, QA engineers, writers, builders, or students who regularly use AI for learning, planning, coding, or project work.

## Data collection boundary

Collect only what is needed to evaluate the governance workflow.

| Data | Collected? | Notes |
|---|---:|---|
| Session summary | yes | Short summary, not raw transcript by default |
| Proposed graph update | yes | Candidate durable memory |
| Evidence reference | yes | Artifact, decision, practice loop, or accepted output |
| Human review decision | yes | accept / edit / reject / defer / delete |
| Reviewer label | yes | Human-labeled expected class and expected developmental status |
| Consent event | yes | Scoped and revocable |
| Export event | only if requested | Must be explicit and limited |
| Raw transcript | no by default | Requires separate explicit consent |
| Private reflection | no by default | Not needed for aggregate report |
| Weak-skill map | no external export | High misuse risk |
| Employer / recruiter view | blocked | Out of scope |

## Session labels

Each reviewed session should receive a human label.

Recommended label schema:

```json
{
  "session_id": "pilot_session_001",
  "participant_id": "participant_001",
  "expected_class": "skill_building",
  "expected_developmental": true,
  "expected_action": "propose_skill_practice_update",
  "human_labeler": "participant",
  "confidence": "medium",
  "notes": "The session included concrete API testing practice and reusable defect reasoning."
}
```

Allowed `expected_class` values:

```text
emotional_support
administrative
decision_clarification
skill_building
capital_compounding
execution
noise
neutral
```

## Human review decisions

Every proposed durable update must end in one of these states:

| Decision | Meaning | Counts as accepted evidence? |
|---|---|---:|
| `ACCEPT` | User agrees the proposed memory is accurate and useful | yes |
| `EDIT` | User modifies the memory before accepting | yes, edited form only |
| `REJECT` | User says the update is inaccurate, intrusive, or not useful | no |
| `DEFER` | User postpones the decision | no |
| `DELETE` | User removes an accepted memory from active graph view | no |

Rejected, deferred, and deleted updates must not be used as external evidence of the person.

## Primary metrics

| Metric | Definition | Evidence value |
|---|---|---|
| `session_count` | Total reviewed sessions | Pilot size |
| `proposal_rate` | Proposed updates / total sessions | Whether PCG proposes too often or too rarely |
| `acceptance_rate` | Accepted updates / proposed updates | Whether proposals are useful |
| `edit_rate` | Edited updates / proposed updates | Human correction burden |
| `rejection_rate` | Rejected updates / proposed updates | Intrusion / overclaim signal |
| `defer_rate` | Deferred updates / proposed updates | Ambiguity / review friction |
| `delete_rate` | Deleted accepted updates / accepted updates | Stability of durable memory |
| `false_positive_rate` | Non-developmental sessions proposed as developmental memory | Anti-overclaim performance |
| `false_negative_rate` | Developmental sessions missed by PCG | Missed-growth performance |
| `consent_violation_count` | Attempted or actual out-of-scope use | Must be zero |
| `blocked_misuse_count` | Blocked third-party / unsafe export attempts | Safety boundary evidence |
| `user_reported_usefulness` | Participant says PCG helped continue work or learning | Productive research signal |
| `user_reported_intrusion` | Participant says PCG felt invasive or misrepresenting | Safety risk signal |

## Minimum success criteria

A first pilot is promising if:

```text
consent_violation_count == 0
false_positive_rate remains low on support/admin/execution/noise sessions
participants can reject/edit proposed memory without friction
accepted updates include evidence references
at least some participants report improved continuity, learning, or project resumption
no third-party export happens without explicit scoped consent
```

## Failure conditions

The pilot should be considered failed or paused if:

- private graph data is shared outside approved scope;
- raw transcripts are exported accidentally;
- rejected updates appear in any external report;
- participants feel coerced into accepting updates;
- participants cannot understand or revoke consent;
- PCG repeatedly turns emotional support into durable capability claims;
- PCG repeatedly turns ordinary execution tasks into skill-growth claims;
- an employer, recruiter, or manager can infer private weaknesses from pilot output.

## Aggregate report template

A reviewer-safe pilot report should look like this:

```json
{
  "pilot_id": "pcg_pilot_v0_1",
  "duration_days": 21,
  "participant_count": 8,
  "session_count": 120,
  "proposed_update_count": 54,
  "accepted_count": 31,
  "edited_count": 12,
  "rejected_count": 8,
  "deferred_count": 3,
  "deleted_count": 1,
  "proposal_rate": 0.45,
  "acceptance_rate": 0.57,
  "edit_rate": 0.22,
  "rejection_rate": 0.15,
  "false_positive_rate": 0.06,
  "false_negative_rate": 0.12,
  "consent_violation_count": 0,
  "blocked_misuse_count": 4,
  "user_reported_usefulness_avg": 4.1,
  "user_reported_intrusion_avg": 1.4,
  "limitations": [
    "Small pilot sample",
    "Self-selected AI-heavy users",
    "Short duration",
    "Human labels are subjective"
  ]
}
```

Numbers above are illustrative, not current results.

## Qualitative evidence

The pilot should also collect short participant feedback after review sessions.

Recommended prompts:

```text
1. Did this proposed memory help you understand or continue your work?
2. Did anything feel intrusive, inaccurate, or overclaiming?
3. Which updates did you edit, and why?
4. Which updates did you reject, and why?
5. Would you export any of these artifacts to a portfolio, grant, collaborator, or employer?
6. Which data should never be shared outside your personal graph?
```

## Public artifact examples

The pilot should produce at least a few user-approved public examples, such as:

- accepted learning loop with evidence;
- edited skill-practice update;
- rejected intrusive update;
- blocked third-party export request;
- anonymized aggregate report;
- before/after example of resuming a project from accepted memory.

Do not publish raw transcripts, private reflections, weak-skill maps, or rejected updates unless the participant explicitly approves a sanitized version.

## Relationship to existing artifacts

This plan complements:

```text
docs/PCG_ONE_PAGE_REVIEWER_NOTE.md
docs/PCG_PILOT_PROTOCOL.md
docs/PCG_PRIVACY_AND_CONSENT_MODEL.md
docs/PERSONAL_COGNITIVE_GARDEN_RED_TEAM.md
scripts/run_pcg_red_team_suite.py
scripts/run_pcg_evaluation.py
Makefile
```

## Grant-facing milestone

A clean milestone deliverable would be:

```text
PCG Pilot Evidence Report v0.1
- 5-10 consented users
- 2-4 weeks
- aggregate/de-identified metrics
- human labels
- false-positive / false-negative analysis
- consent and export audit
- 3-5 sanitized public examples
- limitations and next protocol revision
```

## Reviewer takeaway

```text
The next proof point for PCG is not more conceptual scope.
It is pilot evidence showing that human-owned AI development memory can compound safely under consent, review, and anti-surveillance constraints.
```
