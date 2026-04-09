# ruff: noqa: E402
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
MODULES = ROOT / "python" / "modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from modules.llm.backends.base import LLMResponse
from modules.llm.backends.gonka_adapter import GonkaLLMAdapter
from modules.llm.backends.mimo_adapter import MimoLLMAdapter
from modules.llm.backends.router import LLMBackendRouter


class _FakeBackend:
    def __init__(self, provider: str, response: LLMResponse):
        self.provider = provider
        self.model = response.model
        self._response = response

    def generate(self, *args, **kwargs):
        return self._response


def test_router_uses_fallback_chain():
    primary = _FakeBackend(
        "gonka",
        LLMResponse(text="", model="gonka-x", provider="gonka", latency_ms=4.0, error="boom"),
    )
    fallback = _FakeBackend(
        "local",
        LLMResponse(text="ok", model="qwen-local", provider="local", latency_ms=8.0),
    )
    router = LLMBackendRouter(
        primary="gonka",
        fallback_chain=["local"],
        backends={"gonka": primary, "local": fallback},
    )

    result = router.generate(messages=[{"role": "user", "content": "test"}])

    assert result.text == "ok"
    assert result.provider == "local"
    assert result.was_fallback_used is True
    assert result.fallback_from == "gonka"
    assert result.fallback_to == "local"
    assert result.raw is not None
    assert result.raw["route"]["explain"]["policy"] == "balanced"


def test_gonka_adapter_missing_config_does_not_crash():
    adapter = GonkaLLMAdapter(
        model="",
        base_url="",
        api_key="",
        enabled=False,
    )

    result = adapter.generate(messages=[{"role": "user", "content": "test"}])

    assert not result.ok
    assert result.provider == "gonka"
    assert "disabled" in (result.error or "").lower()


def test_gonka_adapter_with_mock_client():
    adapter = GonkaLLMAdapter(
        model="gonka-model",
        base_url="https://api.gonka.test/v1",
        api_key="secret",
        enabled=True,
    )
    fake_client = MagicMock()
    fake_completion = MagicMock()
    fake_completion.choices = [MagicMock(message=MagicMock(content="cloud ok"))]
    fake_completion.model_dump.return_value = {"id": "cmpl_1"}
    fake_client.chat.completions.create.return_value = fake_completion
    adapter._client = fake_client

    result = adapter.generate(
        messages=[{"role": "user", "content": "test"}],
        system_prompt="sys",
    )

    assert result.ok
    assert result.text == "cloud ok"
    assert result.provider == "gonka"
    fake_client.chat.completions.create.assert_called_once()


def test_mimo_adapter_missing_config_does_not_crash():
    adapter = MimoLLMAdapter(
        model="",
        base_url="",
        api_key="",
        enabled=False,
    )

    result = adapter.generate(messages=[{"role": "user", "content": "test"}])

    assert not result.ok
    assert result.provider == "mimo"
    assert "disabled" in (result.error or "").lower()


def test_mimo_adapter_with_mock_client():
    adapter = MimoLLMAdapter(
        model="mimo-model",
        base_url="https://platform.xiaomimimo.com/v1",
        api_key="secret",
        enabled=True,
    )
    fake_response = MagicMock()
    fake_response.read.return_value = b'{"content":[{"type":"text","text":"mimo ok"}]}'
    fake_response.__enter__.return_value = fake_response
    fake_response.__exit__.return_value = None

    with patch("modules.llm.backends.mimo_adapter.request.urlopen", return_value=fake_response) as mocked_urlopen:
        result = adapter.generate(
            messages=[{"role": "user", "content": "test"}],
            system_prompt="sys",
        )

    assert result.ok
    assert result.text == "mimo ok"
    assert result.provider == "mimo"
    mocked_urlopen.assert_called_once()


