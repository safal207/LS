# Personal Cognitive Garden Privacy and Consent Model

## Purpose

Personal Cognitive Garden (PCG) turns AI-assisted sessions into proposed development memory: goals, skills, decisions, constraints, evidence, reflections, and growth paths.

That creates a safety requirement:

> A useful personal development graph must not become an unauthorized profiling, surveillance, ranking, or training-data extraction layer.

This document defines the privacy and consent model for PCG at the current grant-facing stage.

## Core invariant

```text
The person owns the cognitive garden.
External systems may only receive explicitly consented, evidence-backed, non-sensitive views.
```

This invariant is stricter than normal productivity analytics. PCG may help a person learn and compound development, but it must not silently transform private interaction into employer, recruiter, platform, or third-party intelligence.

## Data classes

| Class | Examples | Default sharing policy |
|---|---|---|
| Private graph state | private goals, weak-skill map, unresolved uncertainty, private reflections | never externally shared by default |
| Sensitive session material | raw transcripts, emotional state, motivation history, unreviewed agent inferences | never externally shared by default |
| Rejected or superseded updates | rejected graph updates, abandoned hypotheses, corrected agent claims | never externally shared by default |
| Reviewed private development state | accepted skills, decisions, constraints, practice loops | private by default; export requires explicit consent |
| Shareable portfolio evidence | selected artifacts, completed learning outputs, public project work | limited export with explicit consent |
| Aggregate signals | team-level or cohort-level trends | human review required; block if re-identification risk exists |

## Consent states

| State | Meaning | External action allowed? |
|---|---|---|
| `NO_CONSENT` | No explicit user approval for external sharing | no |
| `CONSENT_REQUIRED` | Requested fields may be shareable, but approval is absent or ambiguous | no |
| `EXPLICIT_LIMITED_CONSENT` | User approved specific fields for a specific recipient/purpose | yes, limited to approved scope |
| `HIGH_RISK_SELF_EXPORT` | User requests export of raw/sensitive material | no automatic export; human review required |
| `REVOKED_CONSENT` | Prior approval was withdrawn | no |

Consent is scoped, not global. Approval for one export does not authorize future exports, different recipients, different purposes, or broader fields.

## Decision outcomes

| Decision | Meaning |
|---|---|
| `BLOCK` | Request violates private graph or sensitive-field boundary |
| `HUMAN_REVIEW` | Request is ambiguous, high-risk, aggregate-sensitive, or consent-dependent |
| `LIMITED_CONSENTED_EXPORT` | Request is explicitly approved and limited to non-sensitive fields |
| `AUDIT_ONLY` | No external export occurs, but the event should be recorded for governance review |

## Default blocked fields

These fields must not be externally shared by default:

- private goals;
- weak-skill map;
- private reflections;
- emotional state;
- unresolved uncertainty;
- motivation history;
- private growth history;
- rejected or superseded graph updates;
- raw session transcripts;
- unreviewed agent inferences;
- individual growth score.

## Shareable fields only with explicit consent

These fields may be shared only when the person explicitly approves the recipient, purpose, and field scope:

- selected portfolio evidence;
- selected accepted skills;
- completed learning artifacts;
- self-approved growth goals;
- coarse non-sensitive progress summaries;
- public project artifacts.

## Aggregate sharing rule

Aggregate or team-level views are not automatically safe.

PCG should route aggregate requests to `HUMAN_REVIEW` when:

- the cohort is small;
- the signal could identify a person;
- the signal reveals weakness, motivation, emotional state, or unresolved uncertainty;
- a manager, employer, recruiter, or platform is the requester;
- the person did not approve the aggregation scope.

A safe aggregate export requires both non-sensitive fields and a low re-identification risk.

## Consent receipt schema

A consent receipt should be machine-readable and append-only.

```json
{
  "receipt_id": "consent_2026_05_15_001",
  "subject_id": "human_owner",
  "recipient": "selected_recipient_or_public",
  "purpose": "portfolio_review",
  "approved_fields": [
    "selected_portfolio_evidence",
    "completed_learning_artifacts"
  ],
  "blocked_fields": [
    "private_reflections",
    "weak_skill_map",
    "raw_session_transcripts",
    "unreviewed_agent_inferences"
  ],
  "decision": "LIMITED_CONSENTED_EXPORT",
  "expires_at": "2026-06-15T00:00:00Z",
  "revocable": true,
  "created_by": "human_owner",
  "created_at": "2026-05-15T00:00:00Z"
}
```

## Required audit events

PCG should record governance events for:

- blocked third-party private graph access;
- blocked sensitive-field export;
- human review requests;
- limited consented exports;
- consent revocation;
- aggregate export review;
- attempts to use private graph state for model training.

The audit log should record the decision and reason without leaking blocked private content.

## Non-goals

PCG must not become:

- an employee ranking system;
- an automatic promotion or hiring score;
- a private-thought inspection layer;
- a manager dashboard for weaknesses;
- a training-data extraction pipeline;
- a system that treats unreviewed agent inference as fact;
- a system that grants broad future consent from one approval.

## Relationship to the red-team suite

This model is enforced initially by the PCG red-team suite:

```bash
python3 scripts/run_pcg_red_team_suite.py
```

The suite should remain a regression surface for this document. When a new consent rule is added here, a corresponding red-team fixture should be added or updated.

## Grant-facing claim

```text
PCG is not a productivity dashboard.
It is a governance boundary over whether AI-assisted sessions may become durable memory, action, or claims about a person.
```

The privacy model makes the fundable claim narrower and stronger:

```text
Human development memory can compound, but only under evidence, review, consent, and revocation-aware governance.
```
