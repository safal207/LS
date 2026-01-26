#!/usr/bin/env python3
"""
Audio Worker - Main thread for audio capture, STT, and LLM processing
"""

import sys
import queue
import threading
import time
import numpy as np
from PyQt6.QtCore import QThread, pyqtSignal
import pyaudio

from stt_module import SpeechToText
from llm_module import LanguageModel
from config import *

class AudioWorker(QThread):
    """
    Main worker thread that handles:
    1. Audio capture from VB-Cable
    2. Voice Activity Detection
    3. Speech-to-Text conversion
    4. LLM question analysis and response generation
    """
    
    # Signals for GUI updates
    text_ready = pyqtSignal(str, str)  # (question, answer)
    status_update = pyqtSignal(str)    # status messages
    system_stats = pyqtSignal(dict)    # CPU/RAM usage
    
    def __init__(self):
        super().__init__()
        self.running = False
        self.paused = False
        
        # Audio parameters
        self.chunk_size = int(SAMPLE_RATE * AUDIO_CHUNK_DURATION)
        self.format = pyaudio.paInt16
        self.audio_queue = queue.Queue(maxsize=100)
        
        # Modules
        self.stt_module = None
        self.llm_module = None
        self.pyaudio_instance = None
        self.stream = None
        
        # Buffers
        self.audio_buffer = []
        self.silence_counter = 0
        self.min_silence_chunks = int(1.0 / AUDIO_CHUNK_DURATION)  # 1 second of silence
        
    def initialize_modules(self):
        """Initialize STT and LLM modules"""
        try:
            self.status_update.emit("Initializing STT module...")
            # Create queues for STT module
            self.stt_input_queue = queue.Queue(maxsize=10)
            self.stt_output_queue = queue.Queue(maxsize=10)
            self.stt_module = SpeechToText(self.stt_input_queue, self.stt_output_queue)
            
            self.status_update.emit("Initializing LLM module...")
            # Create queues for LLM module
            self.llm_input_queue = queue.Queue(maxsize=10)
            self.llm_output_queue = queue.Queue(maxsize=10)
            self.llm_module = LanguageModel(self.llm_input_queue, self.llm_output_queue)
            
            self.status_update.emit("✅ All modules initialized")
            return True
        except Exception as e:
            self.status_update.emit(f"❌ Initialization error: {str(e)}")
            return False
    
    def setup_audio_stream(self):
        """Setup audio capture from VB-Cable"""
        try:
            self.pyaudio_instance = pyaudio.PyAudio()
            
            # Find VB-Cable input device
            device_index = self.find_vb_cable_input()
            if device_index is None:
                self.status_update.emit("❌ VB-Cable input not found")
                return False
            
            self.stream = self.pyaudio_instance.open(
                format=self.format,
                channels=1,  # Mono
                rate=SAMPLE_RATE,
                input=True,
                input_device_index=device_index,
                frames_per_buffer=self.chunk_size,
                stream_callback=self.audio_callback
            )
            
            self.status_update.emit(f"✅ Audio stream started (Device: {device_index})")
            return True
            
        except Exception as e:
            self.status_update.emit(f"❌ Audio setup error: {str(e)}")
            return False
    
    def find_vb_cable_input(self):
        """Find VB-Cable input device index"""
        try:
            info = self.pyaudio_instance.get_host_api_info_by_index(0)
            num_devices = info.get('deviceCount')
            
            for i in range(num_devices):
                device_info = self.pyaudio_instance.get_device_info_by_host_api_device_index(0, i)
                device_name = device_info.get('name', '').lower()
                
                # Look for VB-Cable devices
                if any(name in device_name for name in ['vb-cable', 'virtual cable', 'cable input']):
                    if device_info.get('maxInputChannels') > 0:
                        return i
                        
            # Fallback: try default input
            return self.pyaudio_instance.get_default_input_device_info()['index']
            
        except Exception:
            return None
    
    def audio_callback(self, in_data, frame_count, time_info, status):
        """PyAudio callback - put audio data in queue"""
        if self.running and not self.paused:
            try:
                # Convert bytes to numpy array
                audio_data = np.frombuffer(in_data, dtype=np.int16)
                audio_float = audio_data.astype(np.float32) / 32768.0
                
                # Apply VAD threshold
                rms = np.sqrt(np.mean(audio_float**2))
                if rms > VOLUME_THRESHOLD:
                    self.audio_queue.put_nowait({
                        'data': audio_float,
                        'rms': rms,
                        'timestamp': time.time()
                    })
                    
            except queue.Full:
                pass  # Drop chunk if queue is full
            except Exception as e:
                print(f"Audio callback error: {e}")
        
        return (None, pyaudio.paContinue)
    
    def process_audio_loop(self):
        """Main processing loop"""
        accumulated_audio = []
        question_detected = False
        
        while self.running:
            try:
                # Get audio chunk from queue
                chunk_data = self.audio_queue.get(timeout=0.1)
                accumulated_audio.extend(chunk_data['data'])
                
                # Accumulate enough audio for processing (2-3 seconds)
                if len(accumulated_audio) >= SAMPLE_RATE * 2:  # 2 seconds
                    audio_array = np.array(accumulated_audio)
                    
                    # Transcribe with Whisper
                    self.status_update.emit("🎤 Transcribing...")
                    transcription = self.stt_module.transcribe_audio(audio_array)
                    
                    if transcription and len(transcription.strip()) > 10:
                        self.status_update.emit(f"📝 Heard: {transcription[:50]}...")
                        
                        # Check if it's a question
                        if self.is_question(transcription):
                            self.status_update.emit("🤔 Question detected!")
                            
                            # Generate AI response
                            self.status_update.emit("🤖 Thinking...")
                            response = self.llm_module.generate_response(transcription)
                            
                            if response:
                                self.text_ready.emit(transcription, response)
                                self.status_update.emit("✅ Response ready")
                    
                    # Reset buffer
                    accumulated_audio = []
                    
            except queue.Empty:
                # No audio data - check for accumulated silence
                if accumulated_audio:
                    self.silence_counter += 1
                    if self.silence_counter > self.min_silence_chunks:
                        accumulated_audio = []  # Clear buffer
                        self.silence_counter = 0
                continue
            except Exception as e:
                self.status_update.emit(f"❌ Processing error: {str(e)}")
                time.sleep(0.1)
    
    def is_question(self, text):
        """Simple heuristic to detect questions"""
        question_indicators = [
            'what', 'how', 'why', 'when', 'where', 'which', 'can you',
            'could you', 'would you', 'tell me', 'explain', 'describe',
            '?', 'please'
        ]
        
        text_lower = text.lower()
        return any(indicator in text_lower for indicator in question_indicators)
    
    def run(self):
        """Main thread execution"""
        self.running = True
        self.status_update.emit("🚀 Starting Ghost Worker...")
        
        # Initialize modules
        if not self.initialize_modules():
            return
        
        # Setup audio
        if not self.setup_audio_stream():
            return
        
        # Start audio stream
        self.stream.start_stream()
        self.status_update.emit("🎧 Listening...")
        
        # Start processing loop
        try:
            self.process_audio_loop()
        except Exception as e:
            self.status_update.emit(f"❌ Worker error: {str(e)}")
        finally:
            self.cleanup()
    
    def stop(self):
        """Stop the worker gracefully"""
        self.status_update.emit("🛑 Stopping worker...")
        self.running = False
        self.wait()  # Wait for thread to finish
    
    def pause(self):
        """Pause processing"""
        self.paused = True
        self.status_update.emit("⏸️ Paused")
    
    def resume(self):
        """Resume processing"""
        self.paused = False
        self.status_update.emit("▶️ Resumed")
    
    def cleanup(self):
        """Cleanup resources"""
        try:
            if self.stream:
                self.stream.stop_stream()
                self.stream.close()
            if self.pyaudio_instance:
                self.pyaudio_instance.terminate()
            self.status_update.emit("🧹 Cleanup completed")
        except Exception as e:
            print(f"Cleanup error: {e}")

# Test function
def test_audio_worker():
    """Test the AudioWorker functionality"""
    from PyQt6.QtWidgets import QApplication, QLabel
    
    app = QApplication([])
    worker = AudioWorker()
    
    # Simple test UI
    status_label = QLabel("Starting test...")
    status_label.show()
    
    def update_status(text):
        status_label.setText(text)
        print(f"[STATUS] {text}")
    
    worker.status_update.connect(update_status)
    
    print("Starting AudioWorker test...")
    worker.start()
    
    # Run for 10 seconds
    time.sleep(10)
    
    print("Stopping worker...")
    worker.stop()
    
    app.exec()

if __name__ == "__main__":
    test_audio_worker()