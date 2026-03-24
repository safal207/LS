import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
MODULES = ROOT / "python" / "modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from modules.llm.backends.base import LLMResponse
from modules.llm.backends.meritocracy import MeritocracyLLMAdapter


class _FakeBackend:
    def __init__(self, provider: str, model: str, text: str, latency_ms: float = 10.0):
        self.provider = provider
        self.model = model
        self._response = LLMResponse(
            text=text,
            model=model,
            provider=provider,
            latency_ms=latency_ms,
        )

    def generate(self, *args, **kwargs):
        return self._response


def test_meritocracy_selects_best_answer():
    backends = {
        "gonka": _FakeBackend("gonka", "gonka-model", "Я люблю кофе и путешествия."),
        "cloud": _FakeBackend(
            "cloud",
            "cloud-model",
            "Я выбрал этот стек, потому что он даёт хороший баланс скорости, стоимости и поддержки команды.",
        ),
        "local": _FakeBackend(
            "local",
            "local-model",
            "Я выбрал Node.js, потому что он быстрый.",
        ),
    }
    adapter = MeritocracyLLMAdapter(
        backends=backends,
        candidate_order=["gonka", "cloud", "local"],
        enabled=True,
    )

    result = adapter.generate(
        messages=[{"role": "user", "content": "Почему вы выбрали этот стек?"}],
        system_prompt="You are an interview assistant.",
        metadata={"thread_context": "Мы обсуждаем выбор стека и trade-offs."},
    )

    assert result.ok
    assert result.provider == "cloud"
    assert result.model == "cloud-model"
    assert result.raw is not None
    meritocracy = result.raw["meritocracy"]
    assert meritocracy["selected_backend"] == "cloud"
    assert meritocracy["ranking"][0]["backend"] == "cloud"
    assert meritocracy["ranking"][0]["quality"]["overall"] >= meritocracy["ranking"][1]["quality"]["overall"]


def test_meritocracy_disabled_returns_error():
    adapter = MeritocracyLLMAdapter(backends={}, candidate_order=[], enabled=False)

    result = adapter.generate(messages=[{"role": "user", "content": "test"}])

    assert not result.ok
    assert "disabled" in (result.error or "").lower()
