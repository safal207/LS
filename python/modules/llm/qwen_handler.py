#!/usr/bin/env python3
"""
Qwen API Integration Module
Supports both Ollama Qwen and Alibaba Cloud Qwen API
"""

import requests
import json
import logging
import importlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from ..config import OLLAMA_HOST, LLM_MODEL_NAME
from .errors import (
    LLMEmptyResponseError,
    LLMInvalidFormatError,
    LLMProviderError,
    LLMTimeoutError,
    is_timeout_exception,
)

logger = logging.getLogger(__name__)


DEFAULT_TIMEOUT = 30

_CODEX_WINDOWS_PATH = Path("codex/events/windows")
_CODEX_INDEX_PATH = Path("codex/index.json")
_MAX_CODEX_EVENTS = 20


def _get_focus_tracker():
    if importlib.util.find_spec("rust_core") is None:
        return None
    rust_core_module = importlib.import_module("rust_core")
    tracker_module = getattr(rust_core_module, "focus_tracker", None)
    if tracker_module is None:
        return None
    tracker_cls = getattr(tracker_module, "FocusTracker", None)
    return tracker_cls() if tracker_cls is not None else None


def save_to_codex(event_data: dict) -> Optional[Path]:
    if not isinstance(event_data, dict):
        return None

    _CODEX_WINDOWS_PATH.mkdir(parents=True, exist_ok=True)

    timestamp = event_data.get("timestamp") or datetime.now(timezone.utc).isoformat()
    safe_ts = timestamp.replace(":", "").replace("-", "")
    event_file = _CODEX_WINDOWS_PATH / f"focus_event_{safe_ts}.json"
    event_file.write_text(json.dumps(event_data, ensure_ascii=False, indent=2), encoding="utf-8")

    index_payload = {
        "provider": "windows_context_v1",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "max_in_memory": 10,
        "max_index_entries": _MAX_CODEX_EVENTS,
        "events": []
    }
    if _CODEX_INDEX_PATH.exists():
        existing = json.loads(_CODEX_INDEX_PATH.read_text(encoding="utf-8"))
        if isinstance(existing, dict):
            index_payload.update(existing)

    events = index_payload.get("events", [])
    if not isinstance(events, list):
        events = []

    events = [
        {
            "timestamp": timestamp,
            "event_type": event_data.get("event_type", "focus_change"),
            "path": str(event_file)
        }
    ] + events

    index_payload["events"] = events[:_MAX_CODEX_EVENTS]
    index_payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    _CODEX_INDEX_PATH.write_text(json.dumps(index_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return event_file


def collect_windows_context(session_id: str = "default") -> Optional[dict]:
    tracker = _get_focus_tracker()
    if tracker is None:
        return None

    active_window = tracker.get_active_window()
    if not isinstance(active_window, dict):
        return None

    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": "focus_change",
        "session_id": session_id,
        "active_window": active_window,
        "text_snippet": active_window.get("text_snippet", ""),
        "cursor_position": active_window.get("cursor_position", {"line": 0, "column": 0}),
        "confusion_score": float(active_window.get("confusion_score", 0.0)),
        "fuzzy_factors": active_window.get("fuzzy_factors", {}),
        "confidence": float(active_window.get("confidence", 0.9)),
        "source": "rust_core::focus_tracker",
    }

    if event["confusion_score"] > 0.7:
        event["event_type"] = "confusion_ping"

    save_to_codex(event)
    return event


class QwenHandler:
    def __init__(self, use_cloud_api: bool = False, api_key: str = "", *, raise_on_error: bool = False):
        self.use_cloud_api = use_cloud_api
        self.api_key = api_key
        self.raise_on_error = raise_on_error
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
        print("âœ… Ollama Qwen working!")
        print(f"Question: {test_prompt}")
        print(f"Answer: {response}\n")
    else:
        print("âŒ Ollama Qwen not available\n")
    
    # Test Cloud API if key provided
    api_key = os.getenv("QWEN_API_KEY", "")
    if api_key:
        print("2. Testing Qwen Cloud API...")
        cloud_handler = QwenHandler(use_cloud_api=True, api_key=api_key)
        cloud_response = cloud_handler.generate_response(test_prompt)
        
        if cloud_response:
            print("âœ… Qwen Cloud API working!")
            print(f"Answer: {cloud_response}\n")
        else:
            print("âŒ Qwen Cloud API not working\n")
    else:
        print("2. Qwen Cloud API key not provided (skip test)\n")

if __name__ == "__main__":
    test_qwen_integration()
