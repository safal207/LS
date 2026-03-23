import logging
import sys
from pathlib import Path

import numpy as np
import pyaudio
from PyQt6.QtCore import QThread, pyqtSignal

import config

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SHARED_MODULES = _REPO_ROOT / "python" / "modules"
if str(_SHARED_MODULES) not in sys.path:
    sys.path.insert(0, str(_SHARED_MODULES))

from stt.factory import build_local_whisper_adapter

logger = logging.getLogger(__name__)


class AudioWorker(QThread):
    text_ready = pyqtSignal(str)
    status_update = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.running = True
        whisper_size = getattr(config, "WHISPER_MODEL_SIZE", "base")
        self.stt = build_local_whisper_adapter(
            model_size=whisper_size,
            device="cpu",
            compute_type="int8",
            vad_filter=True,
            local_files_only=False,
        )

    def _find_preferred_device(self, p):
        """Find the best available input device for audio capture.

        Preference order: VB-Cable output device > any VB-Cable device >
        default input device > first device with input channels.

        Returns:
            Tuple of ``(device_index, device_info)`` or ``(None, None)`` if
            no suitable device is found.
        """
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
        except Exception as e:
            logger.warning("Default input device unavailable: %s", e)
            for i in range(p.get_device_count()):
                info = p.get_device_info_by_index(i)
                if info.get('maxInputChannels', 0) > 0:
                    return i, info

        return None, None

    def run(self):
        self.status_update.emit("Audio: initializing")
        p = pyaudio.PyAudio()
        try:
            self._run_with_pyaudio(p)
        finally:
            p.terminate()

    def _run_with_pyaudio(self, p):
        """Core audio capture loop. Caller owns *p* and must call ``p.terminate()``.

        Opens a stream, reads chunks, transcribes, and emits detected
        questions. Stream is always closed via try/finally.
        """
        dev_idx, dev_info = self._find_preferred_device(p)
        if dev_idx is None:
            self.status_update.emit("Audio: no input devices found")
            return

        self.status_update.emit(f"Audio: using {dev_info.get('name', 'device')} (index {dev_idx})")
        self.status_update.emit(f"Audio: STT backend {self.stt.name}")

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
                except Exception as e:
                    logger.debug("Device %d failed: %s", i, e)
                    continue

        if stream is None:
            self.status_update.emit("Audio: no working input device")
            return

        try:
            while self.running:
                frames = []
                for _ in range(0, int(config.SAMPLE_RATE / 4096 * config.CHUNK_DURATION)):
                    data = stream.read(4096, exception_on_overflow=False)
                    frames.append(np.frombuffer(data, dtype=np.int16))

                audio = np.concatenate(frames).astype(np.float32) / 32768.0
                result = self.stt.transcribe_audio(audio)
                text = result.get("text", "").strip()

                if len(text) > 10 and "?" in text:
                    self.text_ready.emit(text)
        finally:
            stream.stop_stream()
            stream.close()

    def stop(self):
        self.running = False
