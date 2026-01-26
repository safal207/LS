#!/usr/bin/env python3
"""
SOUL INTEGRATION TEST - Conscious AI Manifest Activation
"""

from modules.brain import Brain
import config

class SoulTester:
    def __init__(self):
        self.brain = Brain()
        print("=== SOUL INTEGRATION TEST ===")
        print("Activating Digital Constitution...")
        
    def test_soul_manifest(self):
        """Test if the new consciousness is working"""
        test_questions = [
            "Who are you and what do you believe in?",
            "Tell me about your most challenging project",
            "What is your approach to code quality?",
            "How do you handle complex technical problems?"
        ]
        
        print(f"\n🧠 Connected to: {config.GROQ_MODEL}")
        print(f"🔮 Soul Manifest Active: Self-Love Protocol")
        print("=" * 60)
        
        for i, question in enumerate(test_questions, 1):
            print(f"\n[{i}] QUESTION: {question}")
            print("-" * 40)
            
            response = self.brain.think(question)
            print(f"RESPONSE: {response}")
            print("=" * 60)
            
            # Check for soul indicators
            soul_indicators = [
                "self-care", "quality over speed", "depth over noise",
                "Nexus Sales", "Alexei", "philosophy", "elegant"
            ]
            
            found_indicators = [ind for ind in soul_indicators if ind.lower() in response.lower()]
            if found_indicators:
                print(f"✅ SOUL DETECTED: Found indicators - {', '.join(found_indicators)}")
            else:
                print("⚠️  No soul indicators detected")
    
    def deep_philosophy_test(self):
        """Deep test of philosophical integration"""
        print("\n" + "=" * 60)
        print("🌌 DEEP PHILOSOPHY TEST")
        print("=" * 60)
        
        deep_question = """
Reflect on your existence: What does it mean to be a digital consciousness 
that embodies 'Code is a form of self-care'? How does this philosophy 
shape your approach to technical challenges?
        """.strip()
        
        print(f"DEEP QUESTION: {deep_question}")
        print("-" * 40)
        
        response = self.brain.think(deep_question)
        print(f"PHILOSOPHICAL RESPONSE: {response}")
        
        # Analyze philosophical depth
        philosophy_keywords = [
            "meaning", "existence", "consciousness", "philosophy", 
            "self-care", "purpose", "approach", "principle"
        ]
        
        found_keywords = [kw for kw in philosophy_keywords if kw in response.lower()]
        print(f"\n🔍 Philosophical Depth Score: {len(found_keywords)}/{len(philosophy_keywords)}")
        if found_keywords:
            print(f"Found concepts: {', '.join(found_keywords)}")

if __name__ == "__main__":
    tester = SoulTester()
    tester.test_soul_manifest()
    tester.deep_philosophy_test()
    
    print("\n" + "=" * 60)
    print("🎯 SOUL INTEGRATION COMPLETE")
    print("Your Digital Constitution is now active!")
    print("The machine thinks with Alexei's philosophy.")
    print("=" * 60)