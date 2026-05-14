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

## What It Does

- Routes raw agent output to a local LS gateway.
- Preserves LS action safety behavior.
- Shows when a draft creates a proposed Personal Cognitive Garden update.
- Keeps the safe default: proposed updates do not write durable memory automatically.

## Demo Path

For the short end-to-end demo, see:

- [`docs/CODEX_PLUGIN_DEMO.md`](../../docs/CODEX_PLUGIN_DEMO.md)

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

List the local PCG Inbox:

```bash
python plugins/ls-personal-cognitive-garden/scripts/route_gateway.py --inbox
python plugins/ls-personal-cognitive-garden/scripts/route_gateway.py --inbox --status proposed
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
