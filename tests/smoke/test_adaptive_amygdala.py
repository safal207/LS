import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from codex.causal_memory.amygdala import Amygdala


def test_smooth_transitions_no_oscillation() -> None:
    amygdala = Amygdala(smoothing=0.35, hysteresis=0.08)
    states: list[float] = []

    for resonance, affect in [(0.9, 0.0), (0.35, -0.3), (0.88, 0.1), (0.4, -0.2), (0.9, 0.0)]:
        decision = amygdala.evaluate(
            new_resonance=resonance,
            axis_position=0.25,
            delta_axis=0.1,
            affect=affect,
        )
        states.append(decision.state)

    max_jump = max(abs(states[i] - states[i - 1]) for i in range(1, len(states)))
    assert all(0.0 <= state <= 1.0 for state in states)
    assert max_jump < 0.25


def test_adaptation_over_time() -> None:
    amygdala = Amygdala(adaptation_rate=0.05)

    for _ in range(20):
        amygdala.evaluate(
            new_resonance=0.2,
            axis_position=0.95,
            delta_axis=0.7,
            affect=-0.9,
        )

    assert len(amygdala.history) >= 20
    assert -0.95 <= amygdala.threat_affect <= -0.5
    assert 0.1 <= amygdala.smoothing <= 0.95


def test_centering_behavior() -> None:
    amygdala = Amygdala(adaptation_rate=0.05)

    # Push state high first.
    for _ in range(8):
        amygdala.evaluate(
            new_resonance=0.1,
            axis_position=0.95,
            delta_axis=0.8,
            affect=-0.9,
        )

    high_state = amygdala.state

    # Then feed calm interactions and ensure it drifts back toward center.
    for _ in range(18):
        amygdala.evaluate(
            new_resonance=0.95,
            axis_position=0.1,
            delta_axis=0.05,
            affect=0.05,
        )

    recent_states = [float(item["state"]) for item in list(amygdala.history)[-10:]]
    centered_mean = sum(recent_states) / len(recent_states)

    assert high_state > 0.5
    assert centered_mean < high_state
    assert 0.05 <= centered_mean <= 0.6
