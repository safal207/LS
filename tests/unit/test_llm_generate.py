"""Unit tests for LanguageModel._generate() and _try_fallback().

Tests cover:
- Local and cloud generation paths
- Fallback triggering and non-triggering
- Exception logging and breaker interaction
- Cancellation mid-generation
- Edge cases (empty response, non-string response)

Import strategy:
    llm_module.py uses ``from ..config import ...`` which requires llm to
    be a sub-package.  We register a synthetic ``_pkg.llm`` hierarchy in
    sys.modules so that relative imports resolve correctly, then load
    llm_module.py via importlib.
"""

import importlib
import importlib.util
import logging
import os
import queue
import threading
import types
import unittest
from unittest.mock import MagicMock

import sys
from pathlib import Path

root = Path(__file__).resolve().parents[2]
modules_root = root / "python" / "modules"

# ---------------------------------------------------------------------------
# Build a synthetic package tree so relative imports inside llm_module.py
# resolve correctly:
#
#   _pkg            (parent package)
#   _pkg.config     (provides OLLAMA_HOST, USE_CLOUD_LLM, …)
#   _pkg.llm        (the llm package — stub __init__)
#   _pkg.llm.errors
#   _pkg.llm.breaker
#   _pkg.llm.cot_adapter   (stub)
#   _pkg.llm.temporal       (stub)
#   _pkg.llm.qwen_handler   (stub)
#   _pkg.llm.ram_model_selector (stub)
#   _pkg.llm.llm_module     (the real module under test)
# ---------------------------------------------------------------------------

_PKG = "_tpkg"  # unique prefix to avoid clashes

def _register_stub(name, *, path=None, attrs=None):
    if name in sys.modules:
        return sys.modules[name]
    m = types.ModuleType(name)
    m.__package__ = name.rsplit(".", 1)[0] if "." in name else name
    if path:
        m.__path__ = [path]
    for k, v in (attrs or {}).items():
        setattr(m, k, v)
    sys.modules[name] = m
    return m

def _load_real(full_name, filepath, package):
    """Load a real .py file as full_name, with __package__ = package."""
    if full_name in sys.modules:
        return sys.modules[full_name]
    spec = importlib.util.spec_from_file_location(
        full_name, filepath, submodule_search_locations=[])
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = package
    sys.modules[full_name] = mod
    spec.loader.exec_module(mod)
    return mod

# 1) Parent package
_register_stub(_PKG, path=str(modules_root))

# 2) Config module  (_pkg.config  —  used by ``from ..config import …``)
_config_attrs = {
    "OLLAMA_HOST": "http://localhost:11434",
    "SYSTEM_PROMPT": "You are a test assistant.",
    "USE_CLOUD_LLM": False,
    "GROQ_API_KEY": "",
    "USE_COTCORE": False,
    "USE_BREAKER": False,
    "LLM_RAM_AWARE": False,
    "LLM_MODEL_NAME": "test-model",
    "BREAKER_THRESHOLD": 3,
    "BREAKER_COOLDOWN": 10,
}
_register_stub(f"{_PKG}.config", attrs=_config_attrs)

# 3) llm sub-package  (stub __init__ — avoids importing cot_adapter etc.)
_register_stub(f"{_PKG}.llm", path=str(modules_root / "llm"))

# 4) Real submodules (no hexagon_core deps)
_errors_mod = _load_real(f"{_PKG}.llm.errors",
                         modules_root / "llm" / "errors.py", f"{_PKG}.llm")
_breaker_mod = _load_real(f"{_PKG}.llm.breaker",
                          modules_root / "llm" / "breaker.py", f"{_PKG}.llm")

# 5) Stub submodules that would trigger hexagon_core
_register_stub(f"{_PKG}.llm.cot_adapter", attrs={"COTAdapter": MagicMock})
_register_stub(f"{_PKG}.llm.temporal", attrs={"TemporalContext": MagicMock})
_register_stub(f"{_PKG}.llm.qwen_handler", attrs={"QwenHandler": MagicMock})
_register_stub(f"{_PKG}.llm.ram_model_selector", attrs={
    "get_available_ram_gb": lambda: 16.0,
    "select_model": lambda ram: ("test-model", "test-model"),
})

