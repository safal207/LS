from modules.dmp import DMP
from modules.cml import CML
from modules.lri import LRI

class CaPU:
    def __init__(self):
        self.dmp = DMP()
        self.cml = CML()
        self.lri = LRI()

    def construct_prompt(self, question):
        # 1. Intent Analysis
        facts = self.dmp.get_context(question)
        logic = self.cml.get_context(question)
        persona = self.lri.get_prompt()

        # 2. Assembly of "Golden Prompt"
        prompt = f"{persona}\n\n"
        
        if facts:
            prompt += f"MY HARD SKILLS & EXPERIENCE:\n{facts}\n\n"
        if logic:
            prompt += f"MY ARCHITECTURAL DECISIONS:\n{logic}\n\n"
            
        prompt += f"QUESTION FROM INTERVIEWER: {question}\n"
        prompt += "INSTRUCTION: Provide a concise, professional answer based on my experience provided above."
        
        return prompt