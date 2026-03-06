import json
import os

class CML:
    def __init__(self, data_path="data/logic.json"):
        if not os.path.exists(data_path):
             if os.path.exists(os.path.join("..", data_path)):
                 data_path = os.path.join("..", data_path)
             elif os.path.exists(os.path.join("..", "..", data_path)):
                 data_path = os.path.join("..", "..", data_path)

        self.db = []
        if os.path.exists(data_path):
            with open(data_path, "r", encoding="utf-8") as f:
                try:
                    self.db = json.load(f)
                except json.JSONDecodeError:
                    print(f"Error decoding {data_path}")

    def get_context(self, question):
        q = question.lower()
        triggers = ["почему", "зачем", "why", "reason", "tradeoff", "выбрал", "decision"]

        if not any(t in q for t in triggers):
            return ""

        found = []
        for item in self.db:
            if any(k in q for k in item.get("keywords", [])):
                found.append(f"DECISION: {item.get('decision')}\nREASON: {item.get('reason')}\nTRADEOFF: {item.get('tradeoff')}")

        return "\n\n".join(found) if found else ""
