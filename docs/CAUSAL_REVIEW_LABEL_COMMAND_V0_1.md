# LS Causal Review Label Command v0.1

## Command

A repository maintainer starts the protected causal ensemble by adding this label to an open,
non-draft pull request:

```text
causal-review
```

The label is the command envelope. The workflow removes it after the run, so a maintainer can add
it again to review a later exact head.

## Authorization

The workflow is loaded from protected `main` through `pull_request_target` and accepts the command
only when all conditions hold:

- target branch is `main`;
- label name is exactly `causal-review`;
- PR is not draft;
- head repository equals `safal207/LS`;
- PR author association is `OWNER`, `MEMBER`, or `COLLABORATOR`.

GitHub label permissions provide the command-side maintainer boundary. The workflow still performs
its own PR/head/branch/patch verification before reading model credentials.

## Execution

```text
add causal-review label
  → protected main workflow definition
  → exact GitHub patch collection
  → pre-secret target verification
  → CodeRabbit and Qodo adaptation
  → blind Grok, DeepSeek, and Codex runner
  → post-model target verification
  → provisional ensemble report
  → seven-day evidence artifact
  → remove causal-review label
```

The native runner is [`tools/run_native_causal_reviewers.sh`](../tools/run_native_causal_reviewers.sh).
Missing secrets produce explicit `NOT_RUN/UNVERIFIED` artifacts. A provider failure cannot appear as
a successful zero-finding review.

## Why label-triggered

The label avoids three unreliable or expensive patterns:

- connector-created comments that may not produce observable Actions events;
- automatic model calls on every push;
- cross-run reconstruction through optional `workflow_run` PR metadata.

It also makes cost and data-egress intent explicit: a maintainer chooses the exact PR head to send
to configured model providers.

## Authority

The command is advisory only. It cannot approve, block, or merge a pull request. Exact findings and
incomplete lanes still require human adjudication.