# 6) Load the real llm_module.py
_llm_mod = _load_real(f"{_PKG}.llm.llm_module",
                      modules_root / "llm" / "llm_module.py", f"{_PKG}.llm")

# Shortcuts
LLMEmptyResponseError = _errors_mod.LLMEmptyResponseError
LLMInvalidFormatError = _errors_mod.LLMInvalidFormatError
LLMProviderError = _errors_mod.LLMProviderError
as_llm_error = _errors_mod.as_llm_error
CircuitBreaker = _breaker_mod.CircuitBreaker
CircuitOpenError = _breaker_mod.CircuitOpenError
LanguageModel = _llm_mod.LanguageModel


def _make_lm(**overrides):
    """Create a LanguageModel with all external dependencies stubbed out."""
    # Temporarily override module-level constants
    saved = {}
    patches = {
        "USE_COTCORE": False,
        "USE_BREAKER": overrides.get("use_breaker", False),
        "USE_CLOUD_LLM": False,
        "LLM_RAM_AWARE": False,
        "LLM_MODEL_NAME": "test-model",
        "BREAKER_THRESHOLD": 3,
        "BREAKER_COOLDOWN": 10,
        "SYSTEM_PROMPT": "You are a test assistant.",
        "OLLAMA_HOST": "http://localhost:11434",
        "GROQ_API_KEY": "",
    }
    for k, v in patches.items():
        saved[k] = getattr(_llm_mod, k, None)
        setattr(_llm_mod, k, v)

    # Stub QwenHandler at module level
    mock_qwen_cls = MagicMock()
    saved["QwenHandler"] = _llm_mod.QwenHandler
    _llm_mod.QwenHandler = mock_qwen_cls

    # Stub COTAdapter
    saved["COTAdapter"] = _llm_mod.COTAdapter
    _llm_mod.COTAdapter = MagicMock(return_value=None)

    # Stub RAM functions
    saved["get_available_ram_gb"] = _llm_mod.get_available_ram_gb
    saved["select_model"] = _llm_mod.select_model
    _llm_mod.get_available_ram_gb = lambda: 16.0
    _llm_mod.select_model = lambda ram: ("test-model", "test-model")

    old_env = os.environ.get("QWEN_API_KEY")
    os.environ["QWEN_API_KEY"] = "test-key"

    try:
        iq = queue.Queue()
        oq = queue.Queue()
        lm = LanguageModel(
            iq, oq,
            use_cotcore=False,
            use_breaker=overrides.get("use_breaker", False),
        )
        lm._mock_handler = mock_qwen_cls.return_value
    finally:
        # Restore module-level state
        for k, v in saved.items():
            setattr(_llm_mod, k, v)
        if old_env is None:
            os.environ.pop("QWEN_API_KEY", None)
        else:
            os.environ["QWEN_API_KEY"] = old_env

    return lm


