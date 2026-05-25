---
name: Network Precision Contributor Run
about: Share an LS network precision run from your model, runtime, hardware, or IDE.
title: "[CONTRIBUTOR RUN] Network Precision on "
labels: help wanted, documentation
assignees: ""
---

## Environment

- Runner:
- Date UTC:
- OS:
- Python:
- Hardware:
- Runtime:
- Models:

## How did you run it?

- [ ] VS Code / Cursor task: `LS: Prepare Contributor Pack`
- [ ] OpenCode command: `/ls-contributor-pack`
- [ ] CLI: `python scripts/prepare_contributor_pack.py`
- [ ] VS Code / Cursor task: `LS: Prepare Contributor Report`
- [ ] OpenCode command: `/ls-precision-report`
- [ ] CLI: `python scripts/prepare_network_precision_contributor_report.py`
- [ ] Manual commands from `docs/NETWORK_PRECISION_CONTRIBUTOR_CALL.md`
- [ ] Other:

## Commands

```bash
python scripts/prepare_contributor_pack.py --runner <your-handle>
```

## Results

- single_baseline_score:
- cooperative_route_score:
- full_stack_score:
- measured_route_reward_gain:
- network_precision_gain_over_baseline:
- stack_added_gain_over_cooperation:
- score_ratio_vs_baseline:
- network_decision:
- route_stability_decision:

## Network Trajectory

- trajectory_cycles:
- observer_delta_final:
- observer_velocity_multiplier:
- trajectory_gain_over_baseline:
- precision_velocity:
- drift_reduction:
- resonance_gain:

## Conductor Noise Robustness

- conductor_noise_decision:
- conductor_noise_pass_rate_at_0_25:
- conductor_noise_margin_at_0_25:
- conductor_noise_moderate_supported:
- conductor_noise_high_noise_degrades:

## Live Model Pilot / Route Memory

- live_model_pilot_decision:
- live_model_pilot_mode:
- live_model_pilot_score:
- live_model_pilot_event:
- route_won_vs_single:
- route_memory_key:
- route_memory_persisted:
- route_memory_health:

## Ready Actors

- 

## Unavailable Actors

- 

## Notes

What was surprising, slow, brittle, useful, or different in your model/runtime?

## Boundary Check

- [ ] I did not include API keys, secrets, private prompts, customer data, or proprietary code.
- [ ] I understand this is not a global model leaderboard.
- [ ] I understand this is not a formal proof of Nash equilibrium.
- [ ] I am sharing this as a reproducible contributor run for improving cooperative precision evidence.
