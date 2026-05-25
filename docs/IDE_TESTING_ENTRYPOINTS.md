# IDE Testing Entrypoints

Status: **lightweight contributor entrypoints for VS Code, Cursor, OpenCode, and similar IDE agents**.

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

## OpenCode Entry

The repository includes `opencode.json` with:

- `ls-network-probes` MCP server: `python -m ls.agent_shell.mcp_server`
- `/ls-precision-report <runner>`: prepares a contributor report for GitHub
- `/ls-probe-roster`: shows ready and unavailable LS actors
- `/ls-probe-precision`: shows the network precision gain metrics
- `/ls-probe-trajectory 6`: shows precision velocity across repeated cycles
- `/ls-probe-conductor-noise`: tests whether conductor ordering survives noisy reasons
- `/ls-live-pilot`: captures a sample route event, or a live one when requested

Recommended first command inside OpenCode:

```text
/ls-precision-report your-github-handle
```

Then paste `reports/network_precision_contributor_report.md` into the public
contributor issue.

## Available Tasks

| Task | What it does | Output |
| --- | --- | --- |
| `LS: Prepare Contributor Report` | Builds a copy-paste Markdown report. | `reports/network_precision_contributor_report.md` |
| `LS: Prepare Contributor Report JSON` | Builds the same report as machine-readable JSON. | `reports/network_precision_contributor_report.json` |
| `LS: Network Precision Test` | Runs the network precision gain probe. | terminal JSON |
| `LS: Model Roster Probe` | Lists which LS actors are ready or unavailable. | terminal JSON |
| `LS: Live Model Roster Probe` | Calls the configured live model route. | terminal JSON |
| `LS: Route Stability Probe` | Runs the Nash-style route-stability proxy. | terminal JSON |
| `LS: Network Trajectory Probe` | Runs the precision velocity over N cycles. | terminal JSON |
| `LS: Conductor Noise Robustness Probe` | Runs the multi-seed noisy-reason robustness check. | terminal JSON |
| `LS: Live Model Pilot` | Captures a sample route event with roster and conductor context. | terminal JSON |

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

Network trajectory probe:

```bash
python scripts/run_network_trajectory_demo.py --cycles 6 --json
```

Conductor noise robustness probe:

```bash
python scripts/run_conductor_noise_robustness_demo.py --cycles 6 --seeds 12 --json
```

Live model pilot:

```bash
python scripts/run_live_model_pilot.py --json
python scripts/run_live_model_pilot.py --live --json --max-tokens 180
```

To include the full JSON inside the Markdown report:

```bash
python scripts/prepare_network_precision_contributor_report.py \
  --output reports/network_precision_contributor_report.md \
  --include-full-json
```

## MCP Tools (IDE-Agent Entry)

Any MCP-compatible client (OpenCode, Cursor, Claude Desktop, Codex, Copilot) can call
network precision probes as tools instead of running CLI commands:

| Tool | What it does |
| --- | --- |
| `ls_run_network_precision_probe` | Run the network precision gain probe and return JSON metrics. |
| `ls_run_model_roster_probe` | Probe which LS actors are ready or unavailable. Pass `{"live": true}` to call the configured model route. |
| `ls_prepare_contributor_report` | Run all probes and compile a full contributor report payload. Pass `{"runner": "your-handle"}` to identify the run. |
| `ls_run_network_trajectory_probe` | Run the precision velocity over repeated cycles. Pass `{"cycles": 6}`. |
| `ls_run_live_model_pilot` | Capture a sample or live route event. Pass `{"live": true}` only when model calls are intended. |

### Connect from an MCP client

The MCP stdio server listens on stdin/stdout:

```bash
python -m ls.agent_shell.mcp_server
```

Or use the HTTP transport (default port 8042):

```bash
python -c "from ls.agent_shell.mcp_http import run_http_server; run_http_server()"
```

### Example: call a probe from another agent

```python
import json, subprocess, sys

request = json.dumps({
    "action": "tools/call",
    "name": "ls_run_network_precision_probe",
    "arguments": {}
}) + "\n"

proc = subprocess.run(
    [sys.executable, "-m", "ls.agent_shell.mcp_server"],
    input=request, capture_output=True, text=True, check=True
)
result = json.loads(proc.stdout.strip())["result"]
print(result["network_precision"]["decision"])
```

### Example: prepare a contributor report from an IDE agent

```python
request = json.dumps({
    "action": "tools/call",
    "name": "ls_prepare_contributor_report",
    "arguments": {"runner": "my-agent"}
}) + "\n"
```

The agent receives the same payload that would be written to
`reports/network_precision_contributor_report.md`.

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
