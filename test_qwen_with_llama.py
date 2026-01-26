#!/usr/bin/env python3
"""
Test Qwen handler with existing llama3.2 model
"""

import time
from qwen_handler import QwenHandler

def test_with_existing_model():
    """Test Qwen handler using existing llama3.2 model"""
    print("=== Testing Qwen Handler with llama3.2 ===\n")
    
    # Create handler for local Ollama
    handler = QwenHandler(use_cloud_api=False)
    
    # Test questions
    test_questions = [
        "What is React?",
        "Explain useState hook",
        "What is the difference between interface and type in TypeScript?",
        "How does Virtual DOM work?",
        "What are React lifecycle methods?"
    ]
    
    print("Testing with existing llama3.2 model...")
    print("(This will demonstrate the full pipeline)\n")
    
    for i, question in enumerate(test_questions, 1):
        print(f"Test {i}/{len(test_questions)}")
        print(f"Question: {question}")
        
        # Create prompt similar to what would be used in interview
        prompt = f"You are a senior React developer. Answer this technical question briefly and clearly in Russian:\n\n{question}"
        
        start_time = time.time()
        try:
            response = handler.generate_with_ollama(prompt)
            end_time = time.time()
            
            if response:
                print(f"✅ Response ({end_time - start_time:.1f}s):")
                print(f"   {response}")
            else:
                print("❌ No response received")
        except Exception as e:
            print(f"❌ Error: {e}")
        
        print("-" * 50)
        time.sleep(1)  # Small delay between requests

def test_russian_questions():
    """Test specifically with Russian questions"""
    print("\n=== Testing Russian Questions ===\n")
    
    handler = QwenHandler(use_cloud_api=False)
    
    russian_questions = [
        "Что такое React и зачем он нужен?",
        "Объясните хук useState",
        "В чем разница между interface и type в TypeScript?",
        "Как работает Virtual DOM?",
        "Какие методы жизненного цикла есть в React?"
    ]
    
    for i, question in enumerate(russian_questions, 1):
        print(f"Russian Test {i}/{len(russian_questions)}")
        print(f"Вопрос: {question}")
        
        prompt = f"Ответь кратко как опытный разработчик React:\n\n{question}"
        
        start_time = time.time()
        try:
            response = handler.generate_with_ollama(prompt)
            end_time = time.time()
            
            if response:
                print(f"✅ Ответ ({end_time - start_time:.1f}s):")
                print(f"   {response}")
            else:
                print("❌ Нет ответа")
        except Exception as e:
            print(f"❌ Ошибка: {e}")
        
        print("-" * 50)
        time.sleep(1)

def main():
    print("Interview Copilot - Qwen Handler Test")
    print("Testing with existing llama3.2 model")
    print("=" * 60)
    
    # Test English questions
    test_with_existing_model()
    
    # Test Russian questions
    test_russian_questions()
    
    print("\n" + "=" * 60)
    print("✅ All tests completed!")
    print("\nNext steps:")
    print("1. Wait for qwen2.5:7b installation to complete")
    print("2. Update config.py to use 'qwen2.5:7b'")
    print("3. Run full integration test")
    print("4. Test with Ghost GUI")

if __name__ == "__main__":
    main()