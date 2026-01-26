#!/usr/bin/env python3
"""
Live Audio Monitoring for GhostGPT
"""

import pyaudio
import numpy as np
import time

def monitor_audio():
    """Monitor audio input in real-time"""
    p = pyaudio.PyAudio()
    
    print("=== LIVE AUDIO MONITOR ===")
    print("Looking for active audio input...")
    
    # Test all input devices
    for i in range(p.get_device_count()):
        try:
            info = p.get_device_info_by_index(i)
            if info['maxInputChannels'] > 0:
                print(f"\nTesting Device {i}: {info['name']}")
                
                # Try to open stream
                try:
                    stream = p.open(
                        format=pyaudio.paInt16,
                        channels=1,
                        rate=16000,
                        input=True,
                        input_device_index=i,
                        frames_per_buffer=1024
                    )
                    
                    print("✓ Stream opened successfully")
                    
                    # Listen for 3 seconds
                    audio_detected = False
                    for _ in range(30):  # 3 seconds at 0.1s intervals
                        data = stream.read(1024, exception_on_overflow=False)
                        audio_np = np.frombuffer(data, dtype=np.int16)
                        audio_float = audio_np.astype(np.float32) / 32768.0
                        rms = np.sqrt(np.mean(audio_float**2))
                        
                        if rms > 0.005:  # Low threshold for detection
                            print(f"🔊 Audio detected! Level: {rms:.4f}")
                            audio_detected = True
                            break
                        
                        time.sleep(0.1)
                    
                    if not audio_detected:
                        print("🔇 No audio detected")
                    
                    stream.stop_stream()
                    stream.close()
                    
                except Exception as e:
                    print(f"✗ Cannot open stream: {e}")
                    
        except Exception as e:
            print(f"Error with device {i}: {e}")
    
    p.terminate()
    print("\n=== MONITORING COMPLETE ===")

if __name__ == "__main__":
    monitor_audio()