from __future__ import annotations

from codex.cognitive.workspace.merit import MeritEngine


def test_merit_engine_narrative_alignment() -> None:
    engine = MeritEngine()
    aggregated = {
        "self_model": {"fragmentation": 0.0},
        "affective": {"energy": 0.8},
        "identity": {"preferences": {"smooth_runtime": 0.6}},
        "capu": {"logits_confidence_margin": 0.7},
        "narrative": {
            "timeline": [
                {
                    "system_state": "stable",
                    "decision_choice": "dummy-llm",
                },
                {
                    "system_state": "stable",
                    "decision_choice": "dummy-llm",
                },
                {
                    "system_state": "stable",
                    "decision_choice": "dummy-llm",
                },
            ]
        },
    }

    scores = engine.score(aggregated)

    assert scores["narrative_alignment"] == 0.65
