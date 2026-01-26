#!/usr/bin/env python3
"""
Setup checker for Interview Copilot
Verifies all required components are installed and configured
"""

import subprocess
import sys
import requests
from config import OLLAMA_HOST

def check_python_version():
    """Check Python version requirement"""
    version = sys.version_info
    print(f"Python version: {version.major}.{version.minor}.{version.micro}")
    if version.major >= 3 and version.minor >= 10:
        print("✅ Python version OK")
        return True
    else:
        print("❌ Python 3.10+ required")
        return False

def check_ollama_installed():
    """Check if Ollama is installed and running"""
    try:
        # Try to get Ollama version
        result = subprocess.run(['ollama', '--version'], 
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            print("✅ Ollama is installed")
            return True
        else:
            print("❌ Ollama not found in PATH")
            return False
    except (subprocess.TimeoutExpired, FileNotFoundError):
        print("❌ Ollama not installed or not in PATH")
        print("   Download from: https://ollama.com/")
        return False

def check_ollama_api():
    """Check if Ollama API is accessible"""
    try:
        response = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=5)
        if response.status_code == 200:
            print("✅ Ollama API is running")
            models = response.json().get('models', [])
            phi3_models = [m for m in models if 'phi3' in m['name']]
            if phi3_models:
                print(f"✅ Phi3 model found: {[m['name'] for m in phi3_models]}")
                return True
            else:
                print("⚠️  Phi3 model not found")
                print("   Run: ollama pull phi3")
                return False
        else:
            print("❌ Ollama API not responding")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Cannot connect to Ollama API: {e}")
        print("   Make sure Ollama is running")
        return False

def check_vb_cable():
    """Check if VB-Cable is installed (Windows specific)"""
    try:
        import pyaudio
        p = pyaudio.PyAudio()
        devices = []
        for i in range(p.get_device_count()):
            info = p.get_device_info_by_index(i)
            devices.append(info['name'])
        
        vb_cable_devices = [d for d in devices if 'cable' in d.lower()]
        if vb_cable_devices:
            print("✅ VB-Cable detected:")
            for device in vb_cable_devices:
                print(f"   - {device}")
            return True
        else:
            print("⚠️  VB-Cable not detected")
            print("   Download from: https://vb-audio.com/Cable/")
            return False
    except ImportError:
        print("❌ PyAudio not installed")
        return False
    except Exception as e:
        print(f"❌ Error checking audio devices: {e}")
        return False

def check_dependencies():
    """Check Python dependencies"""
    required_packages = ['faster_whisper', 'pyaudio', 'requests', 'numpy', 'psutil']
    missing = []
    
    for package in required_packages:
        try:
            __import__(package)
            print(f"✅ {package}")
        except ImportError:
            print(f"❌ {package} missing")
            missing.append(package)
    
    return len(missing) == 0

def main():
    print("=== Interview Copilot Setup Checker ===\n")
    
    checks = [
        ("Python Version", check_python_version),
        ("Dependencies", check_dependencies),
        ("Ollama Installation", check_ollama_installed),
        ("Ollama API", check_ollama_api),
        ("VB-Cable", check_vb_cable),
    ]
    
    results = []
    for name, check_func in checks:
        print(f"Checking {name}...")
        try:
            result = check_func()
            results.append((name, result))
        except Exception as e:
            print(f"❌ Error during {name} check: {e}")
            results.append((name, False))
        print()
    
    # Summary
    print("=== Summary ===")
    all_passed = True
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {name}")
        if not result:
            all_passed = False
    
    print()
    if all_passed:
        print("🎉 All checks passed! Ready to run Interview Copilot.")
        print("\nNext steps:")
        print("1. Change your system audio output to 'CABLE Input'")
        print("2. Run: python main.py")
    else:
        print("⚠️  Some checks failed. Please fix the issues above.")
    
    return all_passed

if __name__ == "__main__":
    main()