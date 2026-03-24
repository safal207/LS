#!/usr/bin/env python3
"""
Language Model Module (Module 3: LLM Processing)
Connects to Ollama phi3 API and generates responses to questions
"""

import requests
import time
import logging
import queue
import os
from typing import Optional
from .breaker import CircuitBreaker, CircuitOpenError
from .cot_adapter import COTAdapter
from .backends import LLMResponse, build_llm_backend
from .errors import LLMEmptyResponseError, LLMInvalidFormatError, as_llm_error
from .qwen_handler import QwenHandler
from .ram_model_selector import get_available_ram_gb, select_model
from config import (
    OLLAMA_HOST,
    SYSTEM_PROMPT,
    USE_CLOUD_LLM,
    USE_GROQ,
    GONKA_ENABLED,
    GROQ_API_KEY,
    USE_COTCORE,
    USE_BREAKER,
    LLM_RAM_AWARE,
    LLM_MODEL_NAME,
    LLM_BACKEND,
    LLM_FALLBACK_BACKEND,
    BREAKER_THRESHOLD,
    BREAKER_COOLDOWN,
)

logger = logging.getLogger(__name__)

def _compress_messages_for_hint(messages: Optional[list[dict]], max_messages: int = 2) -> Optional[list[dict]]:
    """Compress chat history to system messages plus the most recent turns.

    Used when ``WHISPER_MODE=1`` to reduce prompt size for hint-style
    generation.  Returns *messages* unchanged when it is ``None`` or empty.
    """
    if not messages:
        return messages
    system = [m for m in messages if m.get("role") == "system"]
    recent = messages[-max_messages:]
    return system + recent


