# Grok PR Review Command Bus

This document describes the connector-safe command path for the advisory Grok PR Review workflow.

## Why this exists

The GitHub connector can create pull-request comments, but connector-created `issue_comment` events did not produce a reliable, connector-visible workflow acknowledgement.

The command bus uses a path that is already connector-safe: committing a command file to a dedicated branch.

```text
GitHub connector
→ update .github/grok-review-command.json
→ push to ci/grok-review-command
→ Grok PR Review Command Bus workflow
→ target PR acknowledgement
→ advisory review result comment
```

## Command branch

```text
ci/grok-review-command
```

## Command file

```text
.github/grok-review-command.json
```

## Command shape

```json
{
  "command": "grok-review",
  "target_pr": 838,
  "requested_by": "connector",
  "nonce": "2026-07-09T05:30:00Z"
}
```

## Observable signals

The workflow posts a target PR acknowledgement comment containing:

```text
grok-review-command-bus-ack
```

The workflow posts a final advisory review comment containing:

```text
grok-review-command-bus-result
```

## Safety boundaries

- The command workflow only runs on pushes to `ci/grok-review-command`.
- The workflow only reacts to changes to `.github/grok-review-command.json`.
- The command parser accepts only `command: grok-review`.
- `target_pr` must be a positive integer.
- PR code is not checked out or executed.
- The workflow reviews patch text via `gh pr diff`.
- Result publication is advisory and does not block merge.

## Operational flow

1. Create or update branch `ci/grok-review-command` from `main`.
2. Write `.github/grok-review-command.json` with a fresh nonce.
3. Wait for `Grok PR Review Command Bus` run.
4. Confirm the target PR contains `grok-review-command-bus-ack`.
5. Confirm the target PR contains `grok-review-command-bus-result`.

## Relation to `/grok-review`

The `/grok-review` comment path remains useful for humans using GitHub UI.

The command bus is the preferred automation path for connector-driven dispatch.
