#!/usr/bin/env python3
"""
Quick test to verify all modules can be imported and basic functionality works
"""

def test_imports():
    """Test that all modules can be imported"""
    print("Testing imports...")
    
    try:
        import config
        print("✅ config imported")
    except Exception as e:
        print(f"❌ config import failed: {e}")
        return False
    
    try:
        from shared import utils
        print("✅ utils imported")
    except Exception as e:
        print(f"❌ utils import failed: {e}")
        return False

    try:
        from audio import audio_module
        print("✅ audio_module imported")
    except Exception as e:
        print(f"❌ audio_module import failed: {e}")
        return False

    try:
        from stt import stt_module
        print("✅ stt_module imported")
    except Exception as e:
        print(f"❌ stt_module import failed: {e}")
        return False

    try:
        from llm import llm_module
        print("✅ llm_module imported")
    except Exception as e:
        print(f"❌ llm_module import failed: {e}")
        return False
    
    return True

def test_config():
    """Test configuration values"""
    print("\nTesting configuration...")
    
    try:
        from config import (
            MAX_RAM_USAGE_MB, TARGET_LATENCY_SEC, WHISPER_MODEL_SIZE,
            LLM_MODEL_NAME, SAMPLE_RATE, OLLAMA_HOST
        )
        
        print(f"✅ RAM limit: {MAX_RAM_USAGE_MB} MB")
        print(f"✅ Latency target: {TARGET_LATENCY_SEC} seconds")
        print(f"✅ Whisper model: {WHISPER_MODEL_SIZE}")
        print(f"✅ LLM model: {LLM_MODEL_NAME}")
        print(f"✅ Sample rate: {SAMPLE_RATE} Hz")
        print(f"✅ Ollama host: {OLLAMA_HOST}")
        
        return True
    except Exception as e:
        print(f"❌ Config test failed: {e}")
        return False

def test_utils():
    """Test utility functions"""
    print("\nTesting utilities...")
    
    try:
        from shared.utils import is_question
        
        # Test question detection
        test_cases = [
            ("What is React?", True),
            ("How does useState work?", True),
            ("Tell me about closures", True),
            ("This is a statement", False),
            ("I like programming", False),
            ("Почему используется TypeScript?", True),  # Russian
            ("Объясните разницу", True),  # Russian
        ]
        
        all_passed = True
        for text, expected in test_cases:
            result = is_question(text)
            status = "✅" if result == expected else "❌"
            print(f"  {status} '{text}' -> {result} (expected {expected})")
            if result != expected:
                all_passed = False
        
        return all_passed
    except Exception as e:
        print(f"❌ Utils test failed: {e}")
        return False

def main():
    print("=== Interview Copilot Quick Test ===\n")
    
    tests = [
        ("Imports", test_imports),
        ("Configuration", test_config),
        ("Utilities", test_utils),
    ]
    
    results = []
    for name, test_func in tests:
        print(f"--- {name} ---")
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"❌ {name} test crashed: {e}")
            results.append((name, False))
        print()
    
    # Summary
    print("=== Test Summary ===")
    all_passed = True
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {name}")
        if not result:
            all_passed = False
    
    print()
    if all_passed:
        print("🎉 All basic tests passed!")
        print("\nNext steps:")
        print("1. Install Ollama and pull phi3 model")
        print("2. Install VB-Cable")
        print("3. Run check_setup.py to verify everything")
        print("4. Run python main.py to start the application")
    else:
        print("⚠️  Some tests failed. Please check the errors above.")
    
    return all_passed

if __name__ == "__main__":
    main()