def _chunk_ready_for_tts(text: str) -> bool:
    return text.endswith((".", ",", "!", "?", "\n"))


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
        qwen_api_key = os.getenv("QWEN_API_KEY", "")
        self.primary_model, self.fallback_model = self._resolve_models()
        self._qwen_handler = QwenHandler(
            use_cloud_api=USE_CLOUD_LLM,
            api_key=qwen_api_key,
            model_name=self.primary_model,
            raise_on_error=True,
        )
        router_local_handler = self._qwen_handler
        if USE_CLOUD_LLM:
            router_local_handler = QwenHandler(
                use_cloud_api=False,
                model_name=self.primary_model,
                raise_on_error=True,
            )
        self.backend_router = build_llm_backend(
            local_handler=router_local_handler,
            local_model=self.primary_model,
            local_fallback_model=self.fallback_model,
        )
        self.last_response: Optional[LLMResponse] = None

    @property
    def qwen_handler(self):
        return self._qwen_handler

    @qwen_handler.setter
    def qwen_handler(self, value) -> None:
        self._qwen_handler = value
        local_backend = getattr(self.backend_router, "backends", {}).get("local")
        if local_backend is not None and hasattr(local_backend, "handler"):
            local_backend.handler = value

    def _resolve_models(self) -> tuple[str, str]:
        if not LLM_RAM_AWARE:
            return LLM_MODEL_NAME, LLM_MODEL_NAME

        available_ram = get_available_ram_gb()
        primary, fallback = select_model(available_ram)
        logger.info(
            "RAM-aware model selection: primary=%s, fallback=%s (available RAM: %.1f GB)",
            primary,
            fallback,
            available_ram,
        )
        return primary, fallback

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
        """Return ``True`` if *cancel_event* is set, signalling abort.

        Accepts any object with an ``is_set()`` method (e.g.
        ``threading.Event``).  Returns ``False`` when *cancel_event* is
        ``None``.
        """
        return cancel_event is not None and getattr(cancel_event, "is_set", lambda: False)()

    def _generate(self, question: str, *, cancel_event=None, messages: Optional[list[dict]] = None,
                  stream: bool = False, on_token=None, label: str = "local") -> Optional[str]:
        """Core generation logic shared by local and cloud paths.

        Args:
            question: The user question or prompt text.
            cancel_event: Optional threading.Event; when set, generation is
                          abandoned early and ``None`` is returned.
            messages: Optional chat-history list for multi-turn conversations.
            stream: If ``True``, use streaming generation with *on_token*.
            on_token: Callback invoked with each streamed token string.
            label: ``"local"`` or ``"cloud"`` — controls logging context and
                   fallback eligibility.

        Returns:
            Generated response string, or ``None`` on failure/cancellation.

        Raises:
            No exceptions escape this method; all are caught, logged, and may
            trigger fallback via :meth:`_try_fallback`.
        """
        prompt = ""
        active_messages = _compress_messages_for_hint(messages) if os.getenv("WHISPER_MODE", "0") == "1" else messages
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

            logger.debug("Sending to Qwen (%s): %s...", label, question[:50])

            response = self.qwen_handler.generate_response(prompt, messages=active_messages, stream=stream, on_token=on_token)
            if response is None or (isinstance(response, str) and not response.strip()):
                raise LLMEmptyResponseError()
            if not isinstance(response, str):
                raise LLMInvalidFormatError("Expected string response")

            if self.breaker:
                self.breaker.after_success()
            if self._is_cancelled(cancel_event):
                return None

            self.last_response = LLMResponse(
                text=response,
                model=getattr(self.qwen_handler, "model_name", self.primary_model),
                provider=label,
                latency_ms=0.0,
            )
            logger.info("Generated %s response: %s...", label, response[:100])
            return response

        except Exception as exc:
            err = as_llm_error(exc)
            if self.breaker and err.trip_breaker:
                self.breaker.after_failure(err)
            if isinstance(err, LLMEmptyResponseError):
                logger.warning(str(err))
            else:
                logger.error("Error generating %s response (%s): %s", label, err.kind, err)
            self.last_response = LLMResponse(
                text="",
                model=getattr(self.qwen_handler, "model_name", self.primary_model),
                provider=label,
                latency_ms=0.0,
                error=str(err),
            )

            if self.fallback_model != self.primary_model:
                return self._try_fallback(label, prompt, active_messages, stream, on_token)
            return None

    def _try_fallback(self, label: str, prompt: str, active_messages, stream: bool, on_token) -> Optional[str]:
        """Attempt generation with the fallback model.

        Temporarily swaps the handler's model to :attr:`fallback_model` and
        retries.  On success the fallback is promoted to primary; on failure
        the original model is restored.

        Args:
            label: ``"local"`` or ``"cloud"`` — used for log context only.
            prompt: Already-composed prompt string.
            active_messages: Chat-history messages (may be compressed).
            stream: Whether to use streaming generation.
            on_token: Optional streaming token callback.

        Returns:
            Fallback response string, or ``None`` if the fallback also fails.

        Known limitations:
            The fallback always uses the same :attr:`fallback_model` regardless
            of *label*.  A future iteration may select different fallback
            targets per label.
        """
        current_model = self.qwen_handler.model_name
        fallback_succeeded = False
        try:
            logger.warning(
                "Primary %s model %s failed, switching to fallback %s",
                label,
                self.primary_model,
                self.fallback_model,
            )
            self.qwen_handler.model_name = self.fallback_model
            fallback_response = self.qwen_handler.generate_response(prompt, messages=active_messages, stream=stream, on_token=on_token)
            if isinstance(fallback_response, str) and fallback_response.strip():
                self.primary_model = self.fallback_model
                fallback_succeeded = True
                self.last_response = LLMResponse(
                    text=fallback_response,
                    model=self.fallback_model,
                    provider=label,
                    latency_ms=0.0,
                    was_fallback_used=True,
                    fallback_from=current_model,
                    fallback_to=self.fallback_model,
                )
                return fallback_response
        except Exception as fallback_exc:
            logger.error("Fallback model %s also failed (%s): %s", self.fallback_model, label, fallback_exc)
        finally:
            if not fallback_succeeded:
                self.qwen_handler.model_name = current_model
        return None

    def generate_response_local(self, question: str, cancel_event=None, messages: Optional[list[dict]] = None, *, stream: bool = False, on_token=None) -> Optional[str]:
        """Generate response using local Ollama Qwen."""
        return self._generate(question, cancel_event=cancel_event, messages=messages, stream=stream, on_token=on_token, label="local")

    def generate_response_cloud(self, question: str, cancel_event=None, messages: Optional[list[dict]] = None, *, stream: bool = False, on_token=None) -> Optional[str]:
        """Generate response using cloud Qwen API."""
        return self._generate(question, cancel_event=cancel_event, messages=messages, stream=stream, on_token=on_token, label="cloud")

    def _use_backend_router(self) -> bool:
        return bool(
            LLM_BACKEND
            or LLM_FALLBACK_BACKEND
            or USE_CLOUD_LLM
            or USE_GROQ
            or GONKA_ENABLED
        )

    def _generate_via_router(
        self,
        question: str,
        *,
        cancel_event=None,
        messages: Optional[list[dict]] = None,
        stream: bool = False,
        on_token=None,
    ) -> Optional[str]:
        if self._is_cancelled(cancel_event):
            return None
        active_messages = _compress_messages_for_hint(messages) if os.getenv("WHISPER_MODE", "0") == "1" else messages
        if active_messages:
            routed_messages = active_messages
            system_prompt = None
        else:
            routed_messages = [{"role": "user", "content": question}]
            system_prompt = SYSTEM_PROMPT

        response = self.backend_router.generate(
            messages=routed_messages,
            system_prompt=system_prompt,
            metadata={"question": question},
            stream=stream,
            on_token=on_token,
        )
        self.last_response = response
        if response.ok:
            logger.info(
                "Generated response via provider=%s model=%s fallback=%s",
                response.provider,
                response.model,
                response.was_fallback_used,
            )
            return response.text
        logger.error(
            "LLM backend route failed provider=%s error=%s fallback_from=%s fallback_to=%s",
            response.provider,
            response.error,
            response.fallback_from,
            response.fallback_to,
        )
        return None
    
    def generate_response(self, question: str, cancel_event=None, messages: Optional[list[dict]] = None, *, stream: bool = False, on_token=None) -> Optional[str]:
        """Generate response using either local or cloud LLM"""
        if self._use_backend_router():
            return self._generate_via_router(
                question,
                cancel_event=cancel_event,
                messages=messages,
                stream=stream,
                on_token=on_token,
            )
        if USE_CLOUD_LLM:
            logger.info("Using cloud LLM (Groq)")
            return self.generate_response_cloud(question, cancel_event=cancel_event, messages=messages, stream=stream, on_token=on_token)
        else:
            logger.info("Using local LLM (Ollama %s)", self.qwen_handler.model_name)
            return self.generate_response_local(question, cancel_event=cancel_event, messages=messages, stream=stream, on_token=on_token)
    
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
                        
                        logger.info(f"Processing question: {question}")
                        
                        # Generate response (streaming-first path)
                        tts_buffer: list[str] = []

                        def _on_token(token: str) -> None:
                            # NOTE: on_token is currently invoked synchronously inside generate_response,
                            # so tts_buffer access is single-threaded in this path.
                            # Revisit if generation threading/async model changes.
                            tts_buffer.append(token)
                            try:
                                self.output_queue.put_nowait({
                                    'type': 'token',
                                    'question': question,
                                    'text': token,
                                    'timestamp': time.time(),
                                })
                            except queue.Full:
                                logger.warning("UI queue full, dropping token")
                            joined = "".join(tts_buffer).strip()
                            if joined and _chunk_ready_for_tts(joined):
                                try:
                                    self.output_queue.put_nowait({
                                        'type': 'tts_chunk',
                                        'question': question,
                                        'text': joined,
                                        'timestamp': time.time(),
                                    })
                                    tts_buffer.clear()
                                except queue.Full:
                                    logger.warning("UI queue full, dropping tts chunk")

                        start_time = time.time()
                        raw_response = self.generate_response(question, stream=True, on_token=_on_token)
                        generation_time = time.time() - start_time

                        if raw_response:
                            formatted_response = self.format_response(raw_response)

                            logger.info(f"Response generated in {generation_time:.2f}s")

                            if tts_buffer:
                                try:
                                    self.output_queue.put_nowait({
                                        'type': 'tts_chunk',
                                        'question': question,
                                        'text': "".join(tts_buffer).strip(),
                                        'timestamp': time.time(),
                                    })
                                except queue.Full:
                                    logger.warning("UI queue full, dropping final tts chunk")

                            # Send final answer event
                            try:
                                self.output_queue.put_nowait({
                                    'type': 'final',
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
        while result.get('type') not in (None, 'final'):
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
