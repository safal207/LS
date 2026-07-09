# Grok command bus validation

PR #844 introduces a connector-safe Grok command bus.

Validation intent:

- Avoid relying on connector-created `issue_comment` events.
- Use connector-created commits/pushes as the reliable dispatch path.
- Trigger from `.github/grok-review-command.json` on branch `ci/grok-review-command`.
- Publish target PR acknowledgement with marker `grok-review-command-bus-ack`.
- Publish final advisory result with marker `grok-review-command-bus-result`.

This PR should be validated first by normal PR checks. After merge, a post-merge command-bus smoke can update the command file to target an existing open PR.
