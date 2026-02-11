#!/usr/bin/env python3
"""
Audio Ingestion Module (Module 1)
Captures system audio from VB-Cable output and performs basic VAD
"""

import pyaudio
import numpy as np
import time
import logging
import queue
import tempfile
import os
from typing import Optional
from config import SAMPLE_RATE, AUDIO_CHUNK_DURATION, VOLUME_THRESHOLD

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
        """Find VB-Cable output device index"""
        try:
            for i in range(self.p.get_device_count()):
                info = self.p.get_device_info_by_index(i)
                device_name = info['name'].lower()

                # Look for VB-Cable output devices
                if ('cable' in device_name and 'output' in device_name) or \
                   ('vb-audio' in device_name and 'output' in device_name):
                    logger.info(f"Found VB-Cable device: {info['name']} (index: {i})")
                    return i

            # If specific output not found, try any cable device
            for i in range(self.p.get_device_count()):
                info = self.p.get_device_info_by_index(i)
                if 'cable' in info['name'].lower():
                    logger.info(f"Found VB-Cable device: {info['name']} (index: {i})")
                    return i

            logger.warning("VB-Cable device not found")
            return None

        except Exception as e:
            logger.error(f"Error finding VB-Cable device: {e}")
            return None

    def list_audio_devices(self):
        """List all available audio devices for debugging"""
        logger.info("Available audio devices:")
        for i in range(self.p.get_device_count()):
            info = self.p.get_device_info_by_index(i)
            logger.info(
                f"  [{i}] {info['name']} - "
                f"Inputs: {info['maxInputChannels']}, "
                f"Outputs: {info['maxOutputChannels']}"
            )

    def is_voice_active(self, audio_data: np.ndarray) -> bool:
        """
        Simple Voice Activity Detection based on amplitude threshold
        Returns True if voice is detected, False otherwise
        """
        if audio_data.dtype != np.float32:
            audio_data = audio_data.astype(np.float32)

        rms = np.sqrt(np.mean(audio_data ** 2))
        is_active = rms > VOLUME_THRESHOLD

        if is_active:
            logger.debug(f"Voice detected - RMS: {rms:.4f}")

        return is_active

    def save_audio_chunk(self, audio_data: np.ndarray) -> str:
        """Save audio chunk to temporary WAV file"""
        try:
            temp_file = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
            temp_filename = temp_file.name
            temp_file.close()

            # Save as WAV using soundfile (more reliable than scipy.io.wavfile)
            import soundfile as sf
            sf.write(temp_filename, audio_data, SAMPLE_RATE)

            logger.debug(f"Saved audio chunk: {temp_filename}")
            return temp_filename

        except ImportError:
            try:
                from scipy.io import wavfile
                temp_file = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
                temp_filename = temp_file.name
                temp_file.close()

                audio_int16 = (audio_data * 32767).astype(np.int16)
                wavfile.write(temp_filename, SAMPLE_RATE, audio_int16)

                logger.debug(f"Saved audio chunk: {temp_filename}")
                return temp_filename
            except Exception as e:
                logger.error(f"Failed to save audio chunk: {e}")
                return ""
        except Exception as e:
            logger.error(f"Failed to save audio chunk: {e}")
            return ""

    def start_stream(self) -> bool:
        """Initialize and start audio stream"""
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
            logger.info(f"Audio stream started on device {self.device_index}")
            return True

        except Exception as e:
            logger.error(f"Failed to start audio stream: {e}")
            return False

    def audio_callback(self, in_data, frame_count, time_info, status):
        """PyAudio callback for real-time audio processing"""
        if not self.running:
            return (None, pyaudio.paAbort)

        try:
            audio_data = np.frombuffer(in_data, dtype=np.float32)

            if self.is_voice_active(audio_data):
                temp_filename = self.save_audio_chunk(audio_data)

                if temp_filename:
                    try:
                        self.output_queue.put_nowait(temp_filename)
                        logger.debug(f"Queued audio file for transcription: {temp_filename}")
                    except queue.Full:
                        logger.warning("Transcription queue full, dropping chunk")
                        try:
                            os.unlink(temp_filename)
                        except Exception:
                            pass
            else:
                logger.debug("No voice activity detected")

        except Exception as e:
            logger.error(f"Error in audio callback: {e}")

        return (None, pyaudio.paContinue)

    def run(self):
        """Main audio capture loop"""
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
            logger.error(f"Audio ingestion error: {e}")
        finally:
            self.stop()

    def restart_stream(self):
        """Restart audio stream if it stops"""
        try:
            if self.stream:
                self.stream.stop_stream()
                self.stream.close()

            self.start_stream()
        except Exception as e:
            logger.error(f"Failed to restart stream: {e}")

    def stop(self):
        """Stop audio capture"""
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


# Test function
def test_audio_module():
    """Test the audio module standalone"""
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
