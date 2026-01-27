import time
import logging
import os
import requests
import json

from ..rust_bridge import RustOptimizer

logger = logging.getLogger("AdaptiveBrain")


class AdaptiveBrain:
    def __init__(self, tier="local", api_keys=None, rust_instance=None, learner_instance=None):
        """
        Adaptive Intelligence Module (Sovereign Edition).
        Tiers:
        - 'cloud': Uses DeepSeek V3 API.
        - 'local': Uses Qwen 2.5 via Ollama.
        """
        self.tier = tier
        self.api_keys = api_keys or {}
        self.rust = rust_instance if rust_instance else RustOptimizer()

        # Lazy import CaPU v3 with fallback to v2 -> v1
        try:
            from .hexagon_core.capu_v3 import CaPUv3 as CaPU
            logger.info("🧠 Brain upgraded to CaPU v3")
        except ImportError:
            try:
                from .hexagon_core.capu_v2 import CaPU
                logger.warning("⚠️ CaPU v3 not found, falling back to v2")
            except ImportError:
                from .hexagon_core.capu import CaPU
                logger.warning("⚠️ CaPU v2 not found, falling back to v1")

        self.capu = CaPU(memory_module=learner_instance)
        self.latency_stats = []

        if self.tier == "cloud" and not self.api_keys.get("deepseek"):
            logger.warning("⚠️ Cloud tier selected but NO DeepSeek key found. Switching to local.")
            self.tier = "local"

    def generate(self, prompt, context_data=None):
        start_time = time.time()

        # 1. Update history (user)
        try:
            self.capu.update_history("user", prompt)
        except Exception:
            pass

        # 2. Build context ONCE
        full_prompt = self.capu.construct_prompt(prompt)

        # 3. Inference
        response = self._inference_strategy(full_prompt)

        # 4. Update history (AI)
        try:
            self.capu.update_history("ai", response)
        except Exception:
            pass

        # 5. Latency
        self.latency_stats.append(time.time() - start_time)

        return response

    def _inference_strategy(self, prompt: str) -> str:
        """DeepSeek -> Qwen fallback strategy."""
        # Tier 1: Cloud (DeepSeek)
        if self.tier == "cloud":
            backoff = 0.5
            for attempt in range(3):
                try:
                    res = self._call_deepseek(prompt)
                    if res:
                        return res
                except Exception as e:
                    logger.warning(f"DeepSeek attempt {attempt + 1} failed: {e}")
                    time.sleep(backoff)
                    backoff *= 2
            logger.error("DeepSeek failed after retries. Falling back to local Qwen...")

        # Tier 2: Local (Qwen via Ollama)
        return self._call_local_qwen(prompt)

    def _call_deepseek(self, prompt: str) -> str | None:
        key = self.api_keys.get("deepseek")
        if not key:
            return None

        url = "https://api.deepseek.com/chat/completions"
        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }
        data = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt},
            ],
            "stream": False,
            "max_tokens": 4096,
            "temperature": 0.7,
        }

        resp = requests.post(url, json=data, headers=headers, timeout=30)
        if resp.status_code != 200:
            raise ConnectionError(f"DeepSeek Status {resp.status_code}: {resp.text}")

        try:
            j = resp.json()
            choices = j.get("choices")
            if not choices or not isinstance(choices, list):
                raise ValueError("DeepSeek response missing choices")
            first = choices[0]
            message = first.get("message") or {}
            content = message.get("content")
            if not content:
                raise ValueError("DeepSeek response missing content")
            return content
        except ValueError:
            raise
        except Exception as e:
            raise ConnectionError(f"DeepSeek JSON parse error: {e}")

    def _call_local_qwen(self, prompt: str) -> str:
        try:
            url = "http://localhost:11434/api/generate"
            data = {
                "model": "qwen2.5:7b",
                "prompt": prompt,
                "stream": False,
                "options": {"num_ctx": 4096, "temperature": 0.6},
            }
            resp = requests.post(url, json=data, timeout=60)
            if resp.status_code == 200:
                body = resp.json()
                # Ollama format: {"response": "...", ...}
                return body.get("response", "Error: Empty local response")
            return f"Error: Local LLM returned {resp.status_code}"
        except requests.exceptions.ConnectionError:
            return "❌ Error: Ollama offline. Run 'ollama serve'."
        except Exception as e:
            logger.error(f"Local LLM error: {e}")
            return "Error: Brain Failure."
