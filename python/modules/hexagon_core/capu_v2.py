import json
import os
import logging
import re
import copy  # ✅ QWEN FIX: Для безопасного копирования памяти
from collections import deque
from typing import Protocol, List, Optional, Dict, Any
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger("CaPU_v2")

HISTORY_BUFFER_SIZE = 6
MEMORY_SEARCH_LIMIT = 3
TRUNCATE_LIMIT_ANSWER = 150
TRUNCATE_LIMIT_HISTORY = 200

class MemoryInterface(Protocol):
    def search_similar(self, query: str, k: int) -> List[Dict[str, Any]]:
        ...

@dataclass
class Context:
    facts: List[str]
    logic: List[Dict[str, Any]]
    memory: List[Dict[str, Any]]
    history: List[Dict[str, str]]

class CaPU:
    def __init__(self, memory_module: Optional[MemoryInterface] = None):
        self.memory = memory_module
        self.facts: Dict[str, str] = {}
        self.logic: List[Dict[str, Any]] = []
        self.history = deque(maxlen=HISTORY_BUFFER_SIZE)
        self._loaded = False
        # ✅ PATHLIB FIX: Надежный поиск папки data
        self.base_dir = Path(__file__).parent.parent.parent.parent / "data"

    def _ensure_loaded(self):
        if not self._loaded:
            self._load_dmp("facts.json")
            self._load_cml("logic.json")
            self._loaded = True

    def _load_dmp(self, filename: str):
        path = self.base_dir / filename
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # ✅ VALIDATION FIX
                    if isinstance(data, dict):
                        self.facts = data.get("facts", {})
                        logger.info(f"🧠 DMP loaded from {path}")
                    else:
                        logger.warning(f"⚠️ Invalid DMP structure in {path}")
            except Exception as e:
                logger.error(f"❌ Error loading DMP: {e}")

    def _load_cml(self, filename: str):
        path = self.base_dir / filename
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # ✅ VALIDATION FIX
                    if isinstance(data, list):
                        self.logic = data
                        logger.info(f"📐 CML loaded from {path}")
                    else:
                        logger.warning(f"⚠️ Invalid CML structure in {path}")
            except Exception as e:
                logger.error(f"❌ Error loading CML: {e}")

    def update_history(self, role: str, content: str):
        self.history.append({"role": role, "content": content})

    def _matches_query(self, key: str, q_lower: str) -> bool:
        """
        QWEN/DEEPSEEK FIX: Strict matching only.
        """
        key_lower = key.lower()

        # 1. Если это фраза (много слов), то 'in' безопасен
        if " " in key_lower:
             if key_lower in q_lower:
                 return True

        # 2. Если это одно слово ("Rust"), используем ТОЛЬКО строгий Regex
        # \b защищает от срабатывания "Rust" внутри "Trust"
        try:
            pattern = rf'\b{re.escape(key_lower)}\b'
            if re.search(pattern, q_lower):
                return True
        except re.error:
            pass

        return False

    def build_context(self, query: str) -> Context:
        self._ensure_loaded()
        q_lower = query.lower()

        # 1. Facts
        relevant_facts = []
        for key, value in self.facts.items():
            if self._matches_query(key, q_lower):
                relevant_facts.append(f"{key}: {value}")

        # 2. Logic
        relevant_logic = []
        triggers = ["why", "reason", "почему", "зачем", "tradeoff", "decision", "выбор"]
        if any(t in q_lower for t in triggers):
            for item in self.logic:
                keywords = item.get("keywords", [])
                if any(self._matches_query(k, q_lower) for k in keywords):
                    relevant_logic.append(item)

        # 3. Memory
        relevant_memory = []
        if self.memory:
            try:
                # Assuming search_similar follows the protocol or duck typing
                # We need to check if it has the method or just try calling it
                if hasattr(self.memory, "search_similar"):
                    raw_memory = self.memory.search_similar(query, k=MEMORY_SEARCH_LIMIT)
                    # ✅ QWEN FIX: Deepcopy защищает от мутаций внешней памяти
                    if raw_memory:
                        relevant_memory = copy.deepcopy(raw_memory)
            except Exception as e:
                logger.warning(f"⚠️ Memory retrieval failed: {e}")

        return Context(
            facts=relevant_facts,
            logic=relevant_logic,
            memory=relevant_memory,
            history=list(self.history)
        )

    def render_prompt(self, query: str, ctx: Context) -> str:
        sections = []
        if ctx.facts:
            sections.append("📚 RELEVANT KNOWLEDGE (DMP):\n" + "\n".join(ctx.facts))
        if ctx.memory:
            snippets = []
            for m in ctx.memory:
                q = m.get("question") or m.get("q") or "?"
                a = m.get("answer") or m.get("a") or ""
                a_short = (a[:TRUNCATE_LIMIT_ANSWER] + '...') if len(a) > TRUNCATE_LIMIT_ANSWER else a
                snippets.append(f"• Q: {q} | A: {a_short}")
            sections.append("🧠 RECALLED MEMORIES:\n" + "\n".join(snippets))
        if ctx.logic:
            logic_strs = []
            for item in ctx.logic:
                t_off = item.get('trade_off') or item.get('tradeoff', 'None')
                logic_strs.append(f"⚙️ LOGIC: {item.get('decision')} (Reason: {item.get('reason')})")
            sections.append("📐 LOGIC ENGINE:\n" + "\n".join(logic_strs))
        if ctx.history:
            hist_str = "💬 HISTORY:\n"
            for msg in ctx.history:
                hist_str += f"{msg['role'].upper()}: {msg['content'][:TRUNCATE_LIMIT_HISTORY]}\n"
            sections.append(hist_str)

        prompt = ""
        if sections:
            prompt += "\n\n".join(sections) + "\n\n"
        prompt += f"❓ QUERY: {query}\n"
        prompt += "🚀 INSTRUCTION: Synthesize context. Be professional."
        return prompt

    def construct_prompt(self, query: str) -> str:
        ctx = self.build_context(query)
        return self.render_prompt(query, ctx)
