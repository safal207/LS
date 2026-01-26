#!/usr/bin/env python3
"""
Install Qwen model programmatically
"""

import requests
import json
import time

def install_qwen_model(model_name="qwen2.5:7b"):
    """Install Qwen model using Ollama API"""
    print(f"Installing {model_name}...")
    
    try:
        # Send pull request
        url = "http://localhost:11434/api/pull"
        payload = {"name": model_name}
        
        print("Sending pull request...")
        response = requests.post(url, json=payload, stream=True, timeout=300)
        
        if response.status_code == 200:
            print("Download started. This may take several minutes...")
            
            # Stream the response to show progress
            for line in response.iter_lines():
                if line:
                    try:
                        data = json.loads(line.decode('utf-8'))
                        if 'status' in data:
                            print(f"  {data['status']}")
                        if 'digest' in data:
                            print(f"  Digest: {data['digest']}")
                    except:
                        print(f"  {line.decode('utf-8')}")
            
            print("✅ Model installation completed!")
            return True
        else:
            print(f"❌ HTTP {response.status_code}")
            print(response.text)
            return False
            
    except Exception as e:
        print(f"❌ Installation error: {e}")
        return False

def check_available_models():
    """Check what models are available"""
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        if response.status_code == 200:
            models = response.json().get('models', [])
            print(f"\nAvailable models ({len(models)}):")
            for model in models:
                size_gb = model['size'] // (1024**3)
                print(f"  • {model['name']} ({size_gb}GB)")
            return [m['name'] for m in models]
        return []
    except Exception as e:
        print(f"Error checking models: {e}")
        return []

def main():
    print("=== Qwen Model Installer ===\n")
    
    # Check current models
    current_models = check_available_models()
    
    # Check if Qwen is already installed
    qwen_models = [m for m in current_models if 'qwen' in m.lower()]
    
    if qwen_models:
        print("✅ Qwen models already installed:")
        for model in qwen_models:
            print(f"  • {model}")
        return
    
    print("\nQwen model not found. Installing qwen2.5:7b...")
    
    # Install Qwen model
    if install_qwen_model("qwen2.5:7b"):
        print("\n✅ Installation successful!")
        check_available_models()
    else:
        print("\n❌ Installation failed!")

if __name__ == "__main__":
    main()