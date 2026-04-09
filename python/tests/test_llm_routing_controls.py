import queue
import sys
import types
from unittest.mock import MagicMock

import pytest

if "requests" not in sys.modules:
    requests_stub = types.SimpleNamespace(get=lambda *args, **kwargs: None)
    sys.modules["requests"] = requests_stub
if "psutil" not in sys.modules:
    psutil_stub = types.SimpleNamespace(virtual_memory=lambda: types.SimpleNamespace(available=16 * 1024 * 1024 * 1024))
    sys.modules["psutil"] = psutil_stub

from modules.llm import llm_module
from modules.llm.backends.base import LLMResponse


@pytest.fixture
def lm() -> llm_module.LanguageModel:
    class _DummyQwen:
        def __init__(self, *args, **kwargs):
            self.model_name = kwargs.get("model_name", "dummy-model")

        def generate_response(self, *args, **kwargs):
            return "ok"

    from unittest.mock import patch

    with patch.object(llm_module, "QwenHandler", _DummyQwen):
        model = llm_module.LanguageModel(queue.Queue(), queue.Queue(), use_cotcore=False, use_breaker=False)
    model.qwen_handler = MagicMock()
    return model


class _FakeRouter:
    def __init__(self):
        self.last_metadata = None
        self.set_runtime_calls = []

    def generate(self, **kwargs):
        self.last_metadata = kwargs.get("metadata")
        return LLMResponse(
            text="ok",
            model="x",
            provider="local",
            latency_ms=1.0,
            raw={"route": {"explain": {"policy": "balanced"}, "stats": {"requests_total": 1}}},
        )

    def set_runtime_overrides(self, *, policy=None, health_thresholds=None):
        self.set_runtime_calls.append({"policy": policy, "health_thresholds": health_thresholds})


def test_generate_uses_routing_defaults_metadata(lm: llm_module.LanguageModel):
    fake_router = _FakeRouter()
    lm.backend_router = fake_router
    lm.set_routing_defaults({"routing_mode": "ab", "ab_variant_ratio": 0.1, "policy": "balanced"})

    result = lm.generate_response("hello")

    assert result == "ok"
    assert fake_router.last_metadata["routing_mode"] == "ab"
    assert fake_router.last_metadata["ab_variant_ratio"] == 0.1
    assert fake_router.last_metadata["policy"] == "balanced"
    assert fake_router.last_metadata["question"] == "hello"


def test_update_routing_controls_validates_payload(lm: llm_module.LanguageModel):
    with pytest.raises(ValueError):
        lm.update_routing_controls({"routing_mode": "invalid"})

    with pytest.raises(ValueError):
        lm.update_routing_controls({"ab_variant_ratio": 2.0})


def test_update_routing_controls_updates_defaults_and_runtime(lm: llm_module.LanguageModel):
    fake_router = _FakeRouter()
    lm.backend_router = fake_router

    snapshot = lm.update_routing_controls(
        {
            "routing_mode": "ab",
            "ab_variant_ratio": 0.2,
            "ab_variant_policy": "cost_optimized",
            "policy": "balanced",
            "runtime_policy": "latency_optimized",
            "runtime_health_thresholds": {"error_rate": 0.08},
        }
    )

    assert snapshot["defaults"]["routing_mode"] == "ab"
    assert snapshot["defaults"]["ab_variant_ratio"] == 0.2
    assert fake_router.set_runtime_calls[-1]["policy"] == "latency_optimized"
    assert fake_router.set_runtime_calls[-1]["health_thresholds"] == {"error_rate": 0.08}


def test_get_routing_observability_returns_last_route_snapshot(lm: llm_module.LanguageModel):
    fake_router = _FakeRouter()
    lm.backend_router = fake_router

    lm.generate_response("hello")
    snapshot = lm.get_routing_observability()

    assert snapshot["last_explain"]["policy"] == "balanced"
    assert snapshot["stats"]["requests_total"] == 1
