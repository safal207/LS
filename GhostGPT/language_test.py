#!/usr/bin/env python3
"""
Language Protocol Test
Tests the new Language Mirroring functionality
"""

from modules.brain import Brain
import config

class LanguageProtocolTester:
    def __init__(self):
        self.brain = Brain()
        print("=== LANGUAGE PROTOCOL TEST ===")
        print("Testing language mirroring capability...")
        print(f"Connected to: {config.GROQ_MODEL}")
        
    def test_language_mirroring(self):
        """Test if the model mirrors user language"""
        
        test_cases = [
            {
                "input": "How are you doing today?",
                "expected_language": "English"
            },
            {
                "input": "Как дела? Как продвигается работа?",
                "expected_language": "Russian"
            },
            {
                "input": "Расскажи о своем самом сложном проекте",
                "expected_language": "Russian"
            },
            {
                "input": "What is your approach to code quality?",
                "expected_language": "English"
            }
        ]
        
        print("\n" + "="*60)
        print("LANGUAGE MIRRORING TEST")
        print("="*60)
        
        for i, test_case in enumerate(test_cases, 1):
            user_input = test_case["input"]
            expected_lang = test_case["expected_language"]
            
            print(f"\n[{i}] INPUT ({expected_lang}): {user_input}")
            print("-" * 40)
            
            response = self.brain.think(user_input)
            print(f"RESPONSE: {response}")
            
            # Basic language detection in response
            russian_chars = sum(1 for c in response if ord(c) in range(1040, 1104))
            english_words = len([word for word in response.lower().split() if word.isalpha()])
            
            if expected_lang == "Russian" and russian_chars > 10:
                print("✅ CORRECT: Responded in Russian")
            elif expected_lang == "English" and english_words > 5:
                print("✅ CORRECT: Responded in English")
            else:
                print("⚠️  POTENTIAL ISSUE: Language mismatch")
            
            print("="*60)
    
    def test_russian_engineering_slang(self):
        """Test Russian engineering terminology"""
        print("\n" + "="*60)
        print("RUSSIAN ENGINEERING SLANG TEST")
        print("="*60)
        
        engineering_questions = [
            "Как организовать деплой микросервисов?",
            "Расскажи про архитектуру Nexus Sales",
            "Какие практики код-ревью ты используешь?",
            "Что такое резонанс в твоем подходе?"
        ]
        
        for i, question in enumerate(engineering_questions, 1):
            print(f"\n[{i}] RUSSIAN TECH QUESTION: {question}")
            print("-" * 40)
            
            response = self.brain.think(question)
            print(f"RESPONSE: {response}")
            
            # Check for engineering terms
            tech_terms = ["деплой", "архитектура", "микросервис", "код-ревью", 
                         "резонанс", "продакшн", "инфраструктура", "pipeline"]
            
            found_terms = [term for term in tech_terms if term in response.lower()]
            if found_terms:
                print(f"✅ TECH TERMS FOUND: {', '.join(found_terms)}")
            else:
                print("ℹ️  No specific tech terms detected")
            
            print("="*60)

if __name__ == "__main__":
    tester = LanguageProtocolTester()
    tester.test_language_mirroring()
    tester.test_russian_engineering_slang()
    
    print("\n" + "="*60)
    print("🎯 LANGUAGE PROTOCOL TESTING COMPLETE")
    print("System should now mirror user language accurately!")
    print("="*60)