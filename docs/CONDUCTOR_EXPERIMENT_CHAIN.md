# Conductor Experiment Chain

Status: research task chain for the LS Cooperative Precision Network.

## Research Question

Does the reason-aware conductor improve network route precision because it uses
causal reasons, or because the deterministic probe simply grants an extra score
to the conductor mode?

Narrow claim under test:

```text
Reason-aware conductor improves cooperative route precision over repeated cycles
more than observer-only, no-reason, stale-reason, or inverted-reason controls.
```

This is not a claim that models are trained, conscious, or globally safe. The
claim is smaller and stronger: the network can measure whether remembered
causes help the next route become more precise.

## Chain Of Experiments

### E0. Reproduce Reference Trajectory

Goal: make sure the current reference run still holds.

Command:

```bash
python scripts/run_network_trajectory_demo.py --cycles 6
```

Expected current reference:

```text
no_observer: 0.7436 -> 0.7834
observer:    0.7436 -> 0.8631
conductor:   0.7436 -> 0.8698
```

Pass condition: conductor remains above observer and no-observer.

### E1. No-Reason Ablation

Goal: remove reason memory while keeping the same observer state.

Question:

```text
If the conductor has no reasons, does it still improve?
```

Expected: no-reason conductor should collapse to observer-only.

### E2. Stale-Reason Ablation

Goal: apply the previous cycle's reasons to the current cycle.

Question:

```text
Does timing matter, or can any old reason produce the same improvement?
```

Expected: stale reasons may retain some value, but should underperform current
reasons.

### E3. Inverted-Reason Ablation

Goal: apply the opposite correction for the same detected reasons.

Question:

```text
If drift narrows, resonance builds, and lag decreases, what happens when the
conductor pushes the route in the opposite direction?
```

Expected: inverted reasons should underperform no-reason and observer-only.

### E4. Bounded Delta Guard

Goal: verify the conductor cannot inflate scores without limit.

Pass condition: every component remains in `[0.0, 1.0]`, and final precision
does not exceed the reference full-stack maximum unless the metric definition is
explicitly changed.

### E5. Noise And Multi-Seed Robustness

Goal: add controlled perturbations to reason extraction and component values.

Pass condition: conductor advantage survives small noise, but weakens when
causal signals are heavily corrupted.

Runnable probe:

```bash
python scripts/run_conductor_noise_robustness_demo.py --cycles 6 --seeds 12
```

Reference doc:

```text
docs/CONDUCTOR_NOISE_ROBUSTNESS.md
```

### E6. Live Model Pilot

Goal: run the same route protocol with real model outputs from the models
available in the local environment.

Pass condition: LS can produce route events, reason memory, and an audit report
without relying on hidden state.

### E7. Contributor Replication

Goal: let outside contributors run the chain and report their own model stack.

Pass condition: contributors can reproduce the protocol with one command and
submit comparable results.

## First Implemented Experiment

The first runnable ablation is:

```bash
python scripts/run_conductor_ablation_demo.py --cycles 6
```

Regression guard:

```text
python/tests/test_conductor_ablation_demo.py
```

It compares:

```text
reason_aware_conductor
no_reason_conductor
stale_reason_conductor
inverted_reason_conductor
```

Decision rule:

```text
If no_reason, stale_reason, or inverted_reason matches or exceeds
reason_aware_conductor, the reason-aware hypothesis is not supported.
```

## First Results

### 6-cycle run

```text
reason_aware_conductor:   0.8698  delta_vs_observer +0.0067
no_reason_conductor:      0.8631  delta_vs_observer +0.0000
stale_reason_conductor:   0.8654  delta_vs_observer +0.0023
inverted_reason_conductor:0.8564  delta_vs_observer -0.0067
```

Result:

```text
reason_aware_conductor_supported
```

This supports the first narrow claim after conductor v0.2: without reasons, the
conductor collapses to observer-only; inverted reasons make the route worse;
stale reasons keep some value but underperform current reasons.

### 10-cycle stress run

```text
reason_aware_conductor:   0.8653  delta_vs_observer +0.0022
no_reason_conductor:      0.8631  delta_vs_observer +0.0000
stale_reason_conductor:   0.8642  delta_vs_observer +0.0011
inverted_reason_conductor:0.8609  delta_vs_observer -0.0022
```

Result:

```text
reason_aware_conductor_supported
```

This was the first useful failure in v0.1 and is now fixed in v0.2. The
conductor uses reason **kind**, reason **delta**, reason **freshness**, and a
bounded component update. When reason kinds repeat, stale reasons now retain
only part of the gain instead of matching current reasons.

Current conductor rule:

```text
conductor.v0.2 = reason kind + reason delta + reason freshness + bounded update
```

### 20-cycle stress run

```text
reason_aware_conductor:   0.8645  delta_vs_observer +0.0014
no_reason_conductor:      0.8631  delta_vs_observer +0.0000
stale_reason_conductor:   0.8638  delta_vs_observer +0.0007
inverted_reason_conductor:0.8617  delta_vs_observer -0.0014
```

Result:

```text
reason_aware_conductor_supported
```

## Why This Matters

This turns the discovery from a story into a falsifiable path:

```text
models answer
routes remember
observer explains
conductor adjusts
ablation tries to break the explanation
```

If the chain keeps passing, LS gets a sharper research claim:

```text
The network becomes more precise not by making models smarter, but by preserving
and reusing causal route evidence across cycles.
```
