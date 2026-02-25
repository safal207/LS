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
from pathlib import Path  # noqa: F401
from typing import Optional

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
from .errors import (
    LLMEmptyResponseError,
    LLMInvalidFormatError,
    LLMProviderError,
    LLMTimeoutError,
    is_timeout_exception,
)

logger = logging.getLogger(__name__)


DEFAULT_TIMEOUT = 30


def _ensure_requests_available() -> None:
    if requests is None:
        raise LLMProviderError("requests dependency is required for Qwen HTTP provider")


def get_causal_trace_confidence(default: float = DEFAULT_CAUSAL_CONFIDENCE) -> float:
    return _get_causal_trace_confidence_impl(get_registry_manager, default=default)


class QwenHandler:
    def __init__(self, use_cloud_api: bool = False, api_key: str = "", *, raise_on_error: bool = False):
        self.use_cloud_api = use_cloud_api
        self.api_key = api_key
        self.raise_on_error = raise_on_error
        _ensure_requests_available()
        self.session = requests.Session()
        self.session.timeout = 30

    def generate_with_ollama(self, prompt: str) -> Optional[str]:
        """Generate response using Ollama Qwen model"""
        try:
            url = f"{OLLAMA_HOST}/api/generate"

            payload = {
                "model": LLM_MODEL_NAME,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.2,
                    "top_k": 40,
                    "top_p": 0.9,
                    "num_predict": 150,
                    "repeat_penalty": 1.1
                }
            }

            logger.debug(f"Sending to Ollama Qwen: {prompt[:50]}...")
            response = self.session.post(url, json=payload, timeout=DEFAULT_TIMEOUT)
            response.raise_for_status()

            result = response.json()
            if not isinstance(result, dict):
                raise LLMInvalidFormatError("Invalid JSON payload from Ollama")
            raw_answer = result.get("response", "")
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

    def generate_with_cloud_api(self, prompt: str) -> Optional[str]:
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
                    "messages": [
                        {"role": "user", "content": prompt}
                    ]
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

    def generate_response(self, prompt: str) -> Optional[str]:
        """Generate response using appropriate Qwen variant"""
        if self.use_cloud_api:
            return self.generate_with_cloud_api(prompt)
        else:
            return self.generate_with_ollama(prompt)

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
