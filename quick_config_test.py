#!/usr/bin/env python3
"""
Quick Qwen configuration test
"""

def test_current_setup():
    """Test current configuration without installing models"""
    print("=== Current Setup Test ===\n")
    
    # Test 1: Check Python environment
    print("1. Python Environment:")
    import sys
    print(f"   Python version: {sys.version}")
    print(f"   Virtual env: {'Yes' if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix) else 'No'}")
    
    # Test 2: Check required packages
    print("\n2. Required Packages:")
    required_packages = ['requests', 'PyQt6', 'faster_whisper', 'pyaudio']
    for package in required_packages:
        try:
            __import__(package)
            print(f"   ✅ {package}")
        except ImportError as e:
            print(f"   ❌ {package} - {e}")
    
    # Test 3: Check Ollama connection
    print("\n3. Ollama Connection:")
    try:
        import requests
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        if response.status_code == 200:
            models = response.json().get('models', [])
            print(f"   ✅ Connected - {len(models)} models available")
            for model in models:
                print(f"      • {model['name']} ({model['size']//1024//1024//1024}GB)")
        else:
            print(f"   ❌ HTTP {response.status_code}")
    except Exception as e:
        print(f"   ❌ Connection failed: {e}")
    
    # Test 4: Check Qwen handler
    print("\n4. Qwen Handler:")
    try:
        from qwen_handler import QwenHandler
        handler = QwenHandler(use_cloud_api=False)
        print("   ✅ QwenHandler imported successfully")
        print("   ✅ Local mode ready")
    except Exception as e:
        print(f"   ❌ QwenHandler error: {e}")
    
    # Test 5: Check config
    print("\n5. Configuration:")
    try:
        from config import LLM_MODEL_NAME, USE_CLOUD_LLM, WHISPER_MODEL_SIZE
        print(f"   LLM Model: {LLM_MODEL_NAME}")
        print(f"   Cloud LLM: {USE_CLOUD_LLM}")
        print(f"   Whisper Size: {WHISPER_MODEL_SIZE}")
        print("   ✅ Configuration loaded")
    except Exception as e:
        print(f"   ❌ Config error: {e}")

def test_simple_qwen_request():
    """Test sending request to existing llama3.2 model"""
    print("\n=== Simple Model Test ===\n")
    
    try:
        import requests
        import json
        
        # Test with existing llama3.2 model
        url = "http://localhost:11434/api/generate"
        payload = {
            "model": "llama3.2",
            "prompt": "Answer briefly in Russian: What is React?",
            "stream": False,
            "options": {
                "temperature": 0.2,
                "num_predict": 50
            }
        }
        
        print("Testing with llama3.2 model...")
        response = requests.post(url, json=payload, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            answer = result.get('response', '').strip()
            print(f"✅ Success!")
            print(f"Question: What is React?")
            print(f"Answer: {answer}")
            return True
        else:
            print(f"❌ HTTP {response.status_code}")
            print(response.text)
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():
    print("Interview Copilot - Quick Configuration Test")
    print("=" * 50)
    
    test_current_setup()
    test_simple_qwen_request()
    
    print("\n" + "=" * 50)
    print("Next steps:")
    print("1. Install Qwen model: ollama pull qwen2.5:7b")
    print("2. Update config.py to use qwen2.5:7b")
    print("3. Run full test: python test_qwen_integration.py")
    print("4. Test GUI: python ghost_gui.py")

if __name__ == "__main__":
    main()