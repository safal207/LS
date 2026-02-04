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

    def _find_preferred_device(self, p):
        candidates = []
        for i in range(p.get_device_count()):
            info = p.get_device_info_by_index(i)
            if info.get('maxInputChannels', 0) <= 0:
                continue
            name = info.get('name', '').lower()
            if 'cable' in name or 'vb-audio' in name:
                candidates.append((i, info))

        if candidates:
            for i, info in candidates:
                if 'output' in info.get('name', '').lower():
                    return i, info
            return candidates[0]

        try:
            info = p.get_default_input_device_info()
            return info['index'], info
        except Exception:
            for i in range(p.get_device_count()):
                info = p.get_device_info_by_index(i)
                if info.get('maxInputChannels', 0) > 0:
                    return i, info

        return None, None

    def run(self):
        self.status_update.emit("Audio: initializing")
        p = pyaudio.PyAudio()

        dev_idx, dev_info = self._find_preferred_device(p)
        if dev_idx is None:
            self.status_update.emit("Audio: no input devices found")
            return

        self.status_update.emit(f"Audio: using {dev_info.get('name', 'device')} (index {dev_idx})")

        try:
            stream = p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=config.SAMPLE_RATE,
                input=True,
                input_device_index=dev_idx,
                frames_per_buffer=4096,
            )
        except Exception as e:
            self.status_update.emit(f"Audio: open failed ({e})")
            stream = None

        if stream is None:
            # Try all available input devices
            for i in range(p.get_device_count()):
                info = p.get_device_info_by_index(i)
                if info.get('maxInputChannels', 0) <= 0:
                    continue
                try:
                    stream = p.open(
                        format=pyaudio.paInt16,
                        channels=1,
                        rate=config.SAMPLE_RATE,
                        input=True,
                        input_device_index=i,
                        frames_per_buffer=4096,
                    )
                    dev_idx = i
                    dev_info = info
                    self.status_update.emit(f"Audio: using {info.get('name', 'device')} (index {i})")
                    break
                except Exception:
                    continue

        if stream is None:
            self.status_update.emit("Audio: no working input device")
            return

        while self.running:
            frames = []
            for _ in range(0, int(config.SAMPLE_RATE / 4096 * config.CHUNK_DURATION)):
                data = stream.read(4096, exception_on_overflow=False)
                frames.append(np.frombuffer(data, dtype=np.int16))

            audio = np.concatenate(frames).astype(np.float32) / 32768.0

            segments, _ = self.model.transcribe(audio, language="ru", beam_size=1)
            text = " ".join([s.text for s in segments]).strip()

            if len(text) > 10 and "?" in text:
                self.text_ready.emit(text)

        stream.stop_stream()
        stream.close()
        p.terminate()

    def stop(self):
        self.running = False
