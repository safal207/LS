# IDE Testing Entrypoints

Status: **lightweight contributor entrypoints for VS Code, Cursor, and similar IDEs**.

The goal is to let contributors test LS without learning the full architecture
first. Open the repository in an IDE, run one task, and paste the generated
report into the contributor issue.

Public collection issue:

- [Contributor call: test Network Precision Gain on your models](https://github.com/safal207/LS/issues/571)

## Best First Click

In VS Code or Cursor:

1. Open the LS repository folder.
2. Open **Terminal -> Run Task...**.
3. Choose **LS: Prepare Contributor Report**.
4. Copy `reports/network_precision_contributor_report.md` into the contributor issue.

The task runs the same probes used by the public Network Precision Contributor
Call and writes a Markdown report with environment, actor readiness, and metric
values.

## Available Tasks

| Task | What it does | Output |
| --- | --- | --- |
| `LS: Prepare Contributor Report` | Builds a copy-paste Markdown report. | `reports/network_precision_contributor_report.md` |
| `LS: Prepare Contributor Report JSON` | Builds the same report as machine-readable JSON. | `reports/network_precision_contributor_report.json` |
| `LS: Network Precision Test` | Runs the network precision gain probe. | terminal JSON |
| `LS: Model Roster Probe` | Lists which LS actors are ready or unavailable. | terminal JSON |
| `LS: Live Model Roster Probe` | Calls the configured live model route. | terminal JSON |
| `LS: Route Stability Probe` | Runs the Nash-style route-stability proxy. | terminal JSON |

`LS: Live Model Roster Probe` is opt-in because it may call configured local or
hosted model backends.

## CLI Equivalent

If the IDE task runner is not available:

```bash
python scripts/prepare_network_precision_contributor_report.py \
  --output reports/network_precision_contributor_report.md
```

JSON form:

```bash
python scripts/prepare_network_precision_contributor_report.py \
  --json \
  --output reports/network_precision_contributor_report.json
```

Live model route:

```bash
python scripts/prepare_network_precision_contributor_report.py \
  --live-roster \
  --output reports/network_precision_contributor_report.md
```

To include the full JSON inside the Markdown report:

```bash
python scripts/prepare_network_precision_contributor_report.py \
  --output reports/network_precision_contributor_report.md \
  --include-full-json
```

## What This Gives The Network

Each contributor report adds one environment-tested route sample:

```text
environment
-> available actors
-> cooperative precision metrics
-> route-stability signal
-> reusable evidence for improving the network
```

This helps LS learn where a route is stable, where it is brittle, and which
model/runtime combinations should become future fixtures.

## Boundary

This is not a model leaderboard. A report should not claim that one model is
globally better than another. The useful claim is narrower:

```text
On this environment, this cooperative route produced these visible precision
signals under the current LS probe.
```
