from openai import OpenAI
import config
from typing import List, Dict

class Brain:
    def __init__(self):
        self.client = None
        self.dialogue_history: List[Dict] = []  # Track conversation history
        self.max_history_tokens = 2048  # Limit history to prevent context overflow
        self.current_tokens = 0
        
        if config.USE_GROQ and config.GROQ_API_KEY:
            try:
                self.client = OpenAI(
                    base_url="https://api.groq.com/openai/v1",
                    api_key=config.GROQ_API_KEY,
                    timeout=120.0  # Give model time to think deeply
                )
            except:
                print("⚠️ Groq Connect Failed")

    def estimate_tokens(self, text: str) -> int:
        """Rough token estimation (1 token ≈ 4 characters)"""
        return len(text) // 4

    def trim_history(self):
        """Trim dialogue history to prevent context overflow"""
        if not self.dialogue_history:
            return
            
        total_tokens = sum(self.estimate_tokens(msg.get('content', '')) 
                          for msg in self.dialogue_history)
        
        # If we're approaching the limit, trim old messages
        if total_tokens > self.max_history_tokens:
            # Keep only last 8 messages (roughly)
            self.dialogue_history = self.dialogue_history[-8:]
            print(f"✂️ Trimmed history to prevent context overflow")

    def add_to_history(self, role: str, content: str):
        """Add message to dialogue history"""
        self.dialogue_history.append({
            "role": role,
            "content": content
        })
        self.trim_history()

    def think(self, prompt_with_context):
        # We wrap the user prompt with the SYSTEM PROTOCOL
        messages = [
            {"role": "system", "content": config.ACCESS_PROTOCOL_PROMPT},
            {"role": "user", "content": prompt_with_context}
        ]
        
        # Add recent dialogue history if available
        if self.dialogue_history:
            # Add last few messages to maintain context
            recent_history = self.dialogue_history[-3:]  # Last 3 exchanges
            messages = messages[:1] + recent_history + messages[1:]
        
        if not self.client:
            return "Error: API Key missing or Offline."
        
        try:
            completion = self.client.chat.completions.create(
                model=config.GROQ_MODEL,
                messages=messages,
                temperature=config.TEMPERATURE,
                max_tokens=config.MAX_TOKENS,
                top_p=config.TOP_P
            )
            
            response_text = completion.choices[0].message.content
            
            # Add interaction to history
            self.add_to_history("user", prompt_with_context)
            self.add_to_history("assistant", response_text)
            
            return response_text
            
        except Exception as e:
            return f"API Error: {e}"

    def clear_history(self):
        """Clear dialogue history"""
        self.dialogue_history.clear()
        self.current_tokens = 0
        print("🧹 Dialogue history cleared")