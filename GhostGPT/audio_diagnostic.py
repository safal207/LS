#!/usr/bin/env python3
"""
Audio Device Diagnostic Tool
"""

import pyaudio

def list_audio_devices():
    """List all available audio devices"""
    p = pyaudio.PyAudio()
    
    print("=== AUDIO DEVICE DIAGNOSTIC ===")
    print(f"Total audio devices: {p.get_device_count()}")
    print("=" * 50)
    
    vb_cable_found = False
    
    for i in range(p.get_device_count()):
        try:
            info = p.get_device_info_by_index(i)
            name = info['name']
            inputs = info['maxInputChannels']
            outputs = info['maxOutputChannels']
            
            print(f"Device {i}: {name}")
            print(f"  Input channels: {inputs}")
            print(f"  Output channels: {outputs}")
            
            # Check for VB-Cable
            if 'cable' in name.lower() or 'virtual' in name.lower():
                print(f"  🎯 VB-CABLE CANDIDATE FOUND!")
                vb_cable_found = True
                if inputs > 0:
                    print(f"  ✅ INPUT AVAILABLE")
                if outputs > 0:
                    print(f"  ✅ OUTPUT AVAILABLE")
            
            print("-" * 30)
            
        except Exception as e:
            print(f"Error getting device {i}: {e}")
    
    p.terminate()
    
    print("\n=== RECOMMENDATIONS ===")
    if not vb_cable_found:
        print("❌ VB-Cable not found! Please install VB-Audio Virtual Cable")
        print("📥 Download from: https://vb-audio.com/Cable/")
    else:
        print("✅ VB-Cable detected!")
        print("🔧 Next steps:")
        print("1. Set Zoom/Meet audio output to 'CABLE Input'")
        print("2. Enable 'Listen to this device' on 'CABLE Output'")
        print("3. Route to your headphones")

if __name__ == "__main__":
    list_audio_devices()