# E6 Live Model Pilot

Status: **live_model_pilot.v0.2** — multi-actor route calling with **Route Memory v0**.

The pilot now bridges deterministic LS network probes to **live multi-actor calls**
(Ollama, Gonka, MiMo) and persists successful routes to durable memory.

```text
capture one answer route
-> score answer quality
-> attach roster readiness
-> attach conductor trajectory context
-> call multiple actors with roles (executor, designer, consumer...)
-> compare route quality vs single answer
-> persist winning route to Route Memory v0
-> emit an audit-ready route event
```

This does not train a model, rank a model, or prove production safety. It shows
whether LS can turn a live or sample model answer into a comparable route event,
and whether the network remembers successful paths for reuse.

## Run It

Safe sample mode:

```bash
python scripts/run_live_model_pilot.py
python scripts/run_live_model_pilot.py --json
```

Configured live route (single actor):

```bash
python scripts/run_live_model_pilot.py --live --json --max-tokens 180
```

## What It Measures (v0.2)

The pilot combines:

- **answer quality** from the local quality proxy;
- **available actor ratio** from the roster probe;
- **conductor trajectory context** from `network_trajectory.v0.2`;
- **multi-actor route probe** (if `--live`): calls all ready actors (Ollama, Gonka, MiMo) with
  assigned roles (executor, designer, consumer, planner, verifier, risk_critic, approver);
- **route comparison**: multi-actor `best` quality vs single-answer quality (`route_won_vs_single`);
- **Route Memory v0**: on `live` + winning route, persists via `TrailNetworkBridge.record_outcome()`
  — sets `durable_state_written = True` and generates a `route_key` for future recall.

Reference sample output:

```text
decision: sample_pipeline_ready
pilot_precision_proxy: 0.5590
ready actors: codex-self-use, local-qwen-light, human_operator
route event: e6-...
route memory: available=true, used=false
```

Reference live output (fragment):

```text
decision: live_route_captured
Multi-actor route WON vs single answer
  best route quality: 0.8210
  avg route quality: 0.7642
Route key: live_model_pilot/a1b2c3d4e5f6>gonka>local-qwen>mimo
Route memory: persisted
```

## Route Memory v0

When `--live` is used and the multi-actor route beats the single answer
(`route_won_vs_single = True`), the pilot:

1. Calls `bridge.submit_contribution()` for each actor with their quality scores.
2. Calls `bridge.record_outcome()` to persist the full route in `RouteStatsStore`.
3. Sets `route_memory.durable_state_written = True`.
4. Generates a `route_key = live_model_pilot/{question_hash}>{actor1}>{actor2}...`.

On subsequent runs with the same question and actors, the pilot checks for
existing routes via `bridge.recommend_route()`. If found, it reports the
cached route health without re-probing all actors.

## Boundary

By default the pilot:

- does not call a live model unless `--live` is passed;
- does not call Gonka/MiMo unless their API keys are configured;
- writes durable route memory only when `--live` and the multi-actor route wins;
- does not allow external actions;
- does not publish private prompts or secrets.

Route memory contents can be inspected at `data/graph_memory/routes.json`.
