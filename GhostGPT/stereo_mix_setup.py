#!/usr/bin/env python3
"""
Stereo Mix Enabler and Audio Router
"""

import pyaudio
import numpy as np
import time

def enable_stereo_mix():
    """Try to enable and test Stereo Mix"""
    p = pyaudio.PyAudio()
    
    print("=== STEREO MIX SETUP ===")
    
    # Look for Stereo Mix devices
    stereo_mix_devices = []
    for i in range(p.get_device_count()):
        info = p.get_device_info_by_index(i)
        name = info['name'].lower()
        if 'stereo mix' in name or 'stereo input' in name:
            stereo_mix_devices.append((i, info['name']))
            print(f"Found potential Stereo Mix: {i} - {info['name']}")
    
    if not stereo_mix_devices:
        print("❌ No Stereo Mix devices found")
        print("🔧 Try enabling in Windows Control Panel:")
        print("   Control Panel → Sound → Recording tab")
        print("   Right-click → Show Disabled Devices")
        print("   Enable 'Stereo Mix'")
        return False
    
    # Try to use each Stereo Mix device
    for device_index, device_name in stereo_mix_devices:
        print(f"\n--- Testing {device_name} ---")
        try:
            stream = p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=16000,
                input=True,
                input_device_index=device_index,
                frames_per_buffer=1024
            )
            
            print("✅ Successfully opened Stereo Mix!")
            
            # Test for 3 seconds
            print("🎤 Testing audio capture... (Play some sound)")
            max_level = 0
            detected = False
            
            for i in range(30):  # 3 seconds
                data = stream.read(1024, exception_on_overflow=False)
                audio_np = np.frombuffer(data, dtype=np.int16)
                audio_float = audio_np.astype(np.float32) / 32768.0
                rms = np.sqrt(np.mean(audio_float**2))
                max_level = max(max_level, rms)
                
                if rms > 0.005:  # Audio detected
                    print(f"🔊 Audio detected! Level: {rms:.4f}")
                    detected = True
                
                time.sleep(0.1)
            
            stream.stop_stream()
            stream.close()
            
            if detected:
                print(f"🎉 SUCCESS! Stereo Mix working with level {max_level:.4f}")
                p.terminate()
                return device_index
            else:
                print(f"🔇 No audio captured (max level: {max_level:.4f})")
                
        except Exception as e:
            print(f"❌ Error with device {device_index}: {e}")
    
    p.terminate()
    return False

def test_system_audio_capture(device_index):
    """Test capturing system audio"""
    print(f"\n=== TESTING SYSTEM AUDIO CAPTURE (Device {device_index}) ===")
    
    try:
        import pyaudio
        from faster_whisper import WhisperModel
        
        p = pyaudio.PyAudio()
        model = WhisperModel("base", device="cpu", compute_type="int8")
        
        stream = p.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=16000,
            input=True,
            input_device_index=device_index,
            frames_per_buffer=4096
        )
        
        print("🎤 Capturing 5 seconds of system audio...")
        print("🔊 Play music/video or speak near microphone")
        
        frames = []
        for _ in range(int(16000 / 4096 * 5)):  # 5 seconds
            data = stream.read(4096, exception_on_overflow=False)
            frames.append(np.frombuffer(data, dtype=np.int16))
        
        audio = np.concatenate(frames).astype(np.float32) / 32768.0
        
        # Try transcription
        print("📝 Attempting transcription...")
        segments, _ = model.transcribe(audio, language="ru", beam_size=1)
        text = " ".join([s.text for s in segments]).strip()
        
        if text:
            print(f"✅ TRANSCRIPTION SUCCESS: '{text}'")
        else:
            print("🔇 No speech detected in audio")
        
        stream.stop_stream()
        stream.close()
        p.terminate()
        
        return bool(text)
        
    except Exception as e:
        print(f"❌ Transcription error: {e}")
        return False

if __name__ == "__main__":
    # Try to enable Stereo Mix
    stereo_device = enable_stereo_mix()
    
    if stereo_device:
        print(f"\n🎯 Stereo Mix enabled on device {stereo_device}")
        success = test_system_audio_capture(stereo_device)
        if success:
            print("\n🎉 FULL SYSTEM AUDIO CAPTURE WORKING!")
        else:
            print("\n⚠️  Audio capture works but no speech detected")
    else:
        print("\n❌ Could not enable Stereo Mix")
        print("🔧 Manual setup required in Windows Audio settings")