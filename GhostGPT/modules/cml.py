import json, os

class CML:
    def __init__(self):
        path = os.path.join("data", "logic.json")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                self.db = json.load(f)
        else:
            self.db = []

    def get_context(self, question):
        q = question.lower()
        triggers = ["почему", "зачем", "why", "reason", "tradeoff", "выбрал"]
        
        if not any(t in q for t in triggers):
            return ""

        found = []
        for item in self.db:
            if any(k in q for k in item["keywords"]):
                found.append(f"DECISION: {item['decision']}\nREASON: {item['reason']}\nTRADEOFF: {item['tradeoff']}")
        
        return "\n\n".join(found) if found else ""