# Agent Context Export

`agent_context.latest.json` is the compact advisory memory file that an agent should read before working on LS CI command-bus tasks.

Path:

```text
.ci_exchange/agent_context.latest.json
```

## Purpose

The file answers four practical questions:

1. What route is known to work?
2. What routes should not be retried without new evidence?
3. What should the next agent do first?
4. What are the authority boundaries?

## Current working route

```text
same-repository command PR
  -> pull_request workflow event
  -> .github/grok-review-command.json
  -> source diagnostic marker
  -> target acknowledgement marker
  -> advisory review
  -> target result marker
```

Markers:

```text
grok-review-command-bus-source-diagnostic
grok-review-command-bus-ack
grok-review-command-bus-result
```

## Known non-winning routes

The context currently records these routes as non-winning in the observed LS connector setup:

- connector-created issue comment command;
- connector-created command branch update;
- pull_request_target command PR.

They are not erased. They remain useful evidence for future routing decisions.

## Authority boundary

This file is advisory memory. It does not approve, merge, deploy, or replace human review.

## Maintenance rule

Update this file when a route changes, when new evidence invalidates a prior claim, or when a new command bus becomes more reliable than the current one.
