import json
import os
import logging
from collections import deque

logger = logging.getLogger("CaPU_v2")

class CaPU:
    def __init__(self, memory_module=None):
        self.memory = memory_module
        self.facts = {}
        self.logic = []
        self.history = deque(maxlen=6) # Short-term history buffer

        # Load Static Memory
        self._load_dmp("data/facts.json")
        self._load_cml("data/logic.json")

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

    def update_history(self, role, content):
        self.history.append({"role": role, "content": content})

    def construct_prompt(self, query):
        q_lower = query.lower()
        context_parts = []

        # 1. Scan for Facts (DMP)
        found_facts = []
        for key, value in self.facts.items():
            key_lower = key.lower()
            # Direct match or query contains key
            if key_lower in q_lower:
                found_facts.append(f"{key}: {value}")
            else:
                # Partial match: checks if significant key words are in query
                # Filter out short words to avoid false positives
                key_words = [w for w in key_lower.split() if len(w) > 3]
                if key_words and any(w in q_lower for w in key_words):
                     found_facts.append(f"{key}: {value}")

        if found_facts:
            context_parts.append("RELEVANT FACTS:\n" + "\n".join(found_facts))

        # 2. Dynamic Memory Lookup
        memory_snippets = []
        if self.memory and hasattr(self.memory, "search_similar"):
            try:
                results = self.memory.search_similar(query, k=3)
                for r in results:
                    q = r.get("question") or r.get("q") or ""
                    a = r.get("answer") or r.get("a") or ""
                    a = (a[:100] + '...') if len(a) > 100 else a
                    memory_snippets.append(f"- Q: {q} | A: {a}")
            except Exception:
                pass
        if memory_snippets:
            context_parts.append("RELATED PAST SESSIONS:\n" + "\n".join(memory_snippets))

        # 3. Scan for Logic (CML)
        # Scans query for triggers ("why", "reason") from Logic.
        triggers = ["why", "reason", "почему", "зачем", "tradeoff", "decision"]
        is_reasoning_query = any(t in q_lower for t in triggers)

        found_logic = []
        if is_reasoning_query:
            for item in self.logic:
                keywords = item.get("keywords", [])
                # If any keyword from the item is in the query
                if any(k.lower() in q_lower for k in keywords):
                    # Use 'trade_off' as primary, fallback to 'tradeoff'
                    t_off = item.get('trade_off') or item.get('tradeoff', 'N/A')
                    found_logic.append(f"DECISION: {item.get('decision')}\nREASON: {item.get('reason')}\nTRADE_OFF: {t_off}")

        if found_logic:
            context_parts.append("ARCHITECTURAL LOGIC:\n" + "\n\n".join(found_logic))

        # 4. Short-term history
        if self.history:
             history_str = "CONVERSATION HISTORY:\n"
             for msg in self.history:
                 history_str += f"{msg['role'].upper()}: {msg['content']}\n"
             context_parts.append(history_str)

        # Assemble "Golden Prompt"
        prompt = ""
        if context_parts:
            prompt += "\n\n".join(context_parts) + "\n\n"

        prompt += f"USER QUERY: {query}\n"
        prompt += "INSTRUCTION: Provide a concise, professional answer based on the context above if relevant."

        return prompt
