import json
import os
import logging
import re
import copy
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
        self.base_dir = self._resolve_data_dir()

    def _resolve_data_dir(self) -> Path:
        """Robustly find the data directory."""
        cwd = Path.cwd()
        candidates = [
            Path(__file__).resolve().parent.parent.parent.parent / "data",
            cwd / "data",
            cwd.parent / "data",
        ]
        for path in candidates:
            if path.exists() and path.is_dir():
                return path
        return Path("data")

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
        STRICT v8:
        - Use word boundaries for strict matching.
        """
        key_lower = key.lower()
        try:
            pattern = rf'\b{re.escape(key_lower)}\b'
            return bool(re.search(pattern, q_lower))
        except re.error:
            return key_lower in q_lower

    def build_context(self, query: str) -> Context:
        self._ensure_loaded()
        q_lower = query.lower()

        # 1. Facts
        facts = [f"{k}: {v}" for k, v in self.facts.items() if self._matches_query(k, q_lower)]

        # 2. Logic
        triggers = ["why", "reason", "почему", "зачем", "tradeoff", "decision", "выбор"]
        logic: List[Dict[str, Any]] = []
        if any(t in q_lower for t in triggers):
            for item in self.logic:
                keywords = item.get("keywords", [])
                if any(self._matches_query(k, q_lower) for k in keywords):
                    logic.append(item)

        # 3. Memory (sorted, safe)
        memory: List[Dict[str, Any]] = []
        if self.memory:
            try:
                raw = self.memory.search_similar(query, k=MEMORY_SEARCH_LIMIT)
                if isinstance(raw, list):
                    def score_of(x: Dict[str, Any]) -> float:
                        try:
                            return float(x.get("score", 0) or 0)
                        except (TypeError, ValueError):
                            return 0.0

                    raw_sorted = sorted(raw, key=score_of, reverse=True)
                    memory = copy.deepcopy(raw_sorted)
                else:
                    logger.warning("⚠️ Memory returned non-list structure.")
            except Exception as e:
                logger.warning(f"⚠️ Memory error: {e}")

        return Context(facts=facts, logic=logic, memory=memory, history=list(self.history))

    def render_prompt(self, query: str, ctx: Context) -> str:
        sections: List[str] = []

        if ctx.facts:
            sections.append("📚 RELEVANT KNOWLEDGE (DMP):\n" + "\n".join(ctx.facts))

        if ctx.memory:
            snippets = []
            for m in ctx.memory:
                q = m.get("question") or m.get("q") or "?"
                a = m.get("answer") or m.get("a") or ""
                a_short = (a[:TRUNCATE_LIMIT_ANSWER] + "...") if len(a) > TRUNCATE_LIMIT_ANSWER else a
                snippets.append(f"• Q: {q} | A: {a_short}")
            sections.append("🧠 RECALLED MEMORIES:\n" + "\n".join(snippets))

        if ctx.logic:
            sections.append(
                "📐 LOGIC ENGINE:\n"
                + "\n".join(
                    [f"⚙️ {i.get('decision')} (Reason: {i.get('reason')})" for i in ctx.logic]
                )
            )

        if ctx.history:
            sections.append(
                "💬 HISTORY:\n"
                + "\n".join(
                    [f"{m['role'].upper()}: {m['content'][:TRUNCATE_LIMIT_HISTORY]}" for m in ctx.history]
                )
            )

        prompt = "\n\n".join(sections) + f"\n\n❓ QUERY: {query}\n🚀 INSTRUCTION: Synthesize context. Be professional."
        return prompt

    def construct_prompt(self, query: str) -> str:
        return self.render_prompt(query, self.build_context(query))
