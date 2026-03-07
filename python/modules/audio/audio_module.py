#!/usr/bin/env python3
"""
Audio Ingestion Module (Module 1)
Captures system audio and performs basic VAD before enqueueing in-memory PCM buffers.
"""

import logging
import queue
import time
from typing import Optional

import numpy as np
import pyaudio

from config import AUDIO_CHUNK_DURATION, SAMPLE_RATE, VOLUME_THRESHOLD

logger = logging.getLogger(__name__)


class AudioIngestion:
    def __init__(self, output_queue: queue.Queue):
        self.output_queue = output_queue
        self.p = pyaudio.PyAudio()
        self.stream = None
        self.running = False
        self.device_index = None
        self.chunk_size = int(SAMPLE_RATE * AUDIO_CHUNK_DURATION)

    def find_vb_cable_device(self) -> Optional[int]:
        """Find VB-Cable output device index."""
        try:
            for i in range(self.p.get_device_count()):
                info = self.p.get_device_info_by_index(i)
                device_name = info["name"].lower()

                if ("cable" in device_name and "output" in device_name) or (
                    "vb-audio" in device_name and "output" in device_name
                ):
                    logger.info("Found VB-Cable device: %s (index: %d)", info["name"], i)
                    return i

            for i in range(self.p.get_device_count()):
                info = self.p.get_device_info_by_index(i)
                if "cable" in info["name"].lower():
                    logger.info("Found VB-Cable device: %s (index: %d)", info["name"], i)
                    return i

            logger.warning("VB-Cable device not found")
            return None
        except Exception as e:
            logger.error("Error finding VB-Cable device: %s", e)
            return None

    def list_audio_devices(self):
        logger.info("Available audio devices:")
        for i in range(self.p.get_device_count()):
            info = self.p.get_device_info_by_index(i)
            logger.info(
                "  [%d] %s - Inputs: %s, Outputs: %s",
                i,
                info["name"],
                info["maxInputChannels"],
                info["maxOutputChannels"],
            )

    def is_voice_active(self, audio_data: np.ndarray) -> bool:
        if audio_data.dtype != np.float32:
            audio_data = audio_data.astype(np.float32, copy=False)

        rms = float(np.sqrt(np.mean(audio_data**2)))
        is_active = rms > VOLUME_THRESHOLD
        if is_active:
            logger.debug("Voice detected - RMS: %.4f", rms)
        return is_active

    def start_stream(self) -> bool:
        try:
            self.device_index = self.find_vb_cable_device()
            if self.device_index is None:
                logger.error("Cannot find VB-Cable device. Listing available devices:")
                self.list_audio_devices()
                return False

            self.stream = self.p.open(
                format=pyaudio.paFloat32,
                channels=1,
                rate=SAMPLE_RATE,
                input=True,
                input_device_index=self.device_index,
                frames_per_buffer=self.chunk_size,
                stream_callback=self.audio_callback,
            )

            self.stream.start_stream()
            logger.info("Audio stream started on device %s", self.device_index)
            return True
        except Exception as e:
            logger.error("Failed to start audio stream: %s", e)
            return False

    def audio_callback(self, in_data, frame_count, time_info, status):
        if not self.running:
            return (None, pyaudio.paAbort)

        try:
            audio_data = np.frombuffer(in_data, dtype=np.float32)
            if self.is_voice_active(audio_data):
                # hot path: in-memory only, no temp files
                pcm16 = (audio_data * 32767.0).astype(np.int16, copy=False)
                payload = {
                    "samples": pcm16,
                    "sample_rate": SAMPLE_RATE,
                    "timestamp": time.time(),
                }
                try:
                    self.output_queue.put_nowait(payload)
                    logger.debug("Queued audio chunk for transcription (%d samples)", pcm16.size)
                except queue.Full:
                    logger.warning("Transcription queue full, dropping chunk")
            else:
                logger.debug("No voice activity detected")

        except Exception as e:
            logger.error("Error in audio callback: %s", e)

        return (None, pyaudio.paContinue)

    def run(self):
        logger.info("Starting Audio Ingestion module")
        self.running = True

        if not self.start_stream():
            self.running = False
            logger.error("Failed to start audio stream")
            return

        try:
            while self.running:
                time.sleep(0.1)
                if self.stream and not self.stream.is_active():
                    logger.warning("Audio stream inactive, attempting restart")
                    self.restart_stream()
        except KeyboardInterrupt:
            logger.info("Audio ingestion interrupted")
        except Exception as e:
            logger.error("Audio ingestion error: %s", e)
        finally:
            self.stop()

    def restart_stream(self):
        try:
            if self.stream:
                self.stream.stop_stream()
                self.stream.close()
            self.start_stream()
        except Exception as e:
            logger.error("Failed to restart stream: %s", e)

    def stop(self):
        logger.info("Stopping Audio Ingestion module")
        self.running = False

        if self.stream:
            try:
                self.stream.stop_stream()
                self.stream.close()
            except Exception:
                pass

        try:
            self.p.terminate()
        except Exception:
            pass

        logger.info("Audio Ingestion module stopped")


def test_audio_module():
    import queue

    test_queue = queue.Queue()
    audio_module = AudioIngestion(test_queue)

    print("Testing Audio Ingestion module...")
    print("Press Ctrl+C to stop")

    try:
        audio_module.run()
    except KeyboardInterrupt:
        print("\nStopping test...")
        audio_module.stop()


if __name__ == "__main__":
    test_audio_module()
