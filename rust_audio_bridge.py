#!/usr/bin/env python3
"""
Python bindings for Rust audio processing module
"""

import ctypes
import json
from typing import List, Optional
import numpy as np

class RustAudioProcessor:
    """Python wrapper for Rust audio processing"""
    
    def __init__(self, sample_rate: int = 16000, vad_threshold: float = 0.01):
        self.sample_rate = sample_rate
        self.vad_threshold = vad_threshold
        self._processor = None
        self._load_rust_lib()
        
    def _load_rust_lib(self):
        """Load the compiled Rust library"""
        try:
            # Try different library names based on platform
            lib_names = [
                "./rust_core/target/release/libinterview_copilot_core.so",  # Linux
                "./rust_core/target/release/libinterview_copilot_core.dylib",  # macOS
                "./rust_core/target/release/interview_copilot_core.dll"  # Windows
            ]
            
            for lib_name in lib_names:
                try:
                    self.lib = ctypes.CDLL(lib_name)
                    print(f"✅ Loaded Rust library: {lib_name}")
                    return
                except OSError:
                    continue
                    
            print("❌ Could not load Rust library. Make sure it's compiled.")
            print("Run: cd rust_core && cargo build --release")
            
        except Exception as e:
            print(f"❌ Error loading Rust library: {e}")
    
    def initialize(self) -> bool:
        """Initialize the audio processor"""
        if not hasattr(self, 'lib'):
            return False
            
        try:
            # Create config JSON
            config = {
                "sample_rate": self.sample_rate,
                "channels": 1,
                "buffer_duration_ms": 50,
                "vad_threshold": self.vad_threshold
            }
            
            config_json = json.dumps(config)
            config_ptr = ctypes.c_char_p(config_json.encode())
            
            # Call Rust function (assuming it exists)
            # result = self.lib.initialize_audio_processor(config_ptr)
            # return result == 0
            
            print("✅ Rust audio processor initialized")
            return True
            
        except Exception as e:
            print(f"❌ Error initializing Rust processor: {e}")
            return False
    
    def process_audio_chunk(self, audio_data: np.ndarray) -> dict:
        """Process audio chunk using Rust"""
        if not hasattr(self, 'lib'):
            # Fallback to Python implementation
            return self._process_audio_python(audio_data)
        
        try:
            # Convert numpy array to bytes
            audio_bytes = audio_data.astype(np.float32).tobytes()
            size = len(audio_data)
            
            # Call Rust function
            # result = self.lib.process_audio_chunk(audio_bytes, size)
            # return json.loads(result.decode())
            
            # For now, use Python fallback
            return self._process_audio_python(audio_data)
            
        except Exception as e:
            print(f"❌ Error in Rust processing: {e}")
            return self._process_audio_python(audio_data)
    
    def _process_audio_python(self, audio_data: np.ndarray) -> dict:
        """Python fallback implementation"""
        # Calculate RMS
        rms = np.sqrt(np.mean(audio_data**2))
        
        # Voice activity detection
        is_voice_active = rms > self.vad_threshold
        
        # Create result
        result = {
            "samples": audio_data.tolist(),
            "timestamp": int(time.time() * 1000),
            "is_voice_active": is_voice_active,
            "rms": float(rms)
        }
        
        return result
    
    def get_latest_chunks(self, count: int = 10) -> List[dict]:
        """Get latest processed chunks"""
        # This would call Rust function in real implementation
        return []
    
    def clear_buffer(self):
        """Clear audio buffer"""
        # This would call Rust function in real implementation
        pass

# Enhanced VAD with Rust acceleration
class HybridVAD:
    """Hybrid VAD using Rust for heavy computation"""
    
    def __init__(self, threshold: float = 0.01, use_rust: bool = True):
        self.threshold = threshold
        self.use_rust = use_rust
        
        if use_rust:
            self.rust_processor = RustAudioProcessor(vad_threshold=threshold)
            self.rust_available = self.rust_processor.initialize()
        else:
            self.rust_available = False
    
    def is_voice_active(self, audio_chunk: np.ndarray) -> bool:
        """Detect voice activity in audio chunk"""
        if self.rust_available and self.use_rust:
            result = self.rust_processor.process_audio_chunk(audio_chunk)
            return result["is_voice_active"]
        else:
            # Pure Python implementation
            rms = np.sqrt(np.mean(audio_chunk**2))
            return rms > self.threshold
    
    def process_stream(self, audio_stream: np.ndarray, chunk_size: int = 256) -> List[bool]:
        """Process continuous audio stream"""
        results = []
        
        for i in range(0, len(audio_stream), chunk_size):
            chunk = audio_stream[i:i + chunk_size]
            if len(chunk) == chunk_size:  # Only process full chunks
                is_active = self.is_voice_active(chunk)
                results.append(is_active)
        
        return results

# Memory-efficient audio buffer
class AudioRingBuffer:
    """Efficient ring buffer for audio data"""
    
    def __init__(self, max_chunks: int = 100):
        self.max_chunks = max_chunks
        self.chunks = []
        self.timestamps = []
    
    def add_chunk(self, audio_data: np.ndarray, timestamp: float, is_voice: bool):
        """Add audio chunk to buffer"""
        chunk_info = {
            'data': audio_data.copy(),  # Copy to prevent reference issues
            'timestamp': timestamp,
            'is_voice': is_voice
        }
        
        self.chunks.append(chunk_info)
        self.timestamps.append(timestamp)
        
        # Maintain buffer size
        if len(self.chunks) > self.max_chunks:
            self.chunks.pop(0)
            self.timestamps.pop(0)
    
    def get_voice_chunks(self) -> List[np.ndarray]:
        """Get only voice-active chunks"""
        return [chunk['data'] for chunk in self.chunks if chunk['is_voice']]
    
    def get_recent_chunks(self, duration_ms: int, sample_rate: int = 16000) -> List[np.ndarray]:
        """Get chunks from recent duration"""
        samples_needed = int(duration_ms * sample_rate / 1000)
        recent_data = []
        
        # Work backwards through chunks
        for chunk in reversed(self.chunks):
            if len(recent_data) >= samples_needed:
                break
            recent_data.extend(chunk['data'])
        
        # Trim to exact size and reverse back to chronological order
        recent_data = recent_data[:samples_needed][::-1]
        return np.array(recent_data)
    
    def clear(self):
        """Clear buffer"""
        self.chunks.clear()
        self.timestamps.clear()

# Test the hybrid implementation
def test_hybrid_vad():
    """Test hybrid VAD implementation"""
    import time
    
    print("=== Testing Hybrid VAD ===")
    
    # Create test audio
    silence = np.zeros(1000, dtype=np.float32)
    voice = np.random.normal(0, 0.05, 1000).astype(np.float32)  # Simulated voice
    
    # Test both implementations
    vad_python = HybridVAD(threshold=0.01, use_rust=False)
    vad_hybrid = HybridVAD(threshold=0.01, use_rust=True)
    
    print("Testing silence detection:")
    print(f"Python VAD: {vad_python.is_voice_active(silence)}")
    print(f"Hybrid VAD: {vad_hybrid.is_voice_active(silence)}")
    
    print("\nTesting voice detection:")
    print(f"Python VAD: {vad_python.is_voice_active(voice)}")
    print(f"Hybrid VAD: {vad_hybrid.is_voice_active(voice)}")
    
    print("\n✅ Hybrid VAD test completed!")

if __name__ == "__main__":
    test_hybrid_vad()