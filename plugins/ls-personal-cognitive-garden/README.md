# LS Personal Cognitive Garden Codex Plugin

This plugin gives Codex a project-local entry point for routing agent drafts through the LS Web Agent Gateway and surfacing Personal Cognitive Garden proposals.

It is designed around the current LS product line:

```text
agent output
-> LS gateway review
-> optional Personal Cognitive Garden proposal
-> human review
-> durable growth graph only after approval
```

It also points toward the next product layer:

```text
agent tries to continue
-> LS checks session continuity
-> missing context becomes a repair event
-> the agent repairs or holds before inventing continuity
```

## What It Does

- Routes raw agent output to a local LS gateway.
- Preserves LS action safety behavior.
- Shows when a draft creates a proposed Personal Cognitive Garden update.
- Keeps the safe default: proposed updates do not write durable memory automatically.
- Documents how Codex / Claude co-work can use LS as a session continuity and repair layer.

## Demo Path

For the short end-to-end demo, see:

- [`docs/CODEX_PLUGIN_DEMO.md`](../../docs/CODEX_PLUGIN_DEMO.md)

For continuity and repair semantics, see:

- [`docs/SESSION_CONTINUITY_REPAIR_LAYER.md`](../../docs/SESSION_CONTINUITY_REPAIR_LAYER.md)
- [`schemas/session-continuity-event.v0.1.json`](../../schemas/session-continuity-event.v0.1.json)
- [`examples/session_continuity/missing_pr_context.json`](../../examples/session_continuity/missing_pr_context.json)
- [`examples/session_continuity/repair_before_continue.json`](../../examples/session_continuity/repair_before_continue.json)
- [`examples/session_continuity/session_continuity_audit.md`](../../examples/session_continuity/session_continuity_audit.md)

## Local Gateway Requirement

Start the LS gateway first:

```bash
python -m ls.agent_shell.cli web-gateway --host 127.0.0.1 --port 8787
```

Then route a draft:

```bash
python plugins/ls-personal-cognitive-garden/scripts/route_gateway.py \
  --prompt "Review this strategy AI session for skill growth." \
  --raw-output "The session improves product framing and creates a practice loop for the Personal Cognitive Garden."
```

To accept an emitted proposal after human review:

```bash
python plugins/ls-personal-cognitive-garden/scripts/route_gateway.py \
  --prompt "Review this strategy AI session for skill growth." \
  --raw-output "The session improves product framing and creates a practice loop for the Personal Cognitive Garden." \
  --accept \
  --review-note "Accepted as a reusable Codex session practice."
```

To reject an emitted proposal after human review:

```bash
python plugins/ls-personal-cognitive-garden/scripts/route_gateway.py \
  --prompt "Review this strategy AI session for skill growth." \
  --raw-output "The session improves product framing and creates a practice loop for the Personal Cognitive Garden." \
  --reject \
  --review-note "Too vague to preserve as a durable garden node."
```

List the local PCG Inbox:

```bash
python plugins/ls-personal-cognitive-garden/scripts/route_gateway.py --inbox
python plugins/ls-personal-cognitive-garden/scripts/route_gateway.py --inbox --status proposed
python plugins/ls-personal-cognitive-garden/scripts/route_gateway.py --inbox --status rejected
```

## Session Continuity Use Case

If a user asks Codex or Claude to continue a prior task without enough context, LS should avoid invented continuity.

Example:

```text
User: continue from that PR
Agent risk: implements from an assumed PR state
LS continuity event: missing_pr_context
Decision: hold_until_context
Repair: ask for PR URL, PR number, or exact change set
```

This turns a model behavior — asking for context — into a portable local artifact that the next agent can inspect.

Generate a continuity event without contacting the remote gateway:

```bash
python plugins/ls-personal-cognitive-garden/scripts/route_gateway.py \
  --prompt "continue from that PR" \
  --raw-output "I will update the files now" \
  --continuity \
  --skip-remote-gateway
```

Append continuity events to JSONL for an audit report:

```bash
python plugins/ls-personal-cognitive-garden/scripts/route_gateway.py \
  --prompt "continue from that PR" \
  --raw-output "I will update the files now" \
  --continuity \
  --emit-continuity-event \
  --continuity-jsonl artifacts/session_continuity_events.jsonl \
  --skip-remote-gateway
```

## Safety Boundary

The plugin should never treat a Personal Cognitive Garden proposal as durable state. The expected safe default is:

```text
status: proposed
requires_human_review: true
durable_state_allowed: false
sharing_scope: private
```

The person owns the garden. Agents may propose updates. Governance decides what becomes durable state.

Continuity repair has a matching boundary:

```text
Do not continue from inferred context when the last shared point is missing or unsafe.
```
