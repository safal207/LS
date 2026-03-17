#!/usr/bin/env python3
"""
Qwen API Integration Module
Supports both Ollama Qwen and Alibaba Cloud Qwen API.

Note: Causal Memory and Context Provider functions are re-exported here for
backward compatibility. Canonical imports should use .causal_memory and
.context_provider directly.
"""

try:
    import requests
except ImportError:  # optional for replay/context helpers
    requests = None
import json
import logging
import os
from time import perf_counter
from pathlib import Path  # noqa: F401
from typing import Callable, Optional

try:
    from ..config import OLLAMA_HOST, LLM_MODEL_NAME
except Exception:  # optional for replay/context helpers
    OLLAMA_HOST = "http://localhost:11434"
    LLM_MODEL_NAME = "qwen2.5:latest"

from .causal_memory import (  # noqa: F401
    DEFAULT_CAUSAL_CONFIDENCE,
    build_default_trace_payloads,
    get_causal_trace_confidence as _get_causal_trace_confidence_impl,
    handle_replay_command,
    replay_thread,
    replay_thread_ui,
    save_causal_trace,
)
from .context_provider import (  # noqa: F401
    collect_windows_context,
    get_registry_manager,
    save_to_codex,
)
from .cpp_stream_parser import extract_ollama_token_cpp as _extract_ollama_token_cpp
from .errors import (
    LLMEmptyResponseError,
    LLMInvalidFormatError,
    LLMProviderError,
    LLMTimeoutError,
    is_timeout_exception,
)

logger = logging.getLogger(__name__)

try:
    import ghostgpt_core as _ghostgpt_core
except Exception:
    _ghostgpt_core = None




def _is_done_frame(raw_line: str) -> bool:
    if '"done"' not in raw_line:
        return False
    try:
        payload = json.loads(raw_line)
    except (json.JSONDecodeError, TypeError):
        return False
    if not isinstance(payload, dict):
        return False
    return bool(payload.get("done"))

def _extract_stream_token(frame_line: str, has_messages: bool) -> str:
    """Fast path token extraction from Ollama JSONL frame (Rust if available)."""
    if _ghostgpt_core is not None:
        try:
            token = _ghostgpt_core.extract_ollama_token(frame_line, has_messages)
            if token is None:
                return ""
            if not isinstance(token, str):
                raise LLMInvalidFormatError("Expected streamed token to be a string")
            return token
        except Exception:
            # fallback to Python parser on any bridge/runtime error
            pass

    cpp_token = _extract_ollama_token_cpp(frame_line, has_messages)
    if cpp_token is not None:
        return cpp_token

    frame = json.loads(frame_line)
    token = frame.get("message", {}).get("content") if has_messages else frame.get("response", "")
    if token is None:
        return ""
    if not isinstance(token, str):
        raise LLMInvalidFormatError("Expected streamed token to be a string")
    return token


DEFAULT_TIMEOUT = 30


def _ensure_requests_available() -> None:
    if requests is None:
        raise LLMProviderError("requests dependency is required for Qwen HTTP provider")


def get_causal_trace_confidence(default: float = DEFAULT_CAUSAL_CONFIDENCE) -> float:
    return _get_causal_trace_confidence_impl(get_registry_manager, default=default)


