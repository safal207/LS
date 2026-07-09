# Grok review command validation

This branch adds an `issue_comment` slash-command entrypoint for the Grok PR Review workflow.

Intended command:

```text
/grok-review
```

The command lets the GitHub connector trigger Grok review by adding a trusted PR comment instead of relying on manual `workflow_dispatch` or synthetic validation PRs.

The workflow also preserves generated reviews in the job summary and artifact when comment publication fails.
