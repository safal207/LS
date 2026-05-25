# Conductor Noise Robustness

Status: deterministic robustness probe for `conductor.v0.2`.

The conductor ablation proved the basic ordering:

```text
fresh reason > stale reason > no reason > inverted reason
```

This probe asks the next question:

```text
Does that ordering survive noisy causal evidence across multiple seeds?
```

## Run It

```bash
python scripts/run_conductor_noise_robustness_demo.py
python scripts/run_conductor_noise_robustness_demo.py --cycles 6 --seeds 12
python scripts/run_conductor_noise_robustness_demo.py --noise-levels 0,0.1,0.25,0.4 --json
```

## What Noise Means

The probe applies deterministic synthetic noise to reason memory:

- some reasons are dropped;
- some reason kinds are mislabelled;
- reason deltas are perturbed up or down;
- the conductor still receives bounded component updates.

This is not adversarial red teaming and not live model learning. It is a
repeatable robustness check for the route-selection mechanism.

## Current Reference

With 6 cycles, 12 seeds, and noise levels `0, 0.1, 0.25, 0.4`:

```text
decision: robust_under_moderate_noise

ordering under test:
fresh noisy reasons > stale noisy reasons > no reasons > inverted noisy reasons
```

Pass condition:

```text
noise <= 0.25 has pass_rate >= 0.80
fresh_minus_stale remains positive
high noise weakens the margin
```

## Why This Matters

The earlier conductor discovery could have been a single deterministic path.
This robustness layer checks whether the same causal route logic survives
reasonable measurement noise.

Narrow claim:

```text
Conductor v0.2 preserves a fresh-reason advantage under moderate synthetic
noise, while high noise reduces the margin.
```
