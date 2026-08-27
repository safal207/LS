# Grok command bus PR-backed fallback

PR #845 adds a PR-backed fallback for the Grok command bus.

Why:

- PR #844 added a push/file command bus.
- Post-merge smoke showed the command file was written to `ci/grok-review-command`, but no connector-visible acknowledgement appeared on target PR #838.
- Connector-created pull request events are already proven reliable in this repository.

Fallback:

- Keep the push trigger.
- Add `pull_request_target` for PRs that change `.github/grok-review-command.json` into `main`.
- Restrict the job to same-repository branches whose head ref starts with `ci/grok-review-command`.
- Do not check out or execute PR code.
- Read only the command file from the PR head SHA via GitHub API.
- Publish the same acknowledgement/result markers to the target PR.

Expected markers:

- `grok-review-command-bus-ack`
- `grok-review-command-bus-result`
