# ruff: noqa: E402
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
MODULES = ROOT / "python" / "modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from graph.cooperative_engine import CooperativeGraphEngine
from modules.llm.backends.base import LLMResponse


class FakeBackend:
    def __init__(self, provider: str, model: str, text: str, ok: bool = True):
        self.provider = provider
        self.model = model
        self.text = text
        self.ok = ok
        self.last_system_prompt = None

    def generate(
        self,
        messages,
        system_prompt=None,
        temperature=None,
        max_tokens=None,
        timeout=None,
        metadata=None,
        *,
        stream=False,
        on_token=None,
    ):
        self.last_system_prompt = system_prompt
        if not self.ok:
            return LLMResponse(
                text="",
                model=self.model,
                provider=self.provider,
                latency_ms=1.0,
                error="backend failed",
            )
        return LLMResponse(
            text=self.text, model=self.model, provider=self.provider, latency_ms=1.0
        )


def test_cooperative_engine_with_three_backends_returns_final_answer():
    engine = CooperativeGraphEngine(
        {
            "local": FakeBackend("local", "local-model", "draft answer"),
            "gonka": FakeBackend("gonka", "gonka-model", "critique answer"),
            "mimo": FakeBackend("mimo", "mimo-model", "final compressed answer"),
        }
    )

    result = engine.run(
        {"text": "Почему вы выбрали этот стек?"}, "full_run>local>gonka>mimo"
    )

    assert result.success is True
    assert result.final_answer == "final compressed answer"
    assert len(result.participants) == 3


def test_cooperative_engine_degrades_gracefully_if_critic_unavailable():
    engine = CooperativeGraphEngine(
        {
            "local": FakeBackend("local", "local-model", "draft answer"),
            "gonka": FakeBackend("gonka", "gonka-model", "", ok=False),
            "mimo": FakeBackend("mimo", "mimo-model", "final compressed answer"),
        }
    )

    result = engine.run(
        {"text": "Почему вы выбрали этот стек?"}, "full_run>local>gonka>mimo"
    )

    assert result.success is True
    assert result.final_answer == "final compressed answer"
    assert any(p["role"] == "draft" for p in result.participants)


def test_cooperative_engine_degrades_gracefully_if_compressor_unavailable():
    engine = CooperativeGraphEngine(
        {
            "local": FakeBackend("local", "local-model", "draft answer"),
            "gonka": FakeBackend("gonka", "gonka-model", "critique answer"),
            "mimo": FakeBackend("mimo", "mimo-model", "", ok=False),
        }
    )

    result = engine.run(
        {"text": "Почему вы выбрали этот стек?"}, "full_run>local>gonka>mimo"
    )

    assert result.success is True
    assert result.final_answer == "draft answer"


def test_cooperative_engine_uses_role_specific_prompts():
    local = FakeBackend("local", "local-model", "draft answer")
    gonka = FakeBackend("gonka", "gonka-model", "critique answer")
    mimo = FakeBackend("mimo", "mimo-model", "final compressed answer")
    engine = CooperativeGraphEngine({"local": local, "gonka": gonka, "mimo": mimo})

    engine.run(
        {"text": "Почему вы выбрали этот стек?"},
        "full_run>local>gonka>mimo",
        thread_context="Мы обсуждаем trade-offs.",
    )

    assert "Роль: draft" in (local.last_system_prompt or "")
    assert "Роль: critic" in (gonka.last_system_prompt or "")
    assert "Роль: compressor" in (mimo.last_system_prompt or "")


def test_cooperative_engine_propagates_goal_vector_into_role_prompts():
    local = FakeBackend("local", "local-model", "draft answer")
    gonka = FakeBackend("gonka", "gonka-model", "critique answer")
    mimo = FakeBackend("mimo", "mimo-model", "final compressed answer")
    engine = CooperativeGraphEngine({"local": local, "gonka": gonka, "mimo": mimo})

    engine.run(
        {"text": "?????? ?? ??????? ???? ?????"},
        "full_run>local>gonka>mimo",
        thread_context="?? ????????? trade-offs.",
        goal_vector={
            "style": "careful",
            "strategy_bias": "verify_first",
            "target_relevance": 0.8,
            "target_thread_alignment": 0.8,
            "target_hallucination_max": 0.15,
            "target_latency_ms": 12000.0,
        },
    )

    assert "??????? ??????? ??????" in (local.last_system_prompt or "")
    assert "????? ?????? ???? ??????????" in (local.last_system_prompt or "")
    assert "verify_first" in (gonka.last_system_prompt or "")
    assert "??????????? ?????????????" in (mimo.last_system_prompt or "")
