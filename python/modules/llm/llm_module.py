#!/usr/bin/env python3
"""
Language Model Module (Module 3: LLM Processing)
Connects to Ollama phi3 API and generates responses to questions
"""

import requests
import time
import logging
import queue
import threading
from typing import Optional
from .breaker import CircuitBreaker, CircuitOpenError
from .cot_adapter import COTAdapter
from .errors import LLMEmptyResponseError, LLMInvalidFormatError, as_llm_error
from .qwen_handler import QwenHandler
from ..config import (
    OLLAMA_HOST,
    SYSTEM_PROMPT,
    USE_CLOUD_LLM,
    GROQ_API_KEY,
    USE_COTCORE,
    USE_BREAKER,
    BREAKER_THRESHOLD,
    BREAKER_COOLDOWN,
)

logger = logging.getLogger(__name__)

class LanguageModel:
    def __init__(self, input_queue: queue.Queue, output_queue: queue.Queue, use_cotcore: Optional[bool] = None, use_breaker: Optional[bool] = None):
        self.input_queue = input_queue
        self.output_queue = output_queue
        self.running = False
        self.use_cotcore = USE_COTCORE if use_cotcore is None else use_cotcore
        self.use_breaker = USE_BREAKER if use_breaker is None else use_breaker
        self.breaker = CircuitBreaker(failure_threshold=BREAKER_THRESHOLD, cooldown_seconds=BREAKER_COOLDOWN) if self.use_breaker else None
        self.cot_adapter = COTAdapter() if self.use_cotcore else None
        
        # Initialize Qwen handler
        import os
        qwen_api_key = os.getenv("QWEN_API_KEY", "")
        self.qwen_handler = QwenHandler(
            use_cloud_api=USE_CLOUD_LLM,
            api_key=qwen_api_key,
            raise_on_error=True,
        )

    def _compose_prompt(self, question: str) -> str:
        prompt = f"{SYSTEM_PROMPT}\n\n\u0412\u043e\u043f\u0440\u043e\u0441: {question}\n\u041e\u0442\u0432\u0435\u0442:"
        if self.cot_adapter:
            return self.cot_adapter.process(question, prompt)
        return prompt

    def test_ollama_connection(self) -> bool:
        """Test connection to Ollama server"""
        try:
            # Simple check to see if Ollama is responsive
            response = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=2)
            if response.status_code == 200:
                logger.info("Successfully connected to Ollama")
                return True
            else:
                logger.warning(f"Ollama connected but returned status {response.status_code}")
                return False
        except Exception as e:
            logger.warning(f"Could not connect to Ollama: {e}")
            return False
        
    def _is_cancelled(self, cancel_event) -> bool:
        return cancel_event is not None and getattr(cancel_event, "is_set", lambda: False)()

    def generate_response_local(self, question: str, cancel_event=None) -> Optional[str]:
        """Generate response using local Ollama Qwen"""
        try:
            if self._is_cancelled(cancel_event):
                return None
            prompt = self._compose_prompt(question)

            if self._is_cancelled(cancel_event):
                return None

            if self.breaker:
                try:
                    self.breaker.before_call()
                except CircuitOpenError:
                    return "LLM temporarily unavailable. Please try again later."
            
            logger.debug(f"Sending to Qwen: {question[:50]}...")
            
            response = self.qwen_handler.generate_response(prompt)
            if response is None or (isinstance(response, str) and not response.strip()):
                raise LLMEmptyResponseError()
            if not isinstance(response, str):
                raise LLMInvalidFormatError("Expected string response")

            if self.breaker:
                self.breaker.after_success()
            if self._is_cancelled(cancel_event):
                return None
             
            logger.info(f"Generated response: {response[:100]}...")
            return response
                 
        except Exception as exc:
            err = as_llm_error(exc)
            if self.breaker and err.trip_breaker:
                self.breaker.after_failure(err)
            if isinstance(err, LLMEmptyResponseError):
                logger.warning(str(err))
            else:
                logger.error(f"Error generating local response ({err.kind}): {err}")
            return None
    
    def generate_response_cloud(self, question: str, cancel_event=None) -> Optional[str]:
        """Generate response using cloud Qwen API"""
        try:
            if self._is_cancelled(cancel_event):
                return None
            prompt = self._compose_prompt(question)

            if self._is_cancelled(cancel_event):
                return None

            if self.breaker:
                try:
                    self.breaker.before_call()
                except CircuitOpenError:
                    return "LLM temporarily unavailable. Please try again later."
            
            logger.debug(f"Sending to Qwen Cloud: {question[:50]}...")
            
            response = self.qwen_handler.generate_response(prompt)
            if response is None or (isinstance(response, str) and not response.strip()):
                raise LLMEmptyResponseError()
            if not isinstance(response, str):
                raise LLMInvalidFormatError("Expected string response")

            if self.breaker:
                self.breaker.after_success()
            if self._is_cancelled(cancel_event):
                return None
             
            logger.info(f"Generated cloud response: {response[:100]}...")
            return response
                 
        except Exception as exc:
            err = as_llm_error(exc)
            if self.breaker and err.trip_breaker:
                self.breaker.after_failure(err)
            if isinstance(err, LLMEmptyResponseError):
                logger.warning(str(err))
            else:
                logger.error(f"Error generating cloud response ({err.kind}): {err}")
            return None
    
    def generate_response(self, question: str, cancel_event=None) -> Optional[str]:
        """Generate response using either local or cloud LLM"""
        if USE_CLOUD_LLM:
            logger.info("Using cloud LLM (Groq)")
            return self.generate_response_cloud(question, cancel_event=cancel_event)
        else:
            logger.info("Using local LLM (Ollama phi3)")
            return self.generate_response_local(question, cancel_event=cancel_event)
    
    def format_response(self, response: str) -> str:
        """Format response for display"""
        if not response:
            return ""
        
        # Clean up response
        response = response.strip()
        
        # Remove common prefixes/phrases
        prefixes_to_remove = [
            "Ответ:", "Response:", "Вот ответ:", 
            "Как сеньор-разработчик,", "Как опытный разработчик,"
        ]
        
        for prefix in prefixes_to_remove:
            if response.startswith(prefix):
                response = response[len(prefix):].strip()
        
        # Format as bullet points if it looks like a list
        if '\n' in response and not response.startswith('-'):
            lines = [line.strip() for line in response.split('\n') if line.strip()]
            if len(lines) > 1:
                response = '\n'.join([f"• {line}" if not line.startswith('•') else line 
                                    for line in lines])
        
        return response
    
    def run(self):
        """Main LLM processing loop"""
        logger.info("Starting Language Model module")
        
        # Test connection first
        if not USE_CLOUD_LLM:
            if not self.test_ollama_connection():
                logger.error("Cannot connect to Ollama. Consider using cloud fallback.")
                if not GROQ_API_KEY:
                    logger.error("Cloud fallback not configured either.")
                    return
        
        self.running = True
        
        try:
            while self.running:
                try:
                    # Get question from queue
                    item = self.input_queue.get(timeout=1.0)
                    
                    if item['type'] == 'question':
                        question = item['text']
                        item['timestamp']
                        
                        logger.info(f"Processing question: {question}")
                        
                        # Generate response
                        start_time = time.time()
                        raw_response = self.generate_response(question)
                        generation_time = time.time() - start_time
                        
                        if raw_response:
                            formatted_response = self.format_response(raw_response)
                            
                            logger.info(f"Response generated in {generation_time:.2f}s")
                            
                            # Send to UI queue
                            try:
                                self.output_queue.put_nowait({
                                    'question': question,
                                    'response': formatted_response,
                                    'generation_time': generation_time,
                                    'timestamp': time.time()
                                })
                                logger.debug("Response sent to UI queue")
                            except queue.Full:
                                logger.warning("UI queue full, dropping response")
                        else:
                            logger.warning("Failed to generate response")
                    
                    self.input_queue.task_done()
                    
                except queue.Empty:
                    continue
                except Exception as e:
                    logger.error(f"LLM processing error: {e}")
                    
        except KeyboardInterrupt:
            logger.info("LLM module interrupted")
        except Exception as e:
            logger.error(f"LLM module error: {e}")
        finally:
            self.stop()
    
    def stop(self):
        """Stop LLM module"""
        logger.info("Stopping Language Model module")
        self.running = False
        logger.info("Language Model module stopped")

# Test function
def test_llm_module():
    """Test LLM module with sample question"""
    import queue
    
    # Create test queues
    input_queue = queue.Queue()
    output_queue = queue.Queue()
    
    # Create and start LLM module
    llm_module = LanguageModel(input_queue, output_queue)
    
    print("Testing LLM module...")
    
    # Put test question in queue
    test_question = "What is the difference between interface and type in TypeScript?"
    input_queue.put({
        'type': 'question',
        'text': test_question,
        'timestamp': time.time()
    })
    
    # Start module in separate thread
    llm_thread = threading.Thread(target=llm_module.run)
    llm_thread.start()
    
    # Wait for response
    try:
        result = output_queue.get(timeout=30)
        print(f"Question: {result['question']}")
        print(f"Response: {result['response']}")
        print(f"Generation time: {result['generation_time']:.2f}s")
    except queue.Empty:
        print("No response received (timeout)")
    
    # Stop module
    llm_module.stop()
    llm_thread.join()

if __name__ == "__main__":
    test_llm_module()
