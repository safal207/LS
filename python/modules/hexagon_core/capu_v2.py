import json
import os
import logging
import re
from collections import deque
from typing import Protocol, List, Optional, Dict
from dataclasses import dataclass

logger = logging.getLogger("CaPU_v2")

class MemoryInterface(Protocol):
    """Contract for memory systems"""
    def search_similar(self, query: str, k: int) -> List[dict]:
        ...

@dataclass
class Context:
    """Structured context (not just string)"""
    facts: List[str]
    logic: List[dict]
    memory: List[dict]
    history: List[dict]

class CaPU:
    def __init__(self, memory_module: Optional[MemoryInterface] = None):
        self.memory = memory_module
        self.facts = {}
        self.logic = []
        self.history = deque(maxlen=6) # Short-term history buffer

        # Lazy loading flags
        self._loaded = False

    def _resolve_path(self, filename):
        """Helper to find data files from various working directories."""
        candidates = [
            filename,
            os.path.join("..", filename),
            os.path.join("..", "..", filename),
            os.path.join("..", "..", "..", filename),
            os.path.join(os.getcwd(), filename),
        ]

        for path in candidates:
            if os.path.exists(path):
                return path
        return None

    def _load_dmp(self, filename):
        path = self._resolve_path(filename)
        if path:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.facts = data.get("facts", {})
                logger.info(f"Loaded DMP from {path}")
            except Exception as e:
                logger.error(f"Error loading DMP from {path}: {e}")
        else:
            logger.warning(f"DMP file {filename} not found.")

    def _load_cml(self, filename):
        path = self._resolve_path(filename)
        if path:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self.logic = json.load(f)
                logger.info(f"Loaded CML from {path}")
            except Exception as e:
                logger.error(f"Error loading CML from {path}: {e}")
        else:
            logger.warning(f"CML file {filename} not found.")

    def _ensure_loaded(self):
        """Lazy load on first use"""
        if not self._loaded:
            self._load_dmp("data/facts.json")
            self._load_cml("data/logic.json")
            self._loaded = True

    def update_history(self, role, content):
        self.history.append({"role": role, "content": content})

    def _matches_query(self, key: str, q_lower: str) -> bool:
        """Word boundary matching (no false positives)"""
        key_lower = key.lower()

        if key_lower in q_lower:
            return True

        # Filter out short words to avoid false positives
        key_words = [w for w in key_lower.split() if len(w) > 3]
        for word in key_words:
            if re.search(rf'\b{re.escape(word)}\b', q_lower):
                return True

        return False

    def _is_reasoning_query(self, q_lower: str) -> bool:
        triggers = ["why", "reason", "почему", "зачем", "tradeoff", "decision"]
        return any(t in q_lower for t in triggers)

    def _find_logic(self, q_lower: str) -> List[dict]:
        found_logic = []
        for item in self.logic:
            keywords = item.get("keywords", [])
            if any(k.lower() in q_lower for k in keywords):
                found_logic.append(item)
        return found_logic

    def _truncate(self, text: str, length: int) -> str:
        return (text[:length] + '...') if len(text) > length else text

    def build_context(self, query: str) -> Context:
        """Build structured context (separate from rendering)"""
        self._ensure_loaded()

        q_lower = query.lower()

        # Find facts (with word boundaries)
        facts = []
        for key, value in self.facts.items():
            if self._matches_query(key, q_lower):
                facts.append(f"{key}: {value}")

        # Find memory
        memory = []
        if self.memory:
            try:
                # Assuming search_similar follows the protocol or duck typing
                if hasattr(self.memory, "search_similar"):
                     memory = self.memory.search_similar(query, k=3)
            except Exception:
                pass

        # Find logic
        logic = []
        if self._is_reasoning_query(q_lower):
            logic = self._find_logic(q_lower)

        return Context(
            facts=facts,
            logic=logic,
            memory=memory,
            history=list(self.history)
        )

    def render_prompt(self, query: str, context: Context) -> str:
        """Render context to string"""
        sections = []

        if context.facts:
            sections.append("RELEVANT FACTS:\n" + "\n".join(context.facts))

        if context.memory:
            snippets = []
            for m in context.memory:
                q = m.get("question") or m.get("q") or ""
                a = m.get("answer") or m.get("a") or ""
                a = self._truncate(a, 100)
                snippets.append(f"- Q: {q} | A: {a}")
            sections.append("RELATED PAST SESSIONS:\n" + "\n".join(snippets))

        if context.logic:
            logic_strs = []
            for item in context.logic:
                t_off = item.get('trade_off') or item.get('tradeoff', 'N/A')
                logic_strs.append(
                    f"DECISION: {item.get('decision')}\n"
                    f"REASON: {item.get('reason')}\n"
                    f"TRADE_OFF: {t_off}"
                )
            sections.append("ARCHITECTURAL LOGIC:\n\n" + "\n\n".join(logic_strs))

        if context.history:
            hist_strs = []
            for msg in context.history:
                role = msg['role'].upper()
                content = self._truncate(msg['content'], 200)
                hist_strs.append(f"{role}: {content}")
            sections.append("CONVERSATION HISTORY:\n" + "\n".join(hist_strs))

        prompt = ""
        if sections:
            prompt += "\n\n".join(sections) + "\n\n"

        prompt += f"USER QUERY: {query}\n"
        prompt += "INSTRUCTION: Provide a concise, professional answer based on the context above if relevant."

        return prompt

    def construct_prompt(self, query: str) -> str:
        """Main entry point (backward compatible)"""
        context = self.build_context(query)
        return self.render_prompt(query, context)
