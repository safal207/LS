#!/usr/bin/env python3
"""
Strict Russian Language Test
Tests elimination of English internal thoughts in Russian responses
"""

from modules.brain import Brain
import config

class StrictRussianTest:
    def __init__(self):
        self.brain = Brain()
        print("=== STRICT RUSSIAN LANGUAGE TEST ===")
        print("Testing elimination of English internal thoughts...")
        print(f"Model: {config.GROQ_MODEL}")
        
    def test_strict_russian_responses(self):
        """Test that Russian responses have no English internal thoughts"""
        
        russian_questions = [
            "Перечисли виды тестирования ПО",
            "Как организовать CI/CD пайплайн?",
            "Расскажи о принципах SOLID",
            "Какие есть виды архитектурных паттернов?"
        ]
        
        print("\n" + "="*60)
        print("STRICT RUSSIAN RESPONSE TEST")
        print("="*60)
        print("Checking for English internal thoughts in Russian responses...")
        print("="*60)
        
        for i, question in enumerate(russian_questions, 1):
            print(f"\n[{i}] RUSSIAN QUESTION: {question}")
            print("-" * 50)
            
            response = self.brain.think(question)
            print(f"FULL RESPONSE:")
            print(response)
            print("-" * 30)
            
            # Check for English internal thoughts
            english_thought_indicators = [
                "Okay, the user", "Let me start by", "First, I need to", 
                "Wait, there's also", "Oh, and", "Alright, that should",
                "I should", "Make sure", "Check if", "Ensure that"
            ]
            
            found_english_thoughts = []
            for indicator in english_thought_indicators:
                if indicator.lower() in response.lower():
                    found_english_thoughts.append(indicator)
            
            # Check for complete Russian response
            russian_chars = sum(1 for c in response if ord(c) in range(1040, 1104))
            total_chars = len(response)
            russian_ratio = russian_chars / total_chars if total_chars > 0 else 0
            
            if found_english_thoughts:
                print(f"❌ ISSUE FOUND: English thoughts detected:")
                for thought in found_english_thoughts[:3]:  # Show first 3
                    print(f"   - '{thought}'")
                print(f"   Russian content ratio: {russian_ratio:.1%}")
            elif russian_ratio > 0.8:
                print(f"✅ SUCCESS: Pure Russian response ({russian_ratio:.1%} Russian)")
                print("   No English internal thoughts detected")
            else:
                print(f"⚠️  PARTIAL: Low Russian content ({russian_ratio:.1%})")
            
            print("="*60)
    
    def test_response_completeness(self):
        """Test that responses are complete and not cut off"""
        print("\n" + "="*60)
        print("RESPONSE COMPLETENESS TEST")
        print("="*60)
        
        test_questions = [
            "Перечисли виды тестирования ПО",
            "Какие принципы SOLID ты знаешь?",
            "Расскажи о паттерне Observer"
        ]
        
        for i, question in enumerate(test_questions, 1):
            print(f"\n[{i}] TEST: {question}")
            print("-" * 40)
            
            response = self.brain.think(question)
            print(f"RESPONSE LENGTH: {len(response)} characters")
            print(f"RESPONSE: {response}")
            
            # Check completeness indicators
            completeness_indicators = [
                ".", "!", "?", "•", "-", "1.", "2.", "3.", 
                "первый", "второй", "третий", "основные", "например"
            ]
            
            found_indicators = [ind for ind in completeness_indicators 
                              if ind in response.lower()]
            
            if len(response) > 100 and found_indicators:
                print("✅ COMPLETE: Long response with structure")
            elif len(response) < 50:
                print("⚠️  SHORT: Very brief response")
            else:
                print("ℹ️  MODERATE: Medium length response")
            
            print("="*40)

if __name__ == "__main__":
    tester = StrictRussianTest()
    tester.test_strict_russian_responses()
    tester.test_response_completeness()
    
    print("\n" + "="*60)
    print("🎯 STRICT RUSSIAN TESTING COMPLETE")
    print("System should now produce pure Russian responses!")
    print("="*60)