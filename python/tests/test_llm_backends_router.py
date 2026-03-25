import sys
from pathlib import Path
from unittest.mock import MagicMock

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
    fake_client = MagicMock()
    fake_completion = MagicMock()
    fake_completion.choices = [MagicMock(message=MagicMock(content="mimo ok"))]
    fake_completion.model_dump.return_value = {"id": "cmpl_mimo_1"}
    fake_client.chat.completions.create.return_value = fake_completion
    adapter._client = fake_client

    result = adapter.generate(
        messages=[{"role": "user", "content": "test"}],
        system_prompt="sys",
    )

    assert result.ok
    assert result.text == "mimo ok"
    assert result.provider == "mimo"
    fake_client.chat.completions.create.assert_called_once()

