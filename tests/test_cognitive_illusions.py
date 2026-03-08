from __future__ import annotations

from modules.agent.cognitive_illusions import CognitiveIllusionDetector


def test_detect_false_causation() -> None:
    detector = CognitiveIllusionDetector(
        {
            "causal_edges": [
                {"cause": "tool_use", "effect": "high_quality_answer", "confidence": 0.8, "evidence_count": 2},
                {"cause": "retrieve_context", "effect": "grounded_answer", "confidence": 0.7, "evidence_count": 5},
            ]
        }
    )

    warnings = detector.detect_false_causation()

    assert len(warnings) == 1
    assert warnings[0]["type"] == "false_causation"
    assert warnings[0]["edge"] == "tool_use → high_quality_answer"


def test_detect_overconfidence() -> None:
    detector = CognitiveIllusionDetector(
        {
            "beliefs": [
                {"content": "Using tools improves answer quality", "confidence": 0.9, "evidence_count": 3},
                {"content": "Structured prompts help", "confidence": 0.7, "evidence_count": 10},
            ]
        }
    )

    warnings = detector.detect_overconfidence()

    assert len(warnings) == 1
    assert warnings[0] == {
        "type": "overconfidence",
        "belief": "Using tools improves answer quality",
        "message": "High confidence with low evidence",
    }


def test_generate_warnings_combines_illusion_types() -> None:
    detector = CognitiveIllusionDetector(
        {
            "beliefs": [
                {"content": "Using tools improves answer quality", "confidence": 0.9, "evidence_count": 3}
            ],
            "causal_edges": [
                {
                    "cause": "structured_reasoning",
                    "effect": "good_answers",
                    "confidence": 0.75,
                    "evidence_count": 2,
                    "is_universal": True,
                    "contexts": ["complex_questions"],
                }
            ],
        }
    )

    warnings = detector.generate_warnings()
    warning_types = {item["type"] for item in warnings}

    assert warning_types == {"overconfidence", "false_causation", "context_confusion"}
