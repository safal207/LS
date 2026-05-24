# Model Roster Depth Probe

Status: **implemented probe**.

This probe checks which LS actors are present in the cooperative role market and
which of them can answer live right now for a Depth Economy question.

It keeps two things separate:

- **roster presence**: the actor/model is part of LS architecture;
- **runtime readiness**: the actor/model is configured and available in this
  local environment.

## Why This Exists

Depth Economy says different work needs different depth:

```text
executor correctness:    1 + 1 = 2
designer synergy:        1 + 1 = 3
customer-consumer depth: 1 + 1 = n
```

Before LS routes a task through this ladder, it should know which actors are
actually usable now.

## Run

Dry run, safe for CI:

```bash
python scripts/run_model_roster_depth_probe.py
python scripts/run_model_roster_depth_probe.py --json
```

Live route call:

```bash
PYTHONPATH=.:python:python/modules python scripts/run_model_roster_depth_probe.py --live --json
```

The live mode sends one Depth Economy prompt through the currently configured
LLM backend route and scores the answer with the existing LS quality heuristic.

## Actor Roster

The probe uses the current LS role-market roster:

| Actor | Runtime | Current role use |
| --- | --- | --- |
| `codex-self-use` | current Codex session | route planning |
| `local-qwen` | Ollama `qwen2.5:7b` | draft review / single baseline |
| `local-qwen-light` | Ollama `qwen2.5:1.5b` | evidence fallback |
| `gonka` | configured backend, key required | risk critic |
| `mimo` | configured backend, key required | final reviewer |
| `human_operator` | human review | customer, boundary, consent |

## What The Latest Local Smoke Showed

On the current free local setup:

- Gonka was present in the roster but disabled without `GONKA_ENABLED=true` and
  `GONKA_API_KEY`.
- MiMo was present in the roster but disabled without `MIMO_ENABLED=true` and
  `MIMO_API_KEY`.
- Cloud fallback was disabled without `GROQ_API_KEY`.
- The local route answered through `qwen2.5:1.5b`.
- The Depth Economy answer scored low on thread alignment in the smoke test, so
  it should be used for shallow checks, not for deep L2-L4 routing decisions.

This is useful because it makes the boundary honest:

```text
local model = cheap shallow signal
Codex/human = current deep interpretation and review
Gonka/MiMo = configured future multi-model route once keys are present
```

## Interpretation

This probe does not claim that LS has a fully live multi-model network in every
environment.

It proves that LS can:

- enumerate its own cooperative model roster;
- show which actors are ready now;
- call the active route when requested;
- score the response against the Depth Economy context;
- keep deep memory/action decisions under human/Codex review when the live
  model signal is weak.

That gives contributors a concrete next task: add keys, add local models, or
improve the role route, then rerun the same probe and compare the evidence.
