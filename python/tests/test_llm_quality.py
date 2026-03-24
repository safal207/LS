import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
MODULES = ROOT / "python" / "modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from modules.llm.quality import evaluate_llm_answer_quality


def test_quality_prefers_grounded_answer():
    question = "Почему вы выбрали этот стек?"
    grounded = (
        "Я выбрал этот стек, потому что он хорошо подходит под скорость разработки, "
        "поддержку команды и стабильность в продакшене."
    )
    off_topic = "Это интересный вопрос. Я люблю путешествия и кофе."

    grounded_score = evaluate_llm_answer_quality(question, grounded)
    off_topic_score = evaluate_llm_answer_quality(question, off_topic)

    assert grounded_score.overall > off_topic_score.overall
    assert grounded_score.relevance > off_topic_score.relevance
    assert grounded_score.thread_relevance > off_topic_score.thread_relevance


def test_quality_marks_truncation_lower():
    question = "Почему вы выбрали этот стек?"
    full = (
        "Я выбрал этот стек, потому что он даёт хороший баланс скорости, стоимости "
        "и поддержки команды."
    )
    truncated = "Я выбрал этот стек, потому что он даёт хороший баланс скорости"

    full_score = evaluate_llm_answer_quality(question, full)
    truncated_score = evaluate_llm_answer_quality(question, truncated)

    assert full_score.coherence >= truncated_score.coherence


def test_quality_rejects_empty_answer():
    question = "Почему вы выбрали этот стек?"
    score = evaluate_llm_answer_quality(question, "")

    assert score.overall == 0.0
    assert score.hallucination_risk == 1.0
    assert "empty-answer" in score.notes
