from agent.cognitive_illusions import CognitiveIllusionDetector


def test_detect_false_causation():
    detector = CognitiveIllusionDetector(
        {
            "causal_edges": [
                {
                    "cause": "tool_use",
                    "effect": "high_quality_answer",
                    "confidence": 0.8,
                    "evidence_count": 2,
                }
            ]
        }
    )

    warnings = detector.detect_false_causation()

    assert len(warnings) == 1
    assert warnings[0]["type"] == "false_causation"


def test_detect_overconfidence():
    detector = CognitiveIllusionDetector(
        {
            "beliefs": [
                {
                    "content": "Using tools improves answer quality",
                    "confidence": 0.9,
                    "evidence_count": 3,
                }
            ]
        }
    )

    warnings = detector.detect_overconfidence()

    assert len(warnings) == 1
    assert warnings[0]["type"] == "overconfidence"


def test_detect_context_confusion():
    detector = CognitiveIllusionDetector(
        {
            "causal_graph": {
                "edges": [
                    {
                        "cause": "tool_use",
                        "effect": "high_quality_answer",
                        "confidence": 0.7,
                        "evidence_count": 10,
                        "context_specific": True,
                        "treated_as_universal": True,
                        "context": "coding_tasks",
                    }
                ]
            }
        }
    )

    warnings = detector.detect_context_confusion()

    assert len(warnings) == 1
    assert warnings[0]["type"] == "context_confusion"


def test_generate_warnings_aggregates_all_types():
    detector = CognitiveIllusionDetector(
        {
            "beliefs": [
                {
                    "content": "Using tools improves answer quality",
                    "confidence": 0.9,
                    "evidence_count": 3,
                }
            ],
            "causal_edges": [
                {
                    "cause": "tool_use",
                    "effect": "high_quality_answer",
                    "confidence": 0.8,
                    "evidence_count": 2,
                    "context_specific": True,
                    "treated_as_universal": True,
                }
            ],
        }
    )

    warnings = detector.generate_warnings()
    warning_types = {item["type"] for item in warnings}

    assert warning_types == {"overconfidence", "false_causation", "context_confusion"}


def test_adjust_confidence_lowers_confidence_and_marks_uncertain():
    detector = CognitiveIllusionDetector(
        {
            "beliefs": [{"content": "belief", "confidence": 0.9, "evidence_count": 1}],
            "causal_edges": [
                {
                    "cause": "x",
                    "effect": "y",
                    "confidence": 0.8,
                    "evidence_count": 1,
                    "context_specific": True,
                    "treated_as_universal": True,
                }
            ],
        }
    )

    adjusted = detector.adjust_confidence()

    assert adjusted["beliefs"][0]["confidence"] == 0.7
    assert adjusted["beliefs"][0]["uncertain"] is True
    assert adjusted["causal_edges"][0]["confidence"] == 0.6
    assert adjusted["causal_edges"][0]["uncertain"] is True
