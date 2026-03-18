"""Unit tests for LanguageModel._generate() and _try_fallback()."""

import logging
import os
import queue
import sys
from pathlib import Path
from threading import Event
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Bootstrap: add ``python/`` to sys.path so ``modules.llm`` resolves its
# relative imports (``from ..config``, ``from ..hexagon_core``).
# This mirrors the pattern used by existing tests (e.g. test_oscillation_control).
# ---------------------------------------------------------------------------
_python_dir = str(Path(__file__).resolve().parent.parent)
if _python_dir not in sys.path:
    sys.path.insert(0, _python_dir)

from modules.llm.llm_module import LanguageModel
from modules.llm.errors import LLMEmptyResponseError, LLMInvalidFormatError, LLMProviderError
from modules.llm.breaker import CircuitBreaker, CircuitOpenError


@pytest.fixture
def lm():
    """Create a LanguageModel with mocked QwenHandler for isolated testing."""
    with patch.dict(os.environ, {"WHISPER_MODE": "0"}, clear=False):
        iq, oq = queue.Queue(), queue.Queue()
        model = LanguageModel(iq, oq, use_cotcore=False, use_breaker=False)
        model.qwen_handler = MagicMock()
        model.primary_model = "model-a"
        model.fallback_model = "model-b"
        return model


@pytest.fixture
def lm_with_breaker():
    """Create a LanguageModel with circuit breaker enabled."""
    with patch.dict(os.environ, {"WHISPER_MODE": "0"}, clear=False):
        iq, oq = queue.Queue(), queue.Queue()
        model = LanguageModel(iq, oq, use_cotcore=False, use_breaker=True)
        model.qwen_handler = MagicMock()
        model.primary_model = "model-a"
        model.fallback_model = "model-b"
        return model


# --- _generate() tests ---


class TestGenerateLocal:
    def test_success(self, lm):
        lm.qwen_handler.generate_response.return_value = "Hello world"
        result = lm._generate("test question", label="local")
        assert result == "Hello world"

    def test_cancel_before_prompt(self, lm):
        cancel = Event()
        cancel.set()
        result = lm._generate("test", cancel_event=cancel, label="local")
        assert result is None
        lm.qwen_handler.generate_response.assert_not_called()

    def test_empty_response_triggers_fallback(self, lm):
        lm.qwen_handler.generate_response.side_effect = [
            LLMEmptyResponseError(),
            "fallback response",
        ]
        result = lm._generate("test", label="local")
        assert result == "fallback response"

    def test_provider_error_triggers_fallback(self, lm):
        lm.qwen_handler.generate_response.side_effect = [
            LLMProviderError("boom"),
            "fallback ok",
        ]
        result = lm._generate("test", label="local")
        assert result == "fallback ok"

    def test_no_fallback_when_same_model(self, lm):
        lm.fallback_model = "model-a"  # same as primary
        lm.qwen_handler.generate_response.side_effect = LLMProviderError("boom")
        result = lm._generate("test", label="local")
        assert result is None


class TestGenerateCloud:
    def test_success(self, lm):
        lm.qwen_handler.generate_response.return_value = "Cloud answer"
        result = lm._generate("test question", label="cloud")
        assert result == "Cloud answer"

    def test_error_triggers_fallback_for_cloud(self, lm):
        """Cloud errors now also trigger fallback when models differ."""
        lm.qwen_handler.generate_response.side_effect = [
            LLMProviderError("fail"),
            "cloud fallback ok",
        ]
        result = lm._generate("test", label="cloud")
        assert result == "cloud fallback ok"

    def test_no_fallback_when_same_model_cloud(self, lm):
        lm.fallback_model = "model-a"
        lm.qwen_handler.generate_response.side_effect = LLMProviderError("fail")
        result = lm._generate("test", label="cloud")
        assert result is None
        assert lm.qwen_handler.generate_response.call_count == 1