class TestGenerate(unittest.TestCase):
    """Tests for LanguageModel._generate()."""

    def test_local_generation_returns_response(self):
        lm = _make_lm()
        lm._mock_handler.generate_response.return_value = "React is a JS library."
        result = lm._generate("What is React?", label="local")
        self.assertEqual(result, "React is a JS library.")

    def test_cloud_generation_returns_response(self):
        lm = _make_lm()
        lm._mock_handler.generate_response.return_value = "Cloud answer here."
        result = lm._generate("What is React?", label="cloud")
        self.assertEqual(result, "Cloud answer here.")

    def test_empty_response_returns_none_for_cloud_same_models(self):
        lm = _make_lm()
        lm._mock_handler.generate_response.return_value = ""
        result = lm._generate("Question?", label="cloud")
        self.assertIsNone(result)

    def test_empty_response_triggers_fallback_for_local(self):
        lm = _make_lm()
        lm.primary_model = "big-model"
        lm.fallback_model = "small-model"
        lm._mock_handler.generate_response.side_effect = [
            "",           # primary fails
            "Fallback!",  # fallback succeeds
        ]
        result = lm._generate("Question?", label="local")
        self.assertEqual(result, "Fallback!")

    def test_none_response_returns_none(self):
        lm = _make_lm()
        lm._mock_handler.generate_response.return_value = None
        result = lm._generate("Question?", label="cloud")
        self.assertIsNone(result)

    def test_non_string_response_returns_none(self):
        lm = _make_lm()
        lm._mock_handler.generate_response.return_value = 42
        result = lm._generate("Question?", label="cloud")
        self.assertIsNone(result)

    def test_cancellation_before_prompt(self):
        lm = _make_lm()
        cancel = threading.Event()
        cancel.set()
        result = lm._generate("Question?", cancel_event=cancel, label="local")
        self.assertIsNone(result)
        lm._mock_handler.generate_response.assert_not_called()

    def test_cancellation_after_response(self):
        lm = _make_lm()
        cancel = threading.Event()

        def set_cancel_then_return(*a, **kw):
            cancel.set()
            return "Answer"

        lm._mock_handler.generate_response.side_effect = set_cancel_then_return
        result = lm._generate("Question?", cancel_event=cancel, label="local")
        self.assertIsNone(result)

    def test_provider_error_is_logged(self):
        lm = _make_lm()
        lm._mock_handler.generate_response.side_effect = RuntimeError("connection refused")
        with self.assertLogs(f"{_PKG}.llm.llm_module", level="ERROR") as cm:
            result = lm._generate("Question?", label="cloud")
        self.assertIsNone(result)
        self.assertTrue(any("provider_error" in msg for msg in cm.output))

    def test_breaker_open_returns_unavailable_message(self):
        lm = _make_lm(use_breaker=True)
        lm.breaker._failure_count = lm.breaker.failure_threshold
        lm.breaker._opened_at = 1.0
        from unittest.mock import patch
        with patch.object(lm.breaker, "_now", return_value=2.0):
            result = lm._generate("Question?", label="local")
        self.assertEqual(result, "LLM temporarily unavailable. Please try again later.")

    def test_breaker_records_success(self):
        lm = _make_lm(use_breaker=True)
        lm._mock_handler.generate_response.return_value = "Good answer"
        lm.breaker._failure_count = 1
        lm._generate("Question?", label="local")
        self.assertEqual(lm.breaker._failure_count, 0)

    def test_breaker_records_failure_on_trip_breaker_error(self):
        lm = _make_lm(use_breaker=True)
        lm._mock_handler.generate_response.side_effect = RuntimeError("boom")
        lm._generate("Question?", label="cloud")
        self.assertEqual(lm.breaker._failure_count, 1)

    def test_on_token_callback_invoked(self):
        lm = _make_lm()
        tokens = []

        def mock_generate(prompt, *, messages=None, stream=False, on_token=None):
            if on_token:
                on_token("Hello")
                on_token(" world")
            return "Hello world"

        lm._mock_handler.generate_response.side_effect = mock_generate
        result = lm._generate(
            "Question?", stream=True,
            on_token=lambda t: tokens.append(t), label="local",
        )
        self.assertEqual(result, "Hello world")
        self.assertEqual(tokens, ["Hello", " world"])

    def test_fallback_not_triggered_when_models_equal(self):
        lm = _make_lm()
        lm.primary_model = "same-model"
        lm.fallback_model = "same-model"
        lm._mock_handler.generate_response.return_value = ""
        result = lm._generate("Question?", label="local")
        self.assertIsNone(result)
        self.assertEqual(lm._mock_handler.generate_response.call_count, 1)

    def test_fallback_triggered_for_cloud_when_models_differ(self):
        lm = _make_lm()
        lm.primary_model = "big-model"
        lm.fallback_model = "small-model"
        lm._mock_handler.generate_response.side_effect = [
            "",              # primary returns empty
            "Cloud fallback",  # fallback succeeds
        ]
        result = lm._generate("Question?", label="cloud")
        self.assertEqual(result, "Cloud fallback")
        self.assertEqual(lm._mock_handler.generate_response.call_count, 2)


