# CI Node Mesh

CI Node Mesh is the LS model for treating repositories, pull requests, workflow runs, artifacts, and comments as a distributed execution-and-evidence layer.

## Core idea

```text
Git = history
CI = computation
Artifacts = evidence
Comments = interface
Context exports = agent memory
```

This is part of the Internet CI / CI Node Mesh epic in #846.

## Why this exists

The LS project needs a connector-safe way for agents and contributors to:

- request advisory review work;
- observe whether CI accepted the request;
- store route evidence;
- export reusable context for future agents and repositories;
- distinguish raw facts from derived interpretations.

## Current winning route

The current validated route is:

```text
command PR
  -> pull_request event
  -> command JSON
  -> source diagnostic marker
  -> target acknowledgement marker
  -> advisory Grok review
  -> target result marker
```

Route export:

```text
.ci_exchange/routes/grok-review-command-bus.route.json
```

Observable markers:

```text
grok-review-command-bus-source-diagnostic
grok-review-command-bus-ack
grok-review-command-bus-result
```

Evidence:

- #847: validation-only command PR;
- #848: merged switch to pull_request command-bus route;
- workflow run 29027359506: successful smoke run.

## Known non-winning routes

Earlier experiments did not provide reliable visible acknowledgement in this connector setup:

- connector-created issue comment command;
- connector-created push to a command branch;
- pull_request_target command PR.

These are recorded as route evidence and anti-pattern context rather than deleted from history.

## Safety boundaries

- CI evidence is not merge authority.
- Review output is advisory unless a human explicitly promotes it.
- Imported context is evidence, not truth.
- Every exported route should include confidence and applicability boundaries.

## Next steps

- Add more node manifests as the protocol stabilizes.
- Generate `agent_context.latest.json` from route and memory exports.
- Add validation for `.ci_nodes` and `.ci_exchange` JSON files.
- Reuse this route in external repositories and record whether it transfers cleanly.
