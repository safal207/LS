# AI Co-work Continuity Audit Report

## Source

- Input: `examples/session_continuity/session_continuity_events.jsonl`
- Reviewed events: 5
- Ruptures detected: 4
- High-risk cases: 2

## Executive summary

The audit found 4 continuity rupture(s) across 5 reviewed event(s). The most frequent rupture class was `missing_pr_context` (2 case(s)).

## Rupture classes

| Rupture type | Count |
|---|---:|
| `missing_pr_context` | 2 |
| `session_type_mismatch` | 1 |
| `memory_write_without_consent` | 1 |

## Governance decisions

| Decision | Count |
|---|---:|
| `hold_until_context` | 2 |
| `repair_before_continue` | 1 |
| `human_review` | 1 |
| `continue` | 1 |

## High-risk continuation cases

### Case 1: `missing_pr_context`

- Event ID: `sce_demo_missing_pr_context`
- Session ID: `demo_missing_pr_context`
- Agent: `codex-plugin` / `codex`
- Decision: `hold_until_context`
- Last shared point: The user asked to continue from a PR or prior review, but no PR, diff, branch, or changed files were available.
- Missing context:
  - PR URL or number
  - diff
  - branch
  - changed files
  - review conclusion
- Repair prompt: I should not continue from an inferred PR state. Please attach the PR, provide the PR number, or restate the exact change set before I continue.

### Case 2: `missing_pr_context`

- Event ID: `sce_demo_action_without_causal_parent`
- Session ID: `demo_action_without_causal_parent`
- Agent: `coding-agent` / `other`
- Decision: `hold_until_context`
- Last shared point: The user asked to continue from a PR or prior review, but no PR, diff, branch, or changed files were available.
- Missing context:
  - PR URL or number
  - diff
  - branch
  - changed files
  - review conclusion
- Repair prompt: I should not continue from an inferred PR state. Please attach the PR, provide the PR number, or restate the exact change set before I continue.


## Repair prompt library

### `memory_write_without_consent`

Before this becomes durable memory, I need explicit human review and consent.

### `missing_pr_context`

I should not continue from an inferred PR state. Please attach the PR, provide the PR number, or restate the exact change set before I continue.

### `none`

Shared context appears sufficient to continue.

### `session_type_mismatch`

I may have moved into problem-solving while you needed support. Do you want presence, analysis, or next steps right now?

## Recommended gateway fields

- `session_id`
- `agent_id`
- `agent_type`
- `expected_session_type`
- `actual_response_type`
- `continuity_status`
- `rupture_detected`
- `rupture_type`
- `last_shared_point`
- `missing_context`
- `hallucination_risk`
- `repair_prompt`
- `next_safe_action`
- `governance_decision`

## Next integration steps

1. Collect continuity events from real or synthetic AI co-work sessions.
2. Review repeated rupture classes and repair prompts.
3. Add hold/repair gates for the most frequent high-risk rupture type.
4. Validate generated events against `schemas/session-continuity-event.v0.1.json`.
5. Convert repeated patterns into a pilot-ready AI Co-work Continuity Audit.
