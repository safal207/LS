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

## Generator

The latest context is generated from CI Exchange metadata:

```bash
python tools/generate_agent_context.py
```

To verify the committed file is still consistent with the generator:

```bash
python tools/generate_agent_context.py --check
```

The generator currently reads:

```text
.ci_exchange/routes/grok-review-command-bus.route.json
.ci_exchange/contexts/connector-safe-command-bus.context.json
```

## Authority boundary

This file is advisory memory. It does not approve, merge, deploy, or replace human review.

## Maintenance rule

Update the underlying route/context exports first, then regenerate this file. Update this file directly only when recording a temporary transition that the generator does not support yet.
