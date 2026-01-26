#!/usr/bin/env python3
"""
Temporary Audio Test using Stereo Mix
"""

import pyaudio
import numpy as np
from faster_whisper import WhisperModel
import time

def test_stereo_mix():
    """Test audio capture using Stereo Mix"""
    p = pyaudio.PyAudio()
    
    # Find Stereo Mix device
    stereo_mix_index = None
    for i in range(p.get_device_count()):
        info = p.get_device_info_by_index(i)
        if 'stereo mix' in info['name'].lower():
            stereo_mix_index = i
            print(f"Found Stereo Mix: Device {i} - {info['name']}")
            break
    
    if stereo_mix_index is None:
        print("❌ Stereo Mix not found!")
        return
    
    # Initialize Whisper
    print("Initializing Whisper model...")
    model = WhisperModel("base", device="cpu", compute_type="int8")
    
    # Open audio stream
    stream = p.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=16000,
        input=True,
        input_device_index=stereo_mix_index,
        frames_per_buffer=1024
    )
    
    print("🎤 Listening via Stereo Mix... (Press Ctrl+C to stop)")
    print("Speak or play audio to test...")
    
    try:
        while True:
            # Read audio data
            data = stream.read(1024, exception_on_overflow=False)
            audio_np = np.frombuffer(data, dtype=np.int16)
            audio_float = audio_np.astype(np.float32) / 32768.0
            
            # Check volume
            rms = np.sqrt(np.mean(audio_float**2))
            
            if rms > 0.01:  # Voice activity detected
                print(f"🔊 Audio detected! RMS: {rms:.4f}")
                
                # Transcribe (optional - uncomment if you want transcription)
                # segments, _ = model.transcribe(audio_float, language="ru")
                # text = " ".join([s.text for s in segments]).strip()
                # if text:
                #     print(f"📝 Transcribed: {text}")
            
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        print("\n⏹️  Stopped listening")
    finally:
        stream.stop_stream()
        stream.close()
        p.terminate()

if __name__ == "__main__":
    test_stereo_mix()