class TestTryFallback(unittest.TestCase):
    """Tests for LanguageModel._try_fallback()."""

    def test_fallback_success_switches_primary(self):
        lm = _make_lm()
        lm.primary_model = "big-model"
        lm.fallback_model = "small-model"
        lm._mock_handler.generate_response.return_value = "Fallback answer"

        result = lm._try_fallback("prompt", None, False, None)
        self.assertEqual(result, "Fallback answer")
        self.assertEqual(lm.primary_model, "small-model")
        self.assertEqual(lm.qwen_handler.model_name, "small-model")

    def test_fallback_failure_restores_model(self):
        lm = _make_lm()
        lm.primary_model = "big-model"
        lm.fallback_model = "small-model"
        lm.qwen_handler.model_name = "big-model"
        lm._mock_handler.generate_response.side_effect = RuntimeError("fail")

        result = lm._try_fallback("prompt", None, False, None)
        self.assertIsNone(result)
        self.assertEqual(lm.qwen_handler.model_name, "big-model")

    def test_fallback_empty_response_restores_model(self):
        lm = _make_lm()
        lm.primary_model = "big-model"
        lm.fallback_model = "small-model"
        lm.qwen_handler.model_name = "big-model"
        lm._mock_handler.generate_response.return_value = "   "

        result = lm._try_fallback("prompt", None, False, None)
        self.assertIsNone(result)
        self.assertEqual(lm.qwen_handler.model_name, "big-model")

    def test_fallback_exception_logged(self):
        lm = _make_lm()
        lm.primary_model = "big-model"
        lm.fallback_model = "small-model"
        lm._mock_handler.generate_response.side_effect = RuntimeError("timeout")
        with self.assertLogs(f"{_PKG}.llm.llm_module", level="ERROR") as cm:
            lm._try_fallback("prompt", None, False, None)
        self.assertTrue(any("Fallback model" in msg for msg in cm.output))

    def test_fallback_with_label_cloud(self):
        """_try_fallback works with label='cloud' for logging."""
        lm = _make_lm()
        lm.primary_model = "big-model"
        lm.fallback_model = "small-model"
        lm._mock_handler.generate_response.return_value = "Cloud fallback"

        result = lm._try_fallback("prompt", None, False, None, label="cloud")
        self.assertEqual(result, "Cloud fallback")


class TestGenerateResponseRouting(unittest.TestCase):
    """Tests for generate_response_local, generate_response_cloud, generate_response."""

    def test_local_delegates_to_generate(self):
        lm = _make_lm()
        lm._mock_handler.generate_response.return_value = "local answer"
        result = lm.generate_response_local("Q?")
        self.assertEqual(result, "local answer")

    def test_cloud_delegates_to_generate(self):
        lm = _make_lm()
        lm._mock_handler.generate_response.return_value = "cloud answer"
        result = lm.generate_response_cloud("Q?")
        self.assertEqual(result, "cloud answer")

    def test_generate_response_uses_cloud_when_configured(self):
        lm = _make_lm()
        lm._mock_handler.generate_response.return_value = "routed answer"
        old = _llm_mod.USE_CLOUD_LLM
        _llm_mod.USE_CLOUD_LLM = True
        try:
            result = lm.generate_response("Q?")
        finally:
            _llm_mod.USE_CLOUD_LLM = old
        self.assertEqual(result, "routed answer")

    def test_generate_response_uses_local_when_configured(self):
        lm = _make_lm()
        lm._mock_handler.generate_response.return_value = "routed answer"
        old = _llm_mod.USE_CLOUD_LLM
        _llm_mod.USE_CLOUD_LLM = False
        try:
            result = lm.generate_response("Q?")
        finally:
            _llm_mod.USE_CLOUD_LLM = old
        self.assertEqual(result, "routed answer")


if __name__ == "__main__":
    unittest.main()
