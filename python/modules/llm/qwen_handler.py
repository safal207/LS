#!/usr/bin/env python3
"""
Qwen API Integration Module
Supports both Ollama Qwen and Alibaba Cloud Qwen API
"""

try:
    import requests
except ImportError:  # optional for replay/context helpers
    requests = None
import json
import logging
import importlib
import importlib.util
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
try:
    from ..config import OLLAMA_HOST, LLM_MODEL_NAME
except Exception:  # optional for replay/context helpers
    OLLAMA_HOST = "http://localhost:11434"
    LLM_MODEL_NAME = "qwen2.5:latest"
from .errors import (
    LLMEmptyResponseError,
    LLMInvalidFormatError,
    LLMProviderError,
    LLMTimeoutError,
    is_timeout_exception,
)

logger = logging.getLogger(__name__)


DEFAULT_TIMEOUT = 30

_CODEX_ROOT = Path("codex")
_CODEX_WINDOWS_PATH = _CODEX_ROOT / "events" / "windows"
_CODEX_INDEX_PATH = _CODEX_ROOT / "index.json"
_CODEX_CAUSAL_PATH = _CODEX_ROOT / "causal_memory"
_CODEX_CAUSAL_INDEX_PATH = _CODEX_CAUSAL_PATH / "index.json"
_MAX_CODEX_EVENTS = 20




def _ensure_requests_available() -> None:
    if requests is None:
        raise LLMProviderError("requests dependency is required for Qwen HTTP provider")

def _load_rust_module():
    for module_name in ("rust_core", "ghostgpt_core"):
        if importlib.util.find_spec(module_name) is not None:
            return importlib.import_module(module_name)
    return None


def _get_focus_tracker():
    rust_module = _load_rust_module()
    if rust_module is None:
        return None

    tracker_cls = getattr(rust_module, "FocusTracker", None)
    return tracker_cls() if tracker_cls is not None else None


def get_registry_manager(yaml_path: str = "config/base.yaml"):
    rust_module = _load_rust_module()
    if rust_module is None:
        return None

    manager_cls = getattr(rust_module, "RegistryManager", None)
    return manager_cls(yaml_path) if manager_cls is not None else None


