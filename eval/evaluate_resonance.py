import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Callable

from eval.llm_judge import judge_response

ROOT = Path(__file__).resolve().parents[1]
PYTHON_ROOT = ROOT / "python"
MODULES_ROOT = PYTHON_ROOT / "modules"
for _path in (str(MODULES_ROOT), str(PYTHON_ROOT)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from modules.llm.query_rewriter import rewrite_query
from modules.llm.temporal_graph import build_temporal_graph, find_vector_related, get_context_for_question

logger = logging.getLogger(__name__)

# Конфиг (через env для гибкости)
ENABLE_REWRITING = os.getenv("ENABLE_REWRITING_IN_EVAL", "true").lower() in ("true", "1", "yes")
MIN_SIMILARITY = 0.35  # по умолчанию из resonance


# Мок LLM handler (имитирует rewriting: возвращает расширенную версию вопроса на основе ключевых слов)
def mock_llm_handler(prompt: str) -> str:
    # В реальном rewrite_query хендлер получает промпт и возвращает ТОЛЬКО rewritten question.
    question = prompt.split("Question:")[-1].strip() or prompt
    normalized = question.lower()

    expansions = {
        "502 error": "nginx 502 bad gateway error upstream connection failed",
        "timeout": "connection timeout request exceeded maximum wait time",
        "авторизация": "authentication failure invalid credentials or expired session",
    }

    for key, expansion in expansions.items():
        if key in normalized:
            return expansion

    return question  # fallback на оригинальный вопрос


# Тестовые вопросы (хардкод для старта; в будущем можно вынести в YAML)
TEST_QUESTIONS = [
    "502 error",
    "почему не работает авторизация",
    "как увеличить таймаут в fastapi",
    "database pool exhausted",
    "nginx reverse proxy fail",
    "jwt token invalid",
    "connection refused",
    "OOM killed pod",
    "redis cache miss",
    "docker volume mount error",
    "kubernetes deployment failed",
    "sql injection vuln",
    "csrf token missing",
    "rate limit exceeded",
    "ssl handshake fail",
    "",
    "   ",
    "hello world non-tech query",
    "very long query about everything " * 20,
    "как починить 404 not found",
]


# Мок replay_loader (синтетические данные графа)
def mock_replay_loader() -> list[dict[str, Any]]:
    return [
        {"thread_id": "t1", "cause": "nginx timeout", "solution": "increase proxy_read_timeout"},
        {"thread_id": "t2", "cause": "db pool exhausted", "solution": "increase connections"},
        {"thread_id": "t3", "cause": "auth failure jwt invalid", "solution": "refresh token"},
        {"thread_id": "t4", "cause": "connection refused firewall", "solution": "open port"},
        {"thread_id": "t5", "cause": "OOM kubernetes", "solution": "increase memory limits"},
        {"thread_id": "t6", "cause": "nginx 502 bad gateway", "solution": "check upstream service health"},
        {"thread_id": "t7", "cause": "ssl handshake failure", "solution": "update certificate chain"},
        {"thread_id": "t8", "cause": "redis cache miss storm", "solution": "increase cache ttl"},
        {"thread_id": "t9", "cause": "csrf token missing", "solution": "include csrf middleware token"},
        {"thread_id": "t10", "cause": "rate limit exceeded", "solution": "add retry with backoff"},
    ]


def _eval_context(
    question: str,
    thread_id: str,
    replay_loader: Callable[[], list[dict[str, Any]]],
    rewriter: Callable[[str], str] | None = None,
    min_similarity: float = MIN_SIMILARITY,
) -> dict[str, Any]:
    """Обёртка для реальных метрик из find_vector_related (без изменения production-кода)."""
    effective_query = rewriter(question) if rewriter else question
    if effective_query != question:
        logger.debug("Effective query for '%s': %s", question[:50], effective_query[:100])

    graph = build_temporal_graph(replay_loader)
    scores = find_vector_related(
        graph,
        thread_id,
        effective_query,
        top_k=5,
        min_similarity=0.0,
    )

    above_threshold = {k: v for k, v in scores.items() if v >= min_similarity}
    num_scores = len(scores)
    return {
        "hit_rate": 1 if above_threshold else 0,
        "avg_similarity": sum(scores.values()) / num_scores if num_scores else 0.0,
        "top_score": max(scores.values()) if num_scores else 0.0,
        "chunks_found": len(above_threshold),
    }


def evaluate(mode: str, judge_handler: Callable[[str], str] | None = None) -> dict[str, Any]:
    results: list[dict[str, Any]] = []

    for question in TEST_QUESTIONS:
        start_time = time.time()
        context = ""
        metrics = {"hit_rate": 0, "avg_similarity": 0.0, "top_score": 0.0, "chunks_found": 0}

        if mode == "no_rag":
            pass
        elif mode == "original":
            context = get_context_for_question(
                question,
                "test_thread",
                replay_loader=mock_replay_loader,
                enable_rewriting=False,
            )
            metrics = _eval_context(question, "test_thread", mock_replay_loader)
        elif mode == "rewritten":
            rewriter = lambda q: rewrite_query(q, mock_llm_handler)
            context = get_context_for_question(
                question,
                "test_thread",
                replay_loader=mock_replay_loader,
                query_rewriter=rewriter,
                enable_rewriting=ENABLE_REWRITING,
            )
            metrics = _eval_context(
                question,
                "test_thread",
                mock_replay_loader,
                rewriter=rewriter if ENABLE_REWRITING else None,
            )
        else:
            raise ValueError(f"Unknown evaluation mode: {mode}")

        latency_ms = (time.time() - start_time) * 1000

        result = {
            "question": question[:100],
            "mode": mode,
            "context_snippet": context[:200],
            **metrics,
            "latency_ms": latency_ms,
        }

        if judge_handler and context.strip():
            judgment = judge_response(question, context, judge_handler)
            result["relevance"] = judgment.get("relevance", 0)
            result["hallucination_risk"] = judgment.get("hallucination_risk", 10)
            result["judge_reasoning"] = judgment.get("reasoning", "")
        else:
            result["relevance"] = None
            result["hallucination_risk"] = None
            result["judge_reasoning"] = None

        results.append(result)

    judged = [r for r in results if r["relevance"] is not None]

    summary = {
        "avg_hit_rate": sum(r["hit_rate"] for r in results) / len(results),
        "avg_latency_ms": sum(r["latency_ms"] for r in results) / len(results),
        "avg_similarity": sum(r["avg_similarity"] for r in results) / len(results),
        "avg_top_score": sum(r["top_score"] for r in results) / len(results),
        "avg_chunks_found": sum(r["chunks_found"] for r in results) / len(results),
        "avg_relevance": sum(r["relevance"] for r in judged) / len(judged) if judged else None,
        "avg_hallucination_risk": (
            sum(r["hallucination_risk"] for r in judged) / len(judged) if judged else None
        ),
        "worst_questions": [r["question"] for r in sorted(results, key=lambda x: x["hit_rate"])[:3]],
    }

    return {"results": results, "summary": summary}


if __name__ == "__main__":
    modes = ["no_rag", "original", "rewritten"]
    all_results = {mode: evaluate(mode) for mode in modes}
    output_path = "eval/results/resonance_eval.json"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as file_obj:
        json.dump(all_results, file_obj, indent=2, ensure_ascii=False)
    print(f"Eval complete. Results in {output_path}")
