import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from codex.causal_memory.amygdala import Amygdala


def test_fuzzy_smooth_transitions() -> None:
    amygdala = Amygdala(smoothing=0.35, hysteresis=0.06)
    inputs = [
        (0.92, 0.15, 0.05, 0.2),
        (0.74, 0.35, 0.08, -0.1),
        (0.58, 0.45, 0.12, -0.2),
        (0.46, 0.55, 0.16, -0.3),
        (0.38, 0.65, 0.22, -0.45),
        (0.3, 0.75, 0.28, -0.55),
    ]

    scores: list[float] = []
    levels: list[str] = []
    for resonance, axis, delta_axis, affect in inputs:
        decision = amygdala.evaluate(
            new_resonance=resonance,
            axis_position=axis,
            delta_axis=delta_axis,
            affect=affect,
        )
        scores.append(decision.protection_score)
        levels.append(decision.protection_level)

    deltas = [abs(scores[i] - scores[i - 1]) for i in range(1, len(scores))]
    assert max(deltas) < 0.45
    assert scores[0] < scores[-1]
    assert levels[0] in {"open", "mild_protection"}
    assert levels[-1] in {"strong_protection", "full_protection"}


def test_fuzzy_centering_behavior() -> None:
    amygdala = Amygdala(adaptation_rate=0.05)

    for _ in range(10):
        amygdala.evaluate(
            new_resonance=0.15,
            axis_position=0.9,
            delta_axis=0.7,
            affect=-0.85,
        )

    high_state = amygdala.state

    for _ in range(20):
        amygdala.evaluate(
            new_resonance=0.95,
            axis_position=0.1,
            delta_axis=0.05,
            affect=0.1,
        )

    recent_states = [float(item["state"]) for item in list(amygdala.history)[-10:]]
    mean_state = sum(recent_states) / len(recent_states)

    assert high_state > 0.55
    assert mean_state < high_state
    assert 0.05 <= mean_state <= 0.62


def test_fuzzy_adaptation_effect() -> None:
    amygdala = Amygdala(adaptation_rate=0.05)

    for _ in range(24):
        amygdala.evaluate(
            new_resonance=0.25,
            axis_position=0.93,
            delta_axis=0.72,
            affect=-0.9,
        )

    assert len(amygdala.history) >= 20
    assert amygdala.protection_shift <= 0.0

    for _ in range(26):
        amygdala.evaluate(
            new_resonance=0.97,
            axis_position=0.08,
            delta_axis=0.03,
            affect=0.2,
        )

    assert -0.15 <= amygdala.protection_shift <= 0.15
    assert 0.1 <= amygdala.smoothing <= 0.95


def test_fuzzy_strong_threat_protection() -> None:
    amygdala = Amygdala()
    decision = amygdala.evaluate(
        new_resonance=0.35,
        axis_position=0.4,
        delta_axis=0.15,
        affect=-0.9,
    )

    assert decision.protection_level in {"strong_protection", "full_protection"}
    assert decision.protection_score > 0.75


def test_fuzzy_mild_protection() -> None:
    amygdala = Amygdala()
    decision = amygdala.evaluate(
        new_resonance=0.55,
        axis_position=0.35,
        delta_axis=0.12,
        affect=-0.25,
    )

    assert decision.protection_level == "mild_protection"
    assert 0.35 < decision.protection_score < 0.62


def test_fuzzy_zero_strength_fallback() -> None:
    amygdala = Amygdala()
    decision = amygdala.evaluate(
        new_resonance=1.0,
        axis_position=0.1,
        delta_axis=0.0,
        affect=1.0,
    )

    assert decision.protection_level == "open"
    assert decision.protection_score == 0.0
