#!/usr/bin/env python3
"""
Test Qwen integration with Interview Copilot
"""

import os
import sys

def test_qwen_models():
    """Test different Qwen model options"""
    
    print("=== Qwen Model Options ===\n")
    
    # Available Qwen models in Ollama
    qwen_models = [
        "qwen2.5:0.5b",    # Very lightweight
        "qwen2.5:1.5b",    # Light
        "qwen2.5:3b",      # Medium
        "qwen2.5:7b",      # Recommended balance
        "qwen2.5:14b",     # More capable but heavier
        "qwen2.5:32b"      # Most capable but heavy
    ]
    
    print("Available Qwen models for Ollama:")
    for model in qwen_models:
        print(f"  • {model}")
    
    print("\nRecommended for Ryzen 5700U:")
    print("  • qwen2.5:3b  - Fastest, good enough")
    print("  • qwen2.5:7b  - Best balance (recommended)")
    print("  • qwen2.5:14b - Most capable if you have RAM")
    
    return qwen_models

def check_ollama_qwen():
    """Check if Qwen models are available in Ollama"""
    try:
        import requests
        
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        if response.status_code == 200:
            models = response.json().get('models', [])
            qwen_models = [m for m in models if 'qwen' in m['name'].lower()]
            
            print(f"\n✅ Found {len(qwen_models)} Qwen models in Ollama:")
            for model in qwen_models:
                print(f"  • {model['name']} ({model['size']//1024//1024//1024}GB)")
            
            return True
        else:
            print("\n❌ Cannot connect to Ollama")
            return False
            
    except Exception as e:
        print(f"\n❌ Ollama connection error: {e}")
        return False

def pull_qwen_model(model_name: str = "qwen2.5:7b"):
    """Pull Qwen model from Ollama registry"""
    print(f"\n📥 Pulling {model_name}...")
    print("This may take several minutes depending on your internet speed.")
    print("Model will be cached locally for future use.\n")
    
    try:
        import subprocess
        result = subprocess.run(['ollama', 'pull', model_name], 
                              capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0:
            print("✅ Model pulled successfully!")
            return True
        else:
            print(f"❌ Failed to pull model: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print("⏰ Pull operation timed out. Try again later.")
        return False
    except Exception as e:
        print(f"❌ Error pulling model: {e}")
        return False

def test_qwen_performance():
    """Test Qwen response quality and speed"""
    print("\n=== Qwen Performance Test ===\n")
    
    try:
        from llm.qwen_handler import QwenHandler
        
        # Test with local Ollama
        handler = QwenHandler(use_cloud_api=False)
        
        test_questions = [
            "Что такое React и зачем он нужен?",
            "Какие преимущества у Next.js перед обычным React?",
            "Объясните разницу между useState и useEffect"
        ]
        
        for i, question in enumerate(test_questions, 1):
            print(f"Тест {i}: {question}")
            import time
            start_time = time.time()
            
            response = handler.generate_response(f"Ответь кратко на русском: {question}")
            
            end_time = time.time()
            latency = end_time - start_time
            
            if response:
                print(f"✅ Ответ ({latency:.1f}s): {response[:100]}...")
            else:
                print("❌ Не удалось получить ответ")
            print()
            
    except Exception as e:
        print(f"❌ Performance test failed: {e}")

def main():
    """Main test function"""
    print("Interview Copilot - Qwen Integration Test")
    print("=" * 50)
    
    # Check available models
    available_models = test_qwen_models()
    
    # Check Ollama connection
    if check_ollama_qwen():
        # Ask user which model to test
        print("\nХочешь протестировать конкретную модель?")
        choice = input("Введите название модели или 'skip' для пропуска: ").strip()
        
        if choice and choice != 'skip':
            if pull_qwen_model(choice):
                test_qwen_performance()
        else:
            print("Пропускаем установку модели.")
            test_qwen_performance()
    else:
        print("\n🔧 Для использования Qwen:")
        print("1. Установи Ollama: https://ollama.com/")
        print("2. Выбери модель: ollama pull qwen2.5:7b")
        print("3. Запусти: python test_qwen_integration.py")

if __name__ == "__main__":
    main()