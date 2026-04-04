import logging
from typing import Dict, List

import config
from llm.backends import build_llm_backend

logger = logging.getLogger(__name__)


class Brain:
    def __init__(self):
        self.client = None
        self.backend = None
        self.last_response = None
        self.dialogue_history: List[Dict] = []
        self.max_history_tokens = 2048
        self.current_tokens = 0

        if (
            config.LLM_BACKEND
            or config.LLM_FALLBACK_BACKEND
            or config.GONKA_ENABLED
            or config.USE_GROQ
            or config.USE_CLOUD_LLM
        ):
            try:
                self.backend = build_llm_backend()
            except Exception as e:
                logger.error("LLM backend init failed: %s", e)

    def estimate_tokens(self, text: str) -> int:
        """Rough token estimation (1 token ~ 4 characters)"""
        return len(text) // 4

    def trim_history(self):
        """Trim dialogue history to prevent context overflow"""
        if not self.dialogue_history:
            return

        total_tokens = sum(
            self.estimate_tokens(msg.get("content", "")) for msg in self.dialogue_history
        )

        if total_tokens > self.max_history_tokens:
            self.dialogue_history = self.dialogue_history[-8:]
            logger.info("Trimmed history to prevent context overflow")

    def add_to_history(self, role: str, content: str):
        """Add message to dialogue history"""
        self.dialogue_history.append({
            "role": role,
            "content": content,
        })
        self.trim_history()

    def think(self, prompt_with_context):
        messages = [{"role": "user", "content": prompt_with_context}]

        if self.dialogue_history:
            recent_history = self.dialogue_history[-3:]
            messages = recent_history + messages

        if not self.backend:
            return "Error: API Key missing or Offline."

        try:
            response = self.backend.generate(
                messages=messages,
                system_prompt=config.ACCESS_PROTOCOL_PROMPT,
                temperature=config.TEMPERATURE,
                max_tokens=config.MAX_TOKENS,
                metadata={"source": "GhostGPT.Brain"},
            )
            self.last_response = response
            if not response.ok:
                return f"API Error: {response.error}"

            response_text = response.text
            self.add_to_history("user", prompt_with_context)
            self.add_to_history("assistant", response_text)
            return response_text
        except Exception as e:
            return f"API Error: {e}"

    def clear_history(self):
        """Clear dialogue history"""
        self.dialogue_history.clear()
        self.current_tokens = 0
        logger.info("Dialogue history cleared")
