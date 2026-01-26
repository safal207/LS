#!/usr/bin/env python3
"""
Simple test to verify LLM connection with existing llama3.2 model
"""

import requests
import json
from config import LLM_MODEL_NAME

def test_ollama_connection():
    """Test connection to Ollama API"""
    try:
        # Test if API is responsive
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        if response.status_code == 200:
            models = response.json().get('models', [])
            print("✅ Ollama API is running")
            print("Available models:")
            for model in models:
                print(f"  - {model['name']}")
            return True
        else:
            print("❌ Ollama API returned error")
            return False
    except Exception as e:
        print(f"❌ Cannot connect to Ollama: {e}")
        return False

def test_simple_generation():
    """Test simple text generation"""
    try:
        url = "http://localhost:11434/api/generate"
        
        payload = {
            "model": LLM_MODEL_NAME,
            "prompt": "What is 2+2?",
            "stream": False,
            "options": {
                "temperature": 0.2,
                "num_predict": 10
            }
        }
        
        print("\nTesting text generation...")
        response = requests.post(url, json=payload, timeout=60)
        
        if response.status_code == 200:
            result = response.json()
            answer = result.get('response', '').strip()
            print("✅ Generation successful!")
            print(f"Question: What is React?")
            print(f"Answer: {answer}")
            return True
        else:
            print(f"❌ Generation failed: {response.status_code}")
            print(response.text)
            return False
            
    except Exception as e:
        print(f"❌ Generation error: {e}")
        return False

def main():
    print("=== Ollama Connection Test ===\n")
    
    if test_ollama_connection():
        if test_simple_generation():
            print("\n🎉 All tests passed! LLM is ready.")
        else:
            print("\n⚠️  LLM test failed.")
    else:
        print("\n❌ Connection test failed.")

if __name__ == "__main__":
    main()