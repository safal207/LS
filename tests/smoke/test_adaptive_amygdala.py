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


def test_learning_over_time() -> None:
    amygdala = Amygdala()

    for _ in range(8):
        amygdala.learn_from_outcome(stable_interaction=True, user_engaged=True)
    lowered_bias = amygdala.adaptive_bias

    for _ in range(8):
        amygdala.learn_from_outcome(stable_interaction=False, user_engaged=False)

    assert lowered_bias < 0.0
    assert amygdala.adaptive_bias > lowered_bias


def test_harmony_chaos_balance() -> None:
    amygdala = Amygdala()

    calm = amygdala.evaluate(
        new_resonance=0.95,
        axis_position=0.2,
        delta_axis=0.05,
        affect=0.1,
    )

    threat = calm
    for _ in range(6):
        threat = amygdala.evaluate(
            new_resonance=0.15,
            axis_position=0.95,
            delta_axis=0.8,
            affect=-0.9,
        )

    assert calm.allowed is True
    assert calm.state < 0.65
    assert threat.state > calm.state
    assert threat.allowed is False