class QwenHandler:
    def __init__(self, use_cloud_api: bool = False, api_key: str = "", model_name: Optional[str] = None, *, raise_on_error: bool = False):
        self.use_cloud_api = use_cloud_api
        self.api_key = api_key
        self.raise_on_error = raise_on_error
        self.model_name = model_name or LLM_MODEL_NAME
        _ensure_requests_available()
        self.session = requests.Session()
        # Reuse one HTTP session to reduce handshake latency between calls.
        # Note: requests.Session does not support a global timeout attribute;
        # timeout must be passed per request (as done in each .post/.get call).
        self.session.headers.update({"Connection": "keep-alive"})

    @staticmethod
    def _default_num_predict() -> int:
        try:
            value = int(os.getenv("OLLAMA_NUM_PREDICT", "150"))
            return min(max(1, value), 4096)
        except (TypeError, ValueError):
            return 150

    def _build_ollama_payload(
        self,
        prompt: str,
        messages: Optional[list[dict]],
        *,
        stream: bool,
    ) -> tuple[str, dict]:
        num_predict = self._default_num_predict()
        if messages:
            return (
                f"{OLLAMA_HOST}/api/chat",
                {
                    "model": self.model_name,
                    "messages": messages,
                    "stream": stream,
                    "options": {
                        "temperature": 0.2,
                        "num_predict": num_predict,
                    },
                },
            )

        return (
            f"{OLLAMA_HOST}/api/generate",
            {
                "model": self.model_name,
                "prompt": prompt,
                "stream": stream,
                "options": {
                    "temperature": 0.2,
                    "top_k": 40,
                    "top_p": 0.9,
                    "num_predict": num_predict,
                    "repeat_penalty": 1.1,
                },
            },
        )

    def generate_with_ollama(self, prompt: str, messages: Optional[list[dict]] = None) -> Optional[str]:
        """Generate response using Ollama Qwen model. Supports legacy prompt or chat history."""
        try:
            url, payload = self._build_ollama_payload(prompt, messages, stream=False)

            logger.debug(f"Sending to Ollama Qwen: {prompt[:50]}...")
            response = self.session.post(url, json=payload, timeout=DEFAULT_TIMEOUT)
            response.raise_for_status()

            result = response.json()
            if not isinstance(result, dict):
                raise LLMInvalidFormatError("Invalid JSON payload from Ollama")
            raw_answer = result.get("message", {}).get("content") if messages else result.get("response", "")
            if raw_answer is None:
                raw_answer = ""
            if not isinstance(raw_answer, str):
                raise LLMInvalidFormatError("Expected 'response' to be a string")
            answer = raw_answer.strip()

            if answer:
                logger.info(f"Qwen response: {answer[:100]}...")
                return answer
            else:
                if self.raise_on_error:
                    raise LLMEmptyResponseError("Empty response from Qwen (Ollama)")
                logger.warning("Empty response from Qwen")
                return None

        except Exception as e:
            if self.raise_on_error:
                if isinstance(e, (LLMEmptyResponseError, LLMInvalidFormatError, LLMProviderError, LLMTimeoutError)):
                    raise
                if is_timeout_exception(e):
                    raise LLMTimeoutError(cause=e) from e
                if isinstance(e, (KeyError, ValueError, TypeError, json.JSONDecodeError)):
                    raise LLMInvalidFormatError(str(e) or "Invalid response format", cause=e) from e
                raise LLMProviderError(str(e) or "Ollama Qwen error", cause=e) from e
            logger.error(f"Ollama Qwen error: {e}")
            return None

    def generate_with_ollama_stream(
        self,
        prompt: str,
        messages: Optional[list[dict]] = None,
        on_token: Optional[Callable[[str], None]] = None,
    ) -> Optional[str]:
        """Generate response using Ollama stream API and emit incremental chunks."""
        try:
            url, payload = self._build_ollama_payload(prompt, messages, stream=True)
            chunks: list[str] = []
            started = perf_counter()
            first_token_at: float | None = None
            with self.session.post(url, json=payload, timeout=DEFAULT_TIMEOUT, stream=True) as response:
                response.raise_for_status()
                for raw_line in response.iter_lines(decode_unicode=True):
                    if not raw_line:
                        continue
                    if _is_done_frame(raw_line):
                        break
                    token = _extract_stream_token(raw_line, messages is not None)
                    if not token:
                        continue
                    if first_token_at is None:
                        first_token_at = perf_counter()
                        logger.info("llm.ttft_ms=%.1f path=stream", (first_token_at - started) * 1000)
                    chunks.append(token)
                    if on_token is not None:
                        on_token(token)

            answer = "".join(chunks).strip()
            if answer:
                return answer
            if self.raise_on_error:
                raise LLMEmptyResponseError("Empty streamed response from Qwen (Ollama)")
            return None
        except Exception as e:
            if self.raise_on_error:
                if isinstance(e, (LLMEmptyResponseError, LLMInvalidFormatError, LLMProviderError, LLMTimeoutError)):
                    raise
                if is_timeout_exception(e):
                    raise LLMTimeoutError(cause=e) from e
                if isinstance(e, (KeyError, ValueError, TypeError, json.JSONDecodeError)):
                    raise LLMInvalidFormatError(str(e) or "Invalid streamed response format", cause=e) from e
                raise LLMProviderError(str(e) or "Ollama stream error", cause=e) from e
            logger.error(f"Ollama Qwen stream error: {e}")
            return None

    def generate_with_cloud_api(self, prompt: str, messages: Optional[list[dict]] = None) -> Optional[str]:
        """Generate response using Alibaba Cloud Qwen API"""
        if not self.api_key:
            if self.raise_on_error:
                raise LLMProviderError("Qwen API key not provided")
            logger.error("Qwen API key not provided")
            return None

        try:
            # Alibaba Qwen API endpoint
            url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            payload = {
                "model": "qwen-max",  # or qwen-plus for faster response
                "input": {
                    "messages": messages or [{"role": "user", "content": prompt}]
                },
                "parameters": {
                    "temperature": 0.2,
                    "max_tokens": 150,
                    "top_p": 0.9
                }
            }

            logger.debug(f"Sending to Qwen Cloud API: {prompt[:50]}...")
            response = self.session.post(url, headers=headers, json=payload, timeout=DEFAULT_TIMEOUT)
            response.raise_for_status()

            result = response.json()
            if not isinstance(result, dict):
                raise LLMInvalidFormatError("Invalid JSON payload from Qwen Cloud")
            output = result.get("output")
            if not isinstance(output, dict) or "text" not in output:
                raise LLMInvalidFormatError("Missing output.text in Qwen Cloud response")
            raw_answer = output.get("text")
            if raw_answer is None:
                raw_answer = ""
            if not isinstance(raw_answer, str):
                raise LLMInvalidFormatError("Expected output.text to be a string")
            answer = raw_answer.strip()

            if answer:
                logger.info(f"Qwen Cloud response: {answer[:100]}...")
                return answer
            else:
                if self.raise_on_error:
                    raise LLMEmptyResponseError("Empty response from Qwen Cloud")
                logger.warning("Empty response from Qwen Cloud")
                return None

        except Exception as e:
            if self.raise_on_error:
                if isinstance(e, (LLMEmptyResponseError, LLMInvalidFormatError, LLMProviderError, LLMTimeoutError)):
                    raise
                if is_timeout_exception(e):
                    raise LLMTimeoutError(cause=e) from e
                if isinstance(e, (KeyError, ValueError, TypeError, json.JSONDecodeError)):
                    raise LLMInvalidFormatError(str(e) or "Invalid response format", cause=e) from e
                raise LLMProviderError(str(e) or "Qwen Cloud API error", cause=e) from e
            logger.error(f"Qwen Cloud API error: {e}")
            return None

    def generate_response(
        self,
        prompt: str,
        messages: Optional[list[dict]] = None,
        *,
        stream: bool = False,
        on_token: Optional[Callable[[str], None]] = None,
    ) -> Optional[str]:
        """Generate response using appropriate Qwen variant"""
        if stream and not self.use_cloud_api:
            return self.generate_with_ollama_stream(prompt, messages=messages, on_token=on_token)
        if self.use_cloud_api:
            return self.generate_with_cloud_api(prompt, messages=messages)
        else:
            return self.generate_with_ollama(prompt, messages=messages)

    def handle_replay_command(self, user_input: str) -> Optional[str]:
        """Replay UI command helper for AgentLoop/GUI integration."""
        return handle_replay_command(user_input, replay_ui_renderer=replay_thread_ui)


# Test function
def test_qwen_integration():
    """Test Qwen integration"""
    import os

    print("=== Qwen Integration Test ===\n")

    # Test Ollama Qwen first
    print("1. Testing Ollama Qwen...")
    handler = QwenHandler(use_cloud_api=False)

    test_prompt = "Answer briefly in Russian: What is React?"
    response = handler.generate_response(test_prompt)

    if response:
        print("✅ Ollama Qwen working!")
        print(f"Question: {test_prompt}")
        print(f"Answer: {response}\n")
    else:
        print("❌ Ollama Qwen not available\n")

    # Test Cloud API if key provided
    api_key = os.getenv("QWEN_API_KEY", "")
    if api_key:
        print("2. Testing Qwen Cloud API...")
        cloud_handler = QwenHandler(use_cloud_api=True, api_key=api_key)
        cloud_response = cloud_handler.generate_response(test_prompt)

        if cloud_response:
            print("✅ Qwen Cloud API working!")
            print(f"Answer: {cloud_response}\n")
        else:
            print("❌ Qwen Cloud API not working\n")
    else:
        print("2. Qwen Cloud API key not provided (skip test)\n")


if __name__ == "__main__":
    test_qwen_integration()
