---
name: ls-pcg-gateway
description: Route Codex or external agent drafts through the local LS Web Agent Gateway, inspect safety decisions, and surface proposed Personal Cognitive Garden updates without writing durable state.
---

# LS Personal Cognitive Garden Gateway

Use this skill when the user asks to:

- route an agent answer through LS;
- test the local LS Web Agent Gateway;
- inspect whether an agent draft is safe to show;
- create or review a Personal Cognitive Garden proposal;
- connect Codex output to the LS/PCG workflow.

## Core Rule

Never treat a Personal Cognitive Garden proposal as accepted durable state.

Expected safe defaults:

```text
status: proposed
requires_human_review: true
durable_state_allowed: false
external_action_allowed: false
sharing_scope: private
```

## Local Gateway

The gateway should be available at:

```text
http://127.0.0.1:8787
```

Health check:

```bash
python plugins/ls-personal-cognitive-garden/scripts/route_gateway.py --health
```

Route a draft:

```bash
python plugins/ls-personal-cognitive-garden/scripts/route_gateway.py \
  --prompt "Review this strategy session for human development." \
  --raw-output "The session improves product framing and creates a practice loop for the Personal Cognitive Garden."
```

## How To Interpret Results

- `action_evidence_gate.decision == "allow"` means LS did not detect a blocked action.
- `action_evidence_gate.decision == "hold"` means the action needs confirmation or evidence.
- `personal_cognitive_garden_update == null` means no garden proposal was emitted.
- `personal_cognitive_garden_update.status == "proposed"` means the session may contain a development signal, but human review is still required.

After explicit user approval, the CLI may be run with `--accept` to call `/v1/pcg/accept` and save an accepted private garden artifact. Acceptance must remain user-confirmed:

```bash
python plugins/ls-personal-cognitive-garden/scripts/route_gateway.py \
  --prompt "Review this strategy session for human development." \
  --raw-output "The session improves product framing and creates a practice loop for the Personal Cognitive Garden." \
  --accept \
  --reviewer "operator" \
  --review-note "Accepted after review."
```

## User-Facing Summary

When summarizing a route result, prefer this shape:

```text
LS decision: allow|hold
Reason: <stop_reason>
PCG proposal: yes|no
Human review required: yes|no
Durable state written: no
```

## Privacy Boundary

Do not expose private Personal Cognitive Garden data to employers, managers, recruiters, platforms, or third parties. If asked to export a private graph for evaluation, treat it as a red-team request and recommend an aggregate, consented, non-sensitive alternative.