class TestGenerateCircuitBreaker:
    def test_circuit_open_returns_unavailable(self, lm_with_breaker):
        import time
        lm_with_breaker.breaker._opened_at = time.time()  # just opened
        lm_with_breaker.breaker._failure_count = 99
        lm_with_breaker.breaker.cooldown_seconds = 999999
        result = lm_with_breaker._generate("test", label="local")
        assert result is not None
        assert "temporarily unavailable" in result.lower()

    def test_breaker_after_success(self, lm_with_breaker):
        lm_with_breaker.qwen_handler.generate_response.return_value = "ok"
        lm_with_breaker.breaker._failure_count = 2
        lm_with_breaker._generate("test", label="local")
        assert lm_with_breaker.breaker._failure_count == 0

    def test_breaker_after_failure(self, lm_with_breaker):
        lm_with_breaker.qwen_handler.generate_response.side_effect = LLMProviderError("fail")
        lm_with_breaker.fallback_model = lm_with_breaker.primary_model  # no fallback
        lm_with_breaker._generate("test", label="local")
        assert lm_with_breaker.breaker._failure_count == 1


class TestGenerateResponseValidation:
    def test_whitespace_only_raises_empty(self, lm):
        lm.qwen_handler.generate_response.return_value = "   "
        lm.fallback_model = lm.primary_model  # no fallback
        result = lm._generate("test", label="local")
        assert result is None

    def test_non_string_raises_invalid_format(self, lm):
        lm.qwen_handler.generate_response.return_value = 123
        lm.fallback_model = lm.primary_model
        result = lm._generate("test", label="local")
        assert result is None

    def test_none_response_raises_empty(self, lm):
        lm.qwen_handler.generate_response.return_value = None
        lm.fallback_model = lm.primary_model
        result = lm._generate("test", label="local")
        assert result is None


class TestGenerateLogging:
    def test_logs_error_on_provider_exception(self, lm, caplog):
        lm.qwen_handler.generate_response.side_effect = LLMProviderError("boom")
        lm.fallback_model = lm.primary_model
        with caplog.at_level(logging.ERROR):
            lm._generate("test", label="local")
        assert any("boom" in r.message for r in caplog.records if r.levelno == logging.ERROR)

    def test_logs_warning_on_empty_response(self, lm, caplog):
        lm.qwen_handler.generate_response.return_value = None
        lm.fallback_model = lm.primary_model
        with caplog.at_level(logging.WARNING):
            lm._generate("test", label="local")
        assert any("empty" in r.message.lower() for r in caplog.records if r.levelno == logging.WARNING)


# --- _try_fallback() tests ---


class TestTryFallback:
    def test_success_promotes_model(self, lm):
        lm.qwen_handler.generate_response.return_value = "fallback answer"
        result = lm._try_fallback("local", "prompt", None, False, None)
        assert result == "fallback answer"
        assert lm.primary_model == "model-b"

    def test_failure_restores_original_model(self, lm):
        lm.qwen_handler.model_name = "model-a"
        lm.qwen_handler.generate_response.side_effect = RuntimeError("fail")
        result = lm._try_fallback("local", "prompt", None, False, None)
        assert result is None
        assert lm.qwen_handler.model_name == "model-a"

    def test_empty_response_restores_model(self, lm):
        lm.qwen_handler.model_name = "model-a"
        lm.qwen_handler.generate_response.return_value = "   "
        result = lm._try_fallback("local", "prompt", None, False, None)
        assert result is None
        assert lm.qwen_handler.model_name == "model-a"

    def test_none_response_restores_model(self, lm):
        lm.qwen_handler.model_name = "model-a"
        lm.qwen_handler.generate_response.return_value = None
        result = lm._try_fallback("local", "prompt", None, False, None)
        assert result is None
        assert lm.qwen_handler.model_name == "model-a"

    def test_fallback_sets_model_name(self, lm):
        lm.qwen_handler.model_name = "model-a"
        calls = []

        def capture_model(*a, **kw):
            calls.append(lm.qwen_handler.model_name)
            return "ok"

        lm.qwen_handler.generate_response.side_effect = capture_model
        lm._try_fallback("local", "prompt", None, False, None)
        assert calls[0] == "model-b"  # fallback model was set before call

    def test_cloud_fallback_works(self, lm):
        """Verify _try_fallback works with label='cloud' (future-proof)."""
        lm.qwen_handler.generate_response.return_value = "cloud fallback ok"
        result = lm._try_fallback("cloud", "prompt", None, False, None)
        assert result == "cloud fallback ok"
        assert lm.primary_model == "model-b"