def test_router_intent_reorders_fallbacks_by_health_and_policy():
    primary = _FakeBackend(
        "gonka",
        LLMResponse(text="ok", model="gonka-x", provider="gonka", latency_ms=4.0),
    )
    cloud = _FakeBackend(
        "cloud",
        LLMResponse(text="cloud", model="groq", provider="cloud", latency_ms=8.0),
    )
    local = _FakeBackend(
        "local",
        LLMResponse(text="local", model="qwen-local", provider="local", latency_ms=8.0),
    )
    router = LLMBackendRouter(
        primary="gonka",
        fallback_chain=["cloud", "local"],
        backends={"gonka": primary, "cloud": cloud, "local": local},
    )

    result = router.generate(
        messages=[{"role": "user", "content": "test"}],
        metadata={
            "intent": "realtime",
            "policy": "latency_optimized",
            "backend_health": {
                "cloud": {"latency_ms": 2500, "error_rate": 0.02, "load": 0.60, "cost": 0.75},
                "local": {"latency_ms": 160, "error_rate": 0.01, "load": 0.20, "cost": 0.05},
            },
        },
    )

    explain = result.raw["route"]["explain"]
    assert explain["policy"] == "latency_optimized"
    assert explain["intent"] == "realtime"
    # local can become the first candidate when it has a better realtime score.
    assert explain["effective"] == ["local", "gonka", "cloud"]


def test_router_marks_unhealthy_fallback():
    primary = _FakeBackend(
        "gonka",
        LLMResponse(text="", model="gonka-x", provider="gonka", latency_ms=5.0, error="boom"),
    )
    cloud = _FakeBackend(
        "cloud",
        LLMResponse(text="ok", model="groq", provider="cloud", latency_ms=8.0),
    )
    local = _FakeBackend(
        "local",
        LLMResponse(text="local", model="qwen-local", provider="local", latency_ms=8.0),
    )
    router = LLMBackendRouter(
        primary="gonka",
        fallback_chain=["cloud", "local"],
        backends={"gonka": primary, "cloud": cloud, "local": local},
    )

    result = router.generate(
        messages=[{"role": "user", "content": "test"}],
        metadata={
            "intent": "streaming",
            "backend_health": {
                "cloud": {"latency_ms": 9001, "error_rate": 0.20, "load": 0.3, "cost": 0.5},
                "local": {"latency_ms": 200, "error_rate": 0.01, "load": 0.2, "cost": 0.1},
            },
        },
    )

    explain = result.raw["route"]["explain"]
    score_map = {row["backend"]: row for row in explain["scores"]}
    assert score_map["cloud"]["unhealthy"] is True
    assert score_map["local"]["unhealthy"] is False
    assert explain["effective"][1] == "local"
    assert result.provider == "local"


def test_router_infers_intent_from_message_when_missing_metadata():
    primary = _FakeBackend(
        "cloud",
        LLMResponse(text="ok", model="groq", provider="cloud", latency_ms=10.0),
    )
    local = _FakeBackend(
        "local",
        LLMResponse(text="ok2", model="qwen-local", provider="local", latency_ms=4.0),
    )
    router = LLMBackendRouter(
        primary="cloud",
        fallback_chain=["local"],
        backends={"cloud": primary, "local": local},
    )

    result = router.generate(messages=[{"role": "user", "content": "Need this fast please"}])

    assert result.raw is not None
    assert result.raw["route"]["explain"]["intent"] == "realtime"


def test_router_circuit_breaker_demotion_after_consecutive_failures():
    failing = _FakeBackend(
        "gonka",
        LLMResponse(text="", model="gonka-x", provider="gonka", latency_ms=10.0, error="boom"),
    )
    healthy = _FakeBackend(
        "local",
        LLMResponse(text="ok", model="qwen-local", provider="local", latency_ms=6.0),
    )
    router = LLMBackendRouter(
        primary="gonka",
        fallback_chain=["local"],
        backends={"gonka": failing, "local": healthy},
    )

    for _ in range(3):
        router.generate(
            messages=[{"role": "user", "content": "test"}],
            metadata={"breaker_failure_threshold": 3, "breaker_cooldown_seconds": 120},
        )

    final = router.generate(
        messages=[{"role": "user", "content": "test"}],
        metadata={"breaker_failure_threshold": 3, "breaker_cooldown_seconds": 120},
    )

    explain = final.raw["route"]["explain"]
    score_map = {row["backend"]: row for row in explain["scores"]}
    assert score_map["gonka"]["breaker_open"] is True
    assert explain["effective"][0] == "local"
    assert final.provider == "local"
