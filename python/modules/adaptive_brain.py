import os
import time
import logging
from ..rust_bridge import RustOptimizer
from .hexagon_core.capu import CaPU
import requests

# Set up logging
logger = logging.getLogger("AdaptiveBrain")

class AdaptiveBrain:
    def __init__(self, tier="free", api_keys=None, rust_instance=None):
        """
        tier: 'free' | 'pro' | 'premium'
        api_keys: dict with 'groq', 'claude', 'qwen_cloud'
        """
        self.tier = tier
        self.api_keys = api_keys or {}
        self.rust = rust_instance if rust_instance else RustOptimizer()
        self.capu = CaPU()

        # Performance tracking
        self.latency_stats = []
        self.cost_tracker = 0.0

        # Check Rust availability
        if self.rust.available:
            logger.info("Rust Core Active: Memory & Pattern Matching Optimized")
        else:
            logger.warning("Rust Core Inactive: Running in Python-only mode")

    def generate(self, prompt, context_data=None):
        """
        Main generation entry point.
        1. Contextualize (CaPU)
        2. Check Cache (Rust)
        3. Model Inference (Tier-based Fallback)
        4. Self-Improvement (Feedback Loop - to be implemented)
        """
        start_time = time.time()

        # 1. Contextualize using CaPU
        # If the input is just the question, CaPU builds the full prompt
        full_prompt = self.capu.construct_prompt(prompt)

        # 2. Check Cache (Rust)
        # Convert prompt to vector (mock for now, or use simple hash/embedding if available)
        # In a real scenario, we'd embed 'prompt' -> vector
        # cached = self.rust.find_similar(embedded_prompt)
        # if cached_high_confidence: return cached_answer

        # 3. Model Inference with Fallback
        response = self._inference_tier_logic(full_prompt)

        latency = time.time() - start_time
        self.latency_stats.append(latency)

        return response

    def _inference_tier_logic(self, prompt):
        # Premium -> Pro -> Free
        if self.tier == "premium":
            res = self._call_claude(prompt)
            if res: return res
            logger.warning("Premium (Claude) failed, falling back to Pro")

        if self.tier in ["premium", "pro"]:
            res = self._call_groq(prompt)
            if res: return res
            logger.warning("Pro (Groq) failed, falling back to Free")

        # Free Tier (Local or specific free APIs)
        return self._call_local_qwen(prompt)

    def _call_claude(self, prompt):
        key = self.api_keys.get("claude")
        if not key: return None

        try:
            # Direct API call to avoid extra dependencies
            url = "https://api.anthropic.com/v1/messages"
            headers = {
                "x-api-key": key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            }
            data = {
                "model": "claude-3-opus-20240229",
                "max_tokens": 1024,
                "messages": [
                    {"role": "user", "content": prompt}
                ]
            }

            resp = requests.post(url, json=data, headers=headers, timeout=10)
            if resp.status_code == 200:
                result = resp.json()
                return result['content'][0]['text']
            else:
                logger.warning(f"Claude API returned status {resp.status_code}: {resp.text}")

        except Exception as e:
            logger.error(f"Claude API Error: {e}")

        return None

    def _call_groq(self, prompt):
        key = self.api_keys.get("groq")
        if not key: return None
        # Use Groq API
        try:
            headers = {
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json"
            }
            data = {
                "messages": [{"role": "user", "content": prompt}],
                "model": "mixtral-8x7b-32768"
            }
            resp = requests.post("https://api.groq.com/openai/v1/chat/completions", json=data, headers=headers, timeout=5)
            if resp.status_code == 200:
                return resp.json()['choices'][0]['message']['content']
        except Exception as e:
            logger.error(f"Groq Error: {e}")
        return None

    def _call_local_qwen(self, prompt):
        # Call Ollama
        try:
            url = "http://localhost:11434/api/generate"
            data = {
                "model": "qwen2.5:7b", # Or phi3 or whatever is installed
                "prompt": prompt,
                "stream": False
            }
            resp = requests.post(url, json=data, timeout=30)
            if resp.status_code == 200:
                return resp.json()['response']
        except Exception as e:
            logger.error(f"Ollama Error: {e}")
            return "Error: Could not connect to any brain tier."

    def get_metrics(self):
        avg_latency = sum(self.latency_stats) / len(self.latency_stats) if self.latency_stats else 0
        return {
            "avg_latency": avg_latency,
            "requests": len(self.latency_stats),
            "tier": self.tier
        }
