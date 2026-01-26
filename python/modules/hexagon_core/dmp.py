import json
import os

class DMP:
    def __init__(self, data_path="data/facts.json"):
        # Adjust path if running from different cwd
        if not os.path.exists(data_path):
             # Try going up levels if not found
             if os.path.exists(os.path.join("..", data_path)):
                 data_path = os.path.join("..", data_path)
             elif os.path.exists(os.path.join("..", "..", data_path)):
                 data_path = os.path.join("..", "..", data_path)

        self.facts = []
        if os.path.exists(data_path):
            with open(data_path, "r", encoding="utf-8") as f:
                try:
                    data = json.load(f)
                    self.facts = data.get("facts", [])
                except json.JSONDecodeError:
                    print(f"Error decoding {data_path}")

    def get_context(self, question):
        q = question.lower()
        # Simple keyword search (can be upgraded to vector search via Rust later)
        triggers = ["проект", "опыт", "стек", "stack", "project", "experience", "work"]
        if any(t in q for t in triggers):
            return "\n".join([f"- {fact}" for fact in self.facts])
        return ""
