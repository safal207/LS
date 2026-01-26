import json, os

class DMP:
    def __init__(self):
        path = os.path.join("data", "facts.json")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                self.facts = json.load(f)["facts"]
        else:
            self.facts = []

    def get_context(self, question):
        q = question.lower()
        relevant = []
        # Simple keyword search (for speed)
        triggers = ["проект", "опыт", "стек", "stack", "project", "experience"]
        if any(t in q for t in triggers):
            return "\n".join([f"- {fact}" for fact in self.facts])
        return ""