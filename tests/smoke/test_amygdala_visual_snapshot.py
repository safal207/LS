import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from codex.causal_memory.amygdala import Amygdala


def test_visual_snapshot_updates() -> None:
    amygdala = Amygdala()

    amygdala.evaluate(
        new_resonance=0.25,
        axis_position=0.92,
        delta_axis=0.7,
        affect=-0.9,
    )

    snapshot = amygdala.last_snapshot
    assert 0.0 <= float(snapshot["state"]) <= 1.0
    assert snapshot["protection_level"] in {
        "open",
        "mild_protection",
        "strong_protection",
        "full_protection",
    }
    assert float(snapshot["protection_score"]) >= 0.0
    assert float(snapshot["personality_p"]) >= 0.0
    assert float(snapshot["phantom_pain"]) > 0.0
    assert "trigger" in snapshot


def test_phantom_pain_visual_changes_on_resolve() -> None:
    amygdala = Amygdala()
    for _ in range(2):
        amygdala.evaluate(
            new_resonance=0.2,
            axis_position=0.95,
            delta_axis=0.75,
            affect=-0.95,
        )

    pre_resolve = dict(amygdala.last_snapshot)
    amygdala.learn_from_outcome(stable_interaction=True)
    post_resolve = dict(amygdala.last_snapshot)

    assert float(pre_resolve["phantom_pain"]) > float(post_resolve["phantom_pain"])
    assert float(post_resolve["resolution_strength"]) > float(pre_resolve["resolution_strength"])
