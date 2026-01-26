import pyaudio
import numpy as np
from faster_whisper import WhisperModel
from PyQt6.QtCore import QThread, pyqtSignal
import config

class AudioWorker(QThread):
    text_ready = pyqtSignal(str)
    status_update = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.running = True
        self.model = WhisperModel("base", device="cpu", compute_type="int8")

    def run(self):
        p = pyaudio.PyAudio()
        
        # Find VB-Cable first, fallback to default microphone
        dev_idx = None
        
        # Try VB-Cable
        for i in range(p.get_device_count()):
            if "cable" in p.get_device_info_by_index(i)['name'].lower():
                dev_idx = i
                print(f"🎧 Using VB-Cable: Device {i}")
                break
        
        # Fallback to default microphone
        if dev_idx is None:
            print("⚠️  VB-Cable not found, using default microphone...")
            dev_idx = p.get_default_input_device_info()['index']
            print(f"🎤 Using default microphone: Device {dev_idx}")
        
        try:
            stream = p.open(format=pyaudio.paInt16, channels=1, rate=config.SAMPLE_RATE, 
                            input=True, input_device_index=dev_idx, frames_per_buffer=4096)
        except Exception as e:
            print(f"❌ Cannot open audio device {dev_idx}: {e}")
            print("🔧 Trying alternative devices...")
            
            # Try all available input devices
            for i in range(p.get_device_count()):
                info = p.get_device_info_by_index(i)
                if info['maxInputChannels'] > 0:
                    try:
                        stream = p.open(format=pyaudio.paInt16, channels=1, rate=config.SAMPLE_RATE,
                                      input=True, input_device_index=i, frames_per_buffer=4096)
                        dev_idx = i
                        print(f"✅ Successfully opened device {i}: {info['name']}")
                        break
                    except Exception:
                        continue
            else:
                raise RuntimeError("No working audio input device found!")
        
        while self.running:
            frames = []
            for _ in range(0, int(config.SAMPLE_RATE / 4096 * config.CHUNK_DURATION)):
                data = stream.read(4096, exception_on_overflow=False)
                frames.append(np.frombuffer(data, dtype=np.int16))
            
            audio = np.concatenate(frames).astype(np.float32) / 32768.0
            
            # STT
            segments, _ = self.model.transcribe(audio, language="ru", beam_size=1)
            text = " ".join([s.text for s in segments]).strip()
            
            if len(text) > 10 and "?" in text: # Question filter
                self.text_ready.emit(text)

        stream.stop_stream()
        stream.close()
        p.terminate()

    def stop(self):
        self.running = False