#!/usr/bin/env python3
"""
Qwen API Integration Module
Supports both Ollama Qwen and Alibaba Cloud Qwen API
"""

import requests
import json
import logging
from typing import Optional
from config import OLLAMA_HOST, LLM_MODEL_NAME

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30

class QwenHandler:
    def __init__(self, use_cloud_api: bool = False, api_key: str = ""):
        self.use_cloud_api = use_cloud_api
        self.api_key = api_key
        self.session = requests.Session()
        self.session.timeout = 30
        
    def generate_with_ollama(self, prompt: str) -> Optional[str]:
        """Generate response using Ollama Qwen model"""
        try:
            url = f"{OLLAMA_HOST}/api/generate"
            
            payload = {
                "model": LLM_MODEL_NAME,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.2,
                    "top_k": 40,
                    "top_p": 0.9,
                    "num_predict": 150,
                    "repeat_penalty": 1.1
                }
            }
            
            logger.debug(f"Sending to Ollama Qwen: {prompt[:50]}...")
            response = self.session.post(url, json=payload, timeout=DEFAULT_TIMEOUT)
            response.raise_for_status()
            
            result = response.json()
            answer = result.get('response', '').strip()
            
            if answer:
                logger.info(f"Qwen response: {answer[:100]}...")
                return answer
            else:
                logger.warning("Empty response from Qwen")
                return None
                
        except Exception as e:
            logger.error(f"Ollama Qwen error: {e}")
            return None
    
    def generate_with_cloud_api(self, prompt: str) -> Optional[str]:
        """Generate response using Alibaba Cloud Qwen API"""
        if not self.api_key:
            logger.error("Qwen API key not provided")
            return None
            
        try:
            # Alibaba Qwen API endpoint
            url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": "qwen-max",  # or qwen-plus for faster response
                "input": {
                    "messages": [
                        {"role": "user", "content": prompt}
                    ]
                },
                "parameters": {
                    "temperature": 0.2,
                    "max_tokens": 150,
                    "top_p": 0.9
                }
            }
            
            logger.debug(f"Sending to Qwen Cloud API: {prompt[:50]}...")
            response = self.session.post(url, headers=headers, json=payload, timeout=DEFAULT_TIMEOUT)
            response.raise_for_status()
            
            result = response.json()
            answer = result['output']['text'].strip()
            
            if answer:
                logger.info(f"Qwen Cloud response: {answer[:100]}...")
                return answer
            else:
                logger.warning("Empty response from Qwen Cloud")
                return None
                
        except Exception as e:
            logger.error(f"Qwen Cloud API error: {e}")
            return None
    
    def generate_response(self, prompt: str) -> Optional[str]:
        """Generate response using appropriate Qwen variant"""
        if self.use_cloud_api:
            return self.generate_with_cloud_api(prompt)
        else:
            return self.generate_with_ollama(prompt)

# Test function
def test_qwen_integration():
    """Test Qwen integration"""
    import os
    
    print("=== Qwen Integration Test ===\n")
    
    # Test Ollama Qwen first
    print("1. Testing Ollama Qwen...")
    handler = QwenHandler(use_cloud_api=False)
    
    test_prompt = "Answer briefly in Russian: What is React?"
    response = handler.generate_response(test_prompt)
    
    if response:
        print("âœ… Ollama Qwen working!")
        print(f"Question: {test_prompt}")
        print(f"Answer: {response}\n")
    else:
        print("âŒ Ollama Qwen not available\n")
    
    # Test Cloud API if key provided
    api_key = os.getenv("QWEN_API_KEY", "")
    if api_key:
        print("2. Testing Qwen Cloud API...")
        cloud_handler = QwenHandler(use_cloud_api=True, api_key=api_key)
        cloud_response = cloud_handler.generate_response(test_prompt)
        
        if cloud_response:
            print("âœ… Qwen Cloud API working!")
            print(f"Answer: {cloud_response}\n")
        else:
            print("âŒ Qwen Cloud API not working\n")
    else:
        print("2. Qwen Cloud API key not provided (skip test)\n")

if __name__ == "__main__":
    test_qwen_integration()
