"""Unit tests for AudioRingBuffer (deque-backed).

Tests cover:
- Basic add/retrieve
- Overflow behavior (maxlen eviction)
- Empty buffer edge cases
- High-frequency insertions
- get_voice_chunks filtering
- get_recent_chunks retrieval
- clear() behavior
"""

import sys
from pathlib import Path

root = Path(__file__).resolve().parents[2]
if str(root) not in sys.path:
    sys.path.insert(0, str(root))

import unittest
import numpy as np
from rust_audio_bridge import AudioRingBuffer


class TestAudioRingBufferBasic(unittest.TestCase):
    """Basic operations."""

    def test_add_and_retrieve(self):
        buf = AudioRingBuffer(max_chunks=10)
        data = np.array([0.1, 0.2, 0.3], dtype=np.float32)
        buf.add_chunk(data, 1000.0, True)
        self.assertEqual(len(buf.chunks), 1)
        self.assertEqual(len(buf.timestamps), 1)
        np.testing.assert_array_equal(buf.chunks[0]["data"], data)
        self.assertEqual(buf.timestamps[0], 1000.0)

    def test_voice_filtering(self):
        buf = AudioRingBuffer(max_chunks=10)
        voice = np.ones(10, dtype=np.float32)
        silence = np.zeros(10, dtype=np.float32)
        buf.add_chunk(voice, 1.0, True)
        buf.add_chunk(silence, 2.0, False)
        buf.add_chunk(voice, 3.0, True)
        result = buf.get_voice_chunks()
        self.assertEqual(len(result), 2)

    def test_clear(self):
        buf = AudioRingBuffer(max_chunks=10)
        for i in range(5):
            buf.add_chunk(np.zeros(10, dtype=np.float32), float(i), False)
        buf.clear()
        self.assertEqual(len(buf.chunks), 0)
        self.assertEqual(len(buf.timestamps), 0)

    def test_data_is_copied(self):
        """Ensure add_chunk copies data so the original can be mutated safely."""
        buf = AudioRingBuffer(max_chunks=5)
        original = np.array([1.0, 2.0, 3.0], dtype=np.float32)
        buf.add_chunk(original, 1.0, True)
        original[0] = 999.0
        self.assertAlmostEqual(buf.chunks[0]["data"][0], 1.0)


class TestAudioRingBufferOverflow(unittest.TestCase):
    """Overflow / eviction behavior."""

    def test_max_chunks_enforced(self):
        buf = AudioRingBuffer(max_chunks=3)
        for i in range(10):
            buf.add_chunk(np.array([float(i)], dtype=np.float32), float(i), True)
        self.assertEqual(len(buf.chunks), 3)
        self.assertEqual(len(buf.timestamps), 3)
        # Oldest should be evicted: chunks 7, 8, 9 remain
        self.assertAlmostEqual(buf.chunks[0]["data"][0], 7.0)
        self.assertAlmostEqual(buf.timestamps[0], 7.0)

    def test_overflow_preserves_newest(self):
        buf = AudioRingBuffer(max_chunks=1)
        buf.add_chunk(np.array([1.0], dtype=np.float32), 100.0, True)
        buf.add_chunk(np.array([2.0], dtype=np.float32), 200.0, False)
        self.assertEqual(len(buf.chunks), 1)
        self.assertAlmostEqual(buf.chunks[0]["data"][0], 2.0)
        self.assertAlmostEqual(buf.timestamps[0], 200.0)


class TestAudioRingBufferEmpty(unittest.TestCase):
    """Edge cases with empty buffer."""

    def test_get_voice_chunks_empty(self):
        buf = AudioRingBuffer(max_chunks=10)
        self.assertEqual(buf.get_voice_chunks(), [])

    def test_get_recent_chunks_empty(self):
        buf = AudioRingBuffer(max_chunks=10)
        result = buf.get_recent_chunks(1000)
        self.assertEqual(len(result), 0)

    def test_clear_empty_is_safe(self):
        buf = AudioRingBuffer(max_chunks=10)
        buf.clear()  # should not raise
        self.assertEqual(len(buf.chunks), 0)


class TestAudioRingBufferHighFrequency(unittest.TestCase):
    """Simulate high-frequency insertions."""

    def test_rapid_insertions(self):
        buf = AudioRingBuffer(max_chunks=50)
        for i in range(10_000):
            buf.add_chunk(
                np.random.randn(256).astype(np.float32),
                float(i) * 0.001,
                i % 3 == 0,
            )
        self.assertEqual(len(buf.chunks), 50)
        self.assertEqual(len(buf.timestamps), 50)

    def test_voice_chunks_after_rapid_fill(self):
        buf = AudioRingBuffer(max_chunks=100)
        for i in range(500):
            is_voice = i % 5 == 0
            buf.add_chunk(np.zeros(16, dtype=np.float32), float(i), is_voice)
        voice = buf.get_voice_chunks()
        # In the last 100 chunks (400..499), every 5th is voice
        expected_voice_count = sum(1 for i in range(400, 500) if i % 5 == 0)
        self.assertEqual(len(voice), expected_voice_count)


class TestAudioRingBufferGetRecent(unittest.TestCase):
    """Tests for get_recent_chunks."""

    def test_returns_correct_amount(self):
        buf = AudioRingBuffer(max_chunks=10)
        # Add 5 chunks of 16 samples each = 80 total samples
        for i in range(5):
            buf.add_chunk(np.ones(16, dtype=np.float32) * i, float(i), True)
        # Request 32 samples worth of data (2ms at 16kHz)
        result = buf.get_recent_chunks(2, sample_rate=16000)
        self.assertLessEqual(len(result), 32)

    def test_returns_all_if_not_enough_data(self):
        buf = AudioRingBuffer(max_chunks=10)
        buf.add_chunk(np.ones(8, dtype=np.float32), 1.0, True)
        result = buf.get_recent_chunks(10000, sample_rate=16000)
        # Only 8 samples available
        self.assertEqual(len(result), 8)


if __name__ == "__main__":
    unittest.main()
