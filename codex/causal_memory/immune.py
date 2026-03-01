from __future__ import annotations
from typing import List, Dict
import re

class ImmuneMemory:
    def __init__(self):
        self.antibodies: List[Dict] = []  # шаблоны угроз + сила

    def learn_threat(self, pattern: str, trigger_type: str = "regex", strength: float = 0.5):
        """Учит новую угрозу или усиливает старую."""
        for ab in self.antibodies:
            if ab["pattern"] == pattern:
                ab["strength"] = min(1.0, ab["strength"] + 0.15)
                ab["hits"] = ab.get("hits", 0) + 1
                return

        self.antibodies.append({
            "pattern": pattern,
            "type": trigger_type,
            "strength": strength,
            "hits": 1
        })

    def check_threat(self, question: str) -> tuple[bool, float]:
        """Проверяет, есть ли угроза."""
        for ab in self.antibodies:
            if ab["type"] == "regex":
                try:
                    if re.search(ab["pattern"], question, re.IGNORECASE):
                        return True, ab["strength"]
                except re.error:
                    continue
            if ab["type"] == "contains" and ab["pattern"].lower() in question.lower():
                return True, ab["strength"]
        return False, 0.0

    def to_dict(self) -> Dict:
        return {"antibodies": self.antibodies}

    @classmethod
    def from_dict(cls, data: Dict) -> 'ImmuneMemory':
        obj = cls()
        obj.antibodies = data.get("antibodies", [])
        return obj
