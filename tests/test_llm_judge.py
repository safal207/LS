from eval.evaluate_resonance import evaluate
from eval.llm_judge import judge_response


def test_judge_returns_scores():
    def handler(_prompt: str) -> str:
        return '{"relevance": 8, "hallucination_risk": 2, "reasoning": "Context directly answers the question."}'

    result = judge_response("q", "ctx", handler)

    assert 0 <= result["relevance"] <= 10
    assert 0 <= result["hallucination_risk"] <= 10


def test_judge_empty_context():
    result = judge_response("q", "   ", lambda _prompt: "should not be called")

    assert result["relevance"] == 0
    assert result["hallucination_risk"] == 10


def test_judge_parse_error_fallback():
    result = judge_response("q", "ctx", lambda _prompt: "not a json response")

    assert result["relevance"] == 0
    assert result["hallucination_risk"] == 10
    assert result["reasoning"] == "Parse error"


def test_judge_handler_exception():
    def failing_handler(_prompt: str) -> str:
        raise RuntimeError("judge boom")

    result = judge_response("q", "ctx", failing_handler)

    assert result["relevance"] == 0
    assert result["hallucination_risk"] == 10
    assert result["reasoning"] == "Judge failed"


def test_evaluate_with_judge_adds_scores(monkeypatch):
    from eval import evaluate_resonance

    monkeypatch.setattr(evaluate_resonance, "TEST_QUESTIONS", ["q1"])
    monkeypatch.setattr(evaluate_resonance, "get_context_for_question", lambda *args, **kwargs: "ctx")
    monkeypatch.setattr(
        evaluate_resonance,
        "_eval_context",
        lambda *args, **kwargs: {"hit_rate": 1, "avg_similarity": 0.5, "top_score": 0.7, "chunks_found": 1},
    )

    report = evaluate(
        "original",
        judge_handler=lambda _prompt: '{"relevance": 9, "hallucination_risk": 1, "reasoning": "Grounded."}',
    )

    assert report["results"][0]["relevance"] == 9
    assert report["results"][0]["hallucination_risk"] == 1
    assert report["summary"]["avg_relevance"] == 9
    assert report["summary"]["avg_hallucination_risk"] == 1
