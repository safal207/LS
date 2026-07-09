# Observable Grok review command router

This validation note documents the observable `/grok-review` command path.

The command router should make connector-driven command execution visible before the expensive review path runs:

1. `/grok-review` is posted on a pull request.
2. The workflow starts from `issue_comment`.
3. `Resolve review request` posts an acknowledgement comment with marker `<!-- grok-review-command-ack -->`.
4. If trusted, the workflow continues through PR validation, patch preparation, Grok review generation, summary/artifact persistence, and best-effort advisory comment upsert.
5. If not trusted, the workflow posts an ignored acknowledgement with the reason and stops without calling Grok.

This avoids silent command skips and gives the GitHub connector a stable observable signal.

Validation note: this file can be touched to retrigger PR checks when a prior run is cancelled by GitHub concurrency before the review path completes.