def save_to_codex(event_data: dict) -> Optional[Path]:
    if not isinstance(event_data, dict):
        return None

    timestamp = event_data.get("timestamp") or datetime.now(timezone.utc).isoformat()
    safe_ts = timestamp.replace(":", "").replace("-", "").replace(".", "")
    event_type = str(event_data.get("event_type", "focus_change"))

    if event_type.startswith("causal_"):
        target_dir = _CODEX_CAUSAL_PATH
        index_path = _CODEX_CAUSAL_INDEX_PATH
        prefix = "causal_trace"
        provider = "causal_memory_v1"
    else:
        target_dir = _CODEX_WINDOWS_PATH
        index_path = _CODEX_INDEX_PATH
        prefix = "focus_event"
        provider = "windows_context_v1"

    target_dir.mkdir(parents=True, exist_ok=True)
    event_file = target_dir / f"{prefix}_{safe_ts}.json"
    event_file.write_text(json.dumps(event_data, ensure_ascii=False, indent=2), encoding="utf-8")

    index_payload = {
        "provider": provider,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "max_in_memory": 10,
        "max_index_entries": _MAX_CODEX_EVENTS,
        "events": []
    }
    if index_path.exists():
        try:
            existing = json.loads(index_path.read_text(encoding="utf-8"))
            if isinstance(existing, dict):
                index_payload.update(existing)
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            logger.warning("Failed to parse codex index, rebuilding from scratch")

    events = index_payload.get("events", [])
    if not isinstance(events, list):
        events = []

    events.insert(0, {
        "timestamp": timestamp,
        "event_type": event_type,
        "path": str(event_file),
        "confusion_score": event_data.get("confusion_score", 0.0),
        "confidence": event_data.get("confidence", 0.9),
    })

    index_payload["events"] = events[:_MAX_CODEX_EVENTS]
    index_payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    index_path.write_text(json.dumps(index_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return event_file


def collect_windows_context(session_id: str = "default") -> Optional[dict]:
    tracker = _get_focus_tracker()
    if tracker is None:
        return None

    active_window = tracker.get_active_window()
    if not isinstance(active_window, dict):
        return None

    reg = get_registry_manager()
    raw_threshold = reg.get_config("confusion_threshold") if reg else "0.75"
    try:
        confusion_threshold = float(raw_threshold or "0.75")
    except (TypeError, ValueError):
        confusion_threshold = 0.75

    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": "focus_change",
        "session_id": session_id,
        "active_window": {
            "title": active_window.get("title", ""),
            "class_name": active_window.get("class_name", ""),
            "hwnd": active_window.get("hwnd", "0x0"),
            "process_name": active_window.get("process_name", ""),
        },
        "text_snippet": active_window.get("text_snippet", ""),
        "cursor_position": active_window.get("cursor_position", {"line": 0, "column": 0}),
        "confusion_score": float(active_window.get("confusion_score", 0.0)),
        "fuzzy_factors": active_window.get("fuzzy_factors", {}),
        "confidence": float(active_window.get("confidence", 0.9)),
        "source": "ghostgpt_core::focus_tracker",
    }

    if event["confusion_score"] > confusion_threshold:
        event["event_type"] = "confusion_ping"

    save_to_codex(event)
    if reg:
        reg.save_last_event_id(f"event_{int(datetime.now(timezone.utc).timestamp())}")
    return event


def save_causal_trace(cause: str, solution: str, lce: dict, ltp_trace: dict, lri_core: dict, confidence: float = 0.92) -> None:
    reg = get_registry_manager()
    if reg is None:
        return

    reg.save_causal_trace(cause, solution, lce, ltp_trace, lri_core, confidence)
    save_to_codex({
        **(lce if isinstance(lce, dict) else {}),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": "causal_trace",
        "cause": cause,
        "solution": solution,
        "ltp_trace": ltp_trace,
        "lri_core": lri_core,
        "confidence": confidence,
        "source": "registry::causal_memory",
    })


def replay_thread(thread_id: str) -> list:
    reg = get_registry_manager()
    if reg is None:
        return []
    try:
        result = reg.replay_thread(thread_id)
        return result if isinstance(result, list) else []
    except Exception:
        return []


def replay_thread_ui(thread_id: str) -> str:
    """Replay UI — formatted replay output for end users."""
    trace = replay_thread(thread_id)
    if not trace:
        return f"❌ Тред {thread_id} не найден."

    output = [f"🔄 Replay тред **{thread_id}** ({len(trace)} записей):"]
    for entry in trace:
        if not isinstance(entry, dict):
            continue
        ts = entry.get("ts", "—")
        cause = str(entry.get("cause", "—"))[:80]
        solution = str(entry.get("solution", "—"))[:80]
        drift = float(entry.get("ltp_trace", {}).get("drift", 0.0) or 0.0)
        coherence = float(entry.get("lce", {}).get("qos", {}).get("coherence", 0.0) or 0.0)
        lri_core = entry.get("lri_core", {}) if isinstance(entry.get("lri_core", {}), dict) else {}
        emotional_drift = float(lri_core.get("emotional_drift", 0.0) or 0.0)
        stabilizer = lri_core.get("stabilizer", "—")
        resonance_focus = float(lri_core.get("resonance_map", {}).get("focus", 0.0) or 0.0)
        invariants = lri_core.get("invariants", [])
        inv_preview = ", ".join(str(v) for v in invariants[:2]) if isinstance(invariants, list) else "—"
        output.append(f"• {ts} | drift:{drift:.2f} | emo_drift:{emotional_drift:.2f} | coherence:{coherence:.2f}")
        output.append(f"  LRI: stabilizer={stabilizer} | resonance.focus={resonance_focus:.2f} | invariants={inv_preview}")
        output.append(f"  Причина: {cause}")
        output.append(f"  Решение: {solution}\n")
    return "\n".join(output)


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
        lower = user_input.lower()
        if "replay" in lower or "переиграй" in lower:
            parts = user_input.split()
            for part in parts:
                token = part.strip()
                if token.startswith("thread-") or (token.isalnum() and len(token) > 5):
                    return replay_thread_ui(token)
        return None


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
