# LS Agent Shell CLI

`LS Agent Shell` is the operator-facing CLI for the MCP facade and task runtime.

It covers three layers:

1. Task execution and approval flow
2. MCP serving over `stdio` or `http`
3. LTP export and replay inspection bridge

## Runtime layout

By default the CLI uses:

```text
.ls_agent/
  runtime.db
  artifacts/
  ltp/
```

You can override the root with:

```bash
ls-agent ... --runtime-root .ls_agent
```

## Core task flow

Create a plan:

```bash
ls-agent plan "Review PR #387 and write feedback" --mode read-only
```

Run a task:

```bash
ls-agent run "Prepare investor opening slide for LS" --approval safe-write
```

Inspect a task:

```bash
ls-agent inspect task-12345678
```

Approve or reject a waiting step:

```bash
ls-agent approve task-12345678 task-12345678-step-4
ls-agent reject task-12345678 task-12345678-step-4 --reason "Need diff first"
```

Show task queue and approvals:

```bash
ls-agent list --status waiting_approval
ls-agent approvals --task-id task-12345678
```

## Artifacts

List artifacts for a task:

```bash
ls-agent artifacts task-12345678
```

Show one artifact:

```bash
ls-agent artifact artifact-12345678
```

Open one artifact in the OS handler:

```bash
ls-agent artifact-open artifact-12345678
```

## Serving MCP

Serve over stdio:

```bash
ls-agent serve --transport stdio
```

Serve over HTTP:

```bash
ls-agent serve --transport http --host 127.0.0.1 --port 8042
```

HTTP health response includes the runtime root:

```text
GET /health
```

## LTP bridge

The CLI can export task traces into an LTP-compatible JSONL format and run
`L-THREAD` inspection tooling on top of those traces.

Default external repo lookup:

```text
Desktop/_lthread_proto
```

You can override it with:

```bash
ls-agent ltp-inspect task-12345678 --ltp-repo-root C:/path/to/L-THREAD
```

Requirements for live inspect:

```bash
cd C:/path/to/L-THREAD
pnpm install
```

`ltp-inspect` and `ltp-inspect-all` run the local inspector directly through
`node + node_modules/ts-node/dist/bin.js`, so the repo must already have its
dependencies installed.

Export one task trace:

```bash
ls-agent ltp-export task-12345678
```

Inspect one task trace through `ltp inspect`:

```bash
ls-agent ltp-inspect task-12345678
```

Batch inspect all waiting approvals through the local LTP toolchain:

```bash
ls-agent ltp-inspect-all --status waiting_approval
```

Batch export all waiting approvals:

```bash
ls-agent ltp-export-all --status waiting_approval
```

This writes one JSONL file per task into:

```text
.ls_agent/ltp/batch/
```

## Recommended operator loop

```bash
ls-agent list --status waiting_approval
ls-agent inspect task-12345678
ls-agent approvals --task-id task-12345678
ls-agent ltp-inspect task-12345678
ls-agent ltp-inspect-all --status waiting_approval
ls-agent approve task-12345678 task-12345678-step-4
ls-agent artifacts task-12345678
```
