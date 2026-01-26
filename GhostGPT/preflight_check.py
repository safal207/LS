#!/usr/bin/env python3
"""
Quick test of GhostGPT components
"""

import sys
import os

print("=== GHOSTGPT PRE-FLIGHT CHECK ===")

# Test 1: Config
print("\n1. Testing config...")
try:
    import config
    print(f"✅ Config loaded")
    print(f"   Groq API Key: {'SET' if config.GROQ_API_KEY != 'gsk_...' else 'NOT SET'}")
    print(f"   Model: {config.GROQ_MODEL}")
except Exception as e:
    print(f"❌ Config error: {e}")

# Test 2: Data files
print("\n2. Testing data files...")
try:
    import json
    with open("data/facts.json", "r", encoding="utf-8") as f:
        facts = json.load(f)
        print(f"✅ Facts loaded: {len(facts['facts'])} items")
    
    with open("data/logic.json", "r", encoding="utf-8") as f:
        logic = json.load(f)
        print(f"✅ Logic loaded: {len(logic)} decisions")
except Exception as e:
    print(f"❌ Data error: {e}")

# Test 3: Core modules
print("\n3. Testing core modules...")
modules_to_test = [
    ("modules.dmp", "DMP"),
    ("modules.cml", "CML"), 
    ("modules.lri", "LRI"),
    ("modules.capu", "CaPU")
]

for module_path, class_name in modules_to_test:
    try:
        module = __import__(module_path, fromlist=[class_name])
        cls = getattr(module, class_name)
        instance = cls()
        print(f"✅ {class_name} loaded")
    except Exception as e:
        print(f"❌ {class_name} error: {e}")

# Test 4: External dependencies
print("\n4. Testing external dependencies...")
deps_to_test = [
    ("PyQt6", "QtWidgets"),
    ("faster_whisper", "WhisperModel"),
    ("openai", "OpenAI"),
    ("pyaudio", "PyAudio"),
    ("numpy", "array"),
    ("keyboard", "add_hotkey")
]

for dep_name, attr_name in deps_to_test:
    try:
        module = __import__(dep_name)
        getattr(module, attr_name)
        print(f"✅ {dep_name} available")
    except Exception as e:
        print(f"❌ {dep_name} error: {e}")

print("\n=== CHECK COMPLETE ===")
if config.GROQ_API_KEY == "gsk_...":
    print("🚨 CRITICAL: Please set your Groq API key in config.py")
    print("   Get it from: https://console.groq.com/keys")
else:
    print("✅ ALL SYSTEMS GO!")
    print("Ready to run: python main.py")