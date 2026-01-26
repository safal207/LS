#!/usr/bin/env python3
"""
Microphone Test Script
"""

import pyaudio
import numpy as np
import time

def test_microphones():
    """Test all available microphones"""
    p = pyaudio.PyAudio()
    
    print("=== MICROPHONE TESTING ===")
    
    # Find all input devices
    input_devices = []
    for i in range(p.get_device_count()):
        info = p.get_device_info_by_index(i)
        if info['maxInputChannels'] > 0:
            input_devices.append((i, info['name']))
            print(f"Found microphone: {i} - {info['name']}")
    
    print(f"\nTotal microphones found: {len(input_devices)}")
    
    # Test each device
    for device_index, device_name in input_devices:
        print(f"\n--- Testing Device {device_index}: {device_name} ---")
        
        try:
            # Open stream
            stream = p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=16000,
                input=True,
                input_device_index=device_index,
                frames_per_buffer=1024
            )
            
            # Test for 2 seconds
            max_level = 0
            for _ in range(20):  # 2 seconds at 0.1s intervals
                data = stream.read(1024, exception_on_overflow=False)
                audio_np = np.frombuffer(data, dtype=np.int16)
                audio_float = audio_np.astype(np.float32) / 32768.0
                rms = np.sqrt(np.mean(audio_float**2))
                max_level = max(max_level, rms)
                time.sleep(0.1)
            
            stream.stop_stream()
            stream.close()
            
            if max_level > 0.01:
                print(f"✅ WORKING! Max level: {max_level:.4f}")
            elif max_level > 0.001:
                print(f"⚠️  LOW SIGNAL: {max_level:.4f}")
            else:
                print(f"🔇 NO SIGNAL: {max_level:.4f}")
                
        except Exception as e:
            print(f"❌ ERROR: {e}")
    
    p.terminate()
    print("\n=== TEST COMPLETE ===")

if __name__ == "__main__":
    test_microphones()