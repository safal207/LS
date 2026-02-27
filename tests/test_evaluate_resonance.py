import pytest

from eval import evaluate_resonance


def test_eval_context_returns_real_metrics(monkeypatch):
    monkeypatch.setattr(
        evaluate_resonance,
        "find_vector_related",
        lambda *_args, **_kwargs: {"n1": 0.2, "n2": 0.8, "n3": 0.4},
    )

    metrics = evaluate_resonance._eval_context(
        question="question",
        thread_id="t",
        replay_loader=evaluate_resonance.mock_replay_loader,
        min_similarity=0.35,
    )

    assert metrics["hit_rate"] == 1
    assert metrics["avg_similarity"] == pytest.approx((0.2 + 0.8 + 0.4) / 3)
    assert metrics["top_score"] == 0.8
    assert metrics["chunks_found"] == 2


def test_evaluate_no_rag_zero_metrics(monkeypatch):
    monkeypatch.setattr(evaluate_resonance, "TEST_QUESTIONS", ["q1"])

    times = iter([100.0, 100.005])
    monkeypatch.setattr(evaluate_resonance.time, "time", lambda: next(times))

    report = evaluate_resonance.evaluate("no_rag")

    assert report["results"][0]["hit_rate"] == 0
    assert report["results"][0]["avg_similarity"] == 0.0
    assert report["results"][0]["top_score"] == 0.0
    assert report["results"][0]["chunks_found"] == 0
    assert report["results"][0]["latency_ms"] < 10


def test_evaluate_original_vs_rewritten_diff(monkeypatch):
    monkeypatch.setattr(evaluate_resonance, "TEST_QUESTIONS", ["502 error"])

    def fake_eval_context(question, thread_id, replay_loader, rewriter=None, min_similarity=0.35):
        if rewriter is None:
            return {"hit_rate": 0, "avg_similarity": 0.2, "top_score": 0.2, "chunks_found": 0}
        return {"hit_rate": 1, "avg_similarity": 0.7, "top_score": 0.9, "chunks_found": 3}

    monkeypatch.setattr(evaluate_resonance, "_eval_context", fake_eval_context)
    monkeypatch.setattr(evaluate_resonance, "get_context_for_question", lambda *args, **kwargs: "ctx")

    original = evaluate_resonance.evaluate("original")
    rewritten = evaluate_resonance.evaluate("rewritten")

    assert rewritten["summary"]["avg_similarity"] > original["summary"]["avg_similarity"]


def test_evaluate_summary_averages(monkeypatch):
    monkeypatch.setattr(evaluate_resonance, "TEST_QUESTIONS", ["q1", "q2"])

    responses = iter(
        [
            {"hit_rate": 1, "avg_similarity": 0.2, "top_score": 0.3, "chunks_found": 1},
            {"hit_rate": 0, "avg_similarity": 0.6, "top_score": 0.9, "chunks_found": 3},
        ]
    )

    monkeypatch.setattr(evaluate_resonance, "_eval_context", lambda *args, **kwargs: next(responses))
    monkeypatch.setattr(evaluate_resonance, "get_context_for_question", lambda *args, **kwargs: "ctx")

    report = evaluate_resonance.evaluate("original")
    summary = report["summary"]

    assert summary["avg_hit_rate"] == 0.5
    assert summary["avg_similarity"] == 0.4
    assert summary["avg_top_score"] == 0.6
    assert summary["avg_chunks_found"] == 2.0


def test_judge_success_rate_in_summary(monkeypatch):
    monkeypatch.setattr(evaluate_resonance, "TEST_QUESTIONS", ["ok", "parse", "boom", "empty"])

    def fake_context(question, *_args, **_kwargs):
        if question == "empty":
            return "   "
        return "ctx"

    def judge_handler(prompt: str) -> str:
        if "Question: ok" in prompt:
            return '{"relevance": 8, "hallucination_risk": 2, "reasoning": "Good"}'
        if "Question: parse" in prompt:
            return "not-json"
        if "Question: boom" in prompt:
            raise RuntimeError("boom")
        return '{"relevance": 5, "hallucination_risk": 5, "reasoning": "fallback"}'

    monkeypatch.setattr(evaluate_resonance, "_eval_context", lambda *args, **kwargs: {"hit_rate": 1, "avg_similarity": 0.5, "top_score": 0.5, "chunks_found": 1})
    monkeypatch.setattr(evaluate_resonance, "get_context_for_question", fake_context)

    report = evaluate_resonance.evaluate("original", judge_handler=judge_handler)

    assert report["summary"]["judge_success_rate"] == 1 / 3


def test_judge_success_rate_none_without_attempts(monkeypatch):
    monkeypatch.setattr(evaluate_resonance, "TEST_QUESTIONS", ["q1"])
    monkeypatch.setattr(evaluate_resonance, "_eval_context", lambda *args, **kwargs: {"hit_rate": 0, "avg_similarity": 0.0, "top_score": 0.0, "chunks_found": 0})

    report = evaluate_resonance.evaluate("original", judge_handler=lambda _p: "{}")

    assert report["summary"]["judge_success_rate"] is None
