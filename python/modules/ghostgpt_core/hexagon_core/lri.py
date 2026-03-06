class LRI:
    def __init__(self):
        self.modes = {
            "HR": "Role: Friendly Diplomat. Focus: Teamwork, Soft Skills, Reliability. Tone: Polite, Calm.",
            "TECH": "Role: Senior Engineer. Focus: Code, Architecture, Performance, Trade-offs. Tone: Professional, Technical.",
            "CTO": "Role: Architect/Partner. Focus: Business Value, Scalability, Costs, Risks. Tone: Strategic, Confident."
        }
        self.current_mode = "TECH"

    def set_mode(self, mode):
        if mode in self.modes:
            self.current_mode = mode
            return True
        return False

    def get_prompt(self):
        return f"[LRI ADAPTER ACTIVE]\n{self.modes[self.current_mode]}